"""Checks that experiment controls fail closed without paid requests."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.experiment import ROOT, file_hash, run, score, verify_manifest, verify_run_metadata


class ExperimentTests(unittest.TestCase):
    def test_modified_frozen_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            manifest = {"files": {"prompts/extraction_v1.txt": "incorrect-hash"}}
            (directory / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "Frozen input changed"):
                verify_manifest(directory)

    def test_existing_run_blocks_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "development-v1-r1.predictions.jsonl").write_text("preserved")
            manifest = {"repeats": {"development": 1}, "prompts": {"v1": "a", "v2": "b"}}
            with patch("src.experiment.verify_manifest", return_value=manifest), \
                 patch("src.experiment._sources", return_value=[]), \
                 patch("src.experiment.load_settings", return_value={"OPENAI_API_KEY": "test-key"}), \
                 patch("src.experiment.extract_candidates") as client:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    run(directory, "development")
                client.assert_not_called()
            self.assertEqual((directory / "development-v1-r1.predictions.jsonl").read_text(), "preserved")

    def test_missing_credentials_produce_no_prediction_files(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            with patch("src.experiment.verify_manifest", return_value={}), \
                 patch("src.experiment._sources", return_value=[]), \
                 patch("src.experiment.load_settings", return_value={}), \
                 patch("src.experiment.extract_candidates") as client:
                with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                    run(directory, "development")
                client.assert_not_called()
            self.assertEqual(list(directory.iterdir()), [])

    def test_prompt_freeze_preserves_baseline_and_changes_only_day_instruction(self):
        v1 = (ROOT / "prompts/extraction_v1.txt").read_text().splitlines()
        v2 = (ROOT / "prompts/extraction_v2.txt").read_text().splitlines()
        self.assertEqual(file_hash(ROOT / "prompts/extraction_v1.txt"), "d88b76baa0f7454fd31495e03df07a5a607651718714bc24ec67b5103fa55cd7")
        differences = [(a, b) for a, b in zip(v1, v2) if a != b]
        self.assertEqual(len(v1), len(v2))
        self.assertEqual(len(differences), 1)
        self.assertTrue(all(line.startswith("- day_reference:") for line in differences[0]))

    def test_wrong_prompt_output_cannot_be_scored_under_other_label(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "manifest.json").write_text("{}")
            manifest = {"model": "pinned", "experiment": "example", "prompts": {"v2": "prompt.txt"},
                        "files": {"prompt.txt": "v2-file-hash"}}
            from src.pipeline import _code_digest, _digest
            metadata = {"backend": "openai", "requested_model": "pinned", "experiment": "example",
                        "split": "heldout", "repeat": 1, "prompt_label": "v1",
                        "prompt_file_sha256": "v2-file-hash", "manifest_sha256": file_hash(directory / "manifest.json"),
                        "source_dataset_sha256": _digest([]), "code_sha256": _code_digest()}
            with self.assertRaisesRegex(ValueError, "prompt_label"):
                verify_run_metadata(directory, manifest, [], [{"report_id": "X", "status": "ok", "metadata": metadata}],
                                    "heldout", 1, "v2")

    def test_empty_interrupted_outputs_are_scored_as_missing(self):
        from contextlib import redirect_stdout
        import io
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "development-v1-r1.predictions.jsonl").write_text("")
            manifest = {"groups": {"development": []}, "repeats": {"development": 1}, "prompts": {"v1": "x"}}
            with patch("src.experiment.verify_manifest", return_value=manifest), \
                 patch("src.experiment._sources", return_value=[{"report_id": "X"}]), \
                 patch("src.experiment.validate_fixtures", return_value=[]), \
                 patch("src.experiment.verify_run_metadata"), \
                 patch("src.experiment.file_hash", return_value="hash"), \
                 patch("src.experiment.evaluate_predictions", return_value={"report_completion": {"missing": 1},
                       "fields": {"event_date": {"reference_known": {}}}, "assertion_accuracy": {}, "unknown_overfill": {}}) as evaluator, \
                 patch("src.experiment.extract_candidates") as client, redirect_stdout(io.StringIO()):
                score(directory, "development")
            self.assertEqual(evaluator.call_args.args[2], [])
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
