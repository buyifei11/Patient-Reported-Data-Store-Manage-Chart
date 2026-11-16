"""Offline replay preserves extraction failures, provenance, and old artifacts."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.replay_normalization import (ROOT, file_hash, replay, replay_row,
                                         verify_inputs, verify_predictions)
from src.pipeline import read_jsonl
from src.schema import validate_sources
from tests.test_normalization import candidate, report


class NormalizationReplayTests(unittest.TestCase):
    def test_valid_candidates_from_normalization_failure_are_replayed(self):
        text = "I vomited once today."
        source = report(text)
        saved = {"report_id": source["report_id"], "status": "error",
                 "error_code": "normalization_error", "error": "old failure",
                 "candidates": [candidate(text)], "observations": [],
                 "metadata": {"original": True}, "raw_response": "original response"}
        original = copy.deepcopy(saved)
        result = replay_row(source, saved)
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["error_code"])
        self.assertEqual(result["observations"][0]["count"], 1)
        self.assertEqual(result["candidates"], saved["candidates"])
        self.assertEqual(result["raw_response"], "original response")
        self.assertEqual(saved, original)

    def test_extraction_failure_is_never_converted_to_empty_success(self):
        source = report("I vomited today.")
        saved = {"report_id": source["report_id"], "status": "error",
                 "error_code": "invalid_schema", "error": "invalid model JSON",
                 "candidates": [], "observations": []}
        with patch("scripts.replay_normalization.normalize_report") as normalizer:
            self.assertEqual(replay_row(source, saved), saved)
            normalizer.assert_not_called()

    def test_replay_grounding_failure_keeps_candidates_and_error(self):
        source = report("I vomited once today.")
        saved = {"report_id": source["report_id"], "status": "ok", "error_code": None,
                 "error": None, "candidates": [candidate("invented quote")], "observations": []}
        result = replay_row(source, saved)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "normalization_error")
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["candidates"], saved["candidates"])

    def test_existing_output_directory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "summary.json").write_text("preserved")
            with self.assertRaisesRegex(ValueError, "already exists"):
                replay(Path("not-read"), output)
            self.assertEqual((output / "summary.json").read_text(), "preserved")

    def test_changed_evaluator_is_rejected(self):
        actual_hash = file_hash
        def changed_hash(path):
            return "changed" if path == ROOT / "src/evaluation.py" else actual_hash(path)
        with patch("scripts.replay_normalization.file_hash", side_effect=changed_hash):
            with self.assertRaisesRegex(ValueError, "src/evaluation.py"):
                verify_inputs(ROOT / "results/temporal-prompt-v2")

    def test_mislabeled_prompt_metadata_is_rejected(self):
        directory = ROOT / "results/temporal-prompt-v2"
        manifest = json.loads((directory / "manifest.json").read_text())
        sources = validate_sources(read_jsonl(ROOT / "data/heldout/reports.jsonl"))
        rows = read_jsonl(directory / "heldout-v1-r1.predictions.jsonl")
        rows[0]["metadata"]["prompt_label"] = "v2"
        with self.assertRaisesRegex(ValueError, "prompt_label"):
            verify_predictions(directory, manifest, sources, rows, "heldout", 1, "v1")

    def test_all_saved_runs_replay_without_settings_or_network_and_leave_inputs_untouched(self):
        directory = ROOT / "results/temporal-prompt-v2"
        original_hashes = {path: file_hash(path) for path in directory.iterdir() if path.is_file()}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "replay"
            with patch("src.pipeline.load_settings", side_effect=AssertionError("No settings")), \
                 patch("socket.create_connection", side_effect=AssertionError("No network")):
                summary = replay(directory, output)
            self.assertEqual(summary["model_requests"], 0)
            self.assertEqual(len(summary["runs"]), 6)
            self.assertEqual(sum(run["replayed_reports"] for run in summary["runs"].values()), 140)
            self.assertTrue(all(run["extraction_checks_unchanged"] for run in summary["runs"].values()))
            self.assertEqual(len(list(output.glob("*.metrics.json"))), 6)
            self.assertFalse(list(output.glob("*.predictions.jsonl")))
            self.assertEqual(json.loads((output / "summary.json").read_text()), summary)
        self.assertEqual({path: file_hash(path) for path in original_hashes}, original_hashes)


if __name__ == "__main__":
    unittest.main()
