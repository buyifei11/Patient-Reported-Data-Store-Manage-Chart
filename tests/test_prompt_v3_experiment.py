"""The v3 comparison stays frozen and exposes paired errors without API calls."""

from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.run_prompt_v3 import (MODEL, PROMPTS, ROOT, checked_manifest,
                                  material_mismatches, paired_reports, run, score)
from src.experiment import file_hash, verify_run_metadata
from src.pipeline import _code_digest, _digest, read_jsonl


class PromptV3Tests(unittest.TestCase):
    def test_changed_frozen_input_stops_before_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "manifest.json").write_text(json.dumps({
                "files": {"src/normalization.py": "wrong-hash"},
            }))
            with patch("scripts.run_prompt_v3.run_frozen") as runner:
                with self.assertRaisesRegex(ValueError, "Frozen input changed"):
                    run(directory, "regression")
                runner.assert_not_called()

    def test_other_experiment_cannot_be_reused(self):
        with patch("scripts.run_prompt_v3.verify_manifest", return_value={"experiment": "other"}):
            with self.assertRaisesRegex(ValueError, "bounded v3 comparison"):
                checked_manifest(Path("unused"))

    def test_existing_output_prevents_model_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            existing = directory / "regression-v3-r1.predictions.jsonl"
            existing.write_text("preserved")
            manifest = {"prompts": PROMPTS, "repeats": {"regression": 2}}
            with patch("scripts.run_prompt_v3.checked_manifest", return_value=manifest), \
                 patch("src.experiment.verify_manifest", return_value=manifest), \
                 patch("src.experiment._sources", return_value=[]), \
                 patch("src.experiment.load_settings", return_value={"OPENAI_API_KEY": "test-key"}), \
                 patch("src.experiment.extract_candidates") as client:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    run(directory, "regression")
                client.assert_not_called()
            self.assertEqual(existing.read_text(), "preserved")

    def test_wrong_prompt_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "manifest.json").write_text("{}")
            manifest = {"model": MODEL, "experiment": "scope-evidence-v3", "prompts": PROMPTS,
                        "files": {PROMPTS["v3"]: "hash-v3"}}
            metadata = self.metadata(directory, manifest, [], "v3", 1)
            metadata["prompt_label"] = "v1"
            with self.assertRaisesRegex(ValueError, "prompt_label"):
                verify_run_metadata(directory, manifest, [], [{"report_id": "X", "status": "ok", "metadata": metadata}],
                                    "regression", 1, "v3")

    def test_paired_report_distinguishes_new_and_resolved_errors(self):
        mismatches = {
            "v1": {"mismatches": [{"report_id": "A", "kind": "field", "field": "count", "expected": 2, "predicted": 1}]},
            "v3": {"mismatches": [{"report_id": "B", "kind": "report_failure", "status": "error"}]},
        }
        rows = {"v1": [{"report_id": "A", "status": "ok"}, {"report_id": "B", "status": "ok"}],
                "v3": [{"report_id": "A", "status": "ok"}, {"report_id": "B", "status": "error", "error_code": "normalization_error"}]}
        paired = paired_reports([{"report_id": "A"}, {"report_id": "B"}], mismatches, rows)
        self.assertEqual([row["classification"] for row in paired], ["resolved_errors", "new_errors"])
        self.assertEqual(paired[1]["error_code"]["v3"], "normalization_error")

    def test_time_text_boundary_and_date_basis_are_diagnostic_only(self):
        metrics = {"mismatches": [
            {"report_id": "A", "kind": "field", "field": "time_text"},
            {"report_id": "A", "kind": "field", "field": "date_basis"},
            {"report_id": "A", "kind": "extraction_check", "differences": [{"field": "time_text"}]},
            {"report_id": "A", "kind": "extraction_check", "differences": [{"field": "count_scope"}, {"field": "time_text"}]},
        ]}
        original = copy.deepcopy(metrics)
        result = material_mismatches(metrics, "A")
        self.assertEqual(result, [{"report_id": "A", "kind": "extraction_check", "differences": [{"field": "count_scope"}]}])
        self.assertEqual(metrics, original)

    @staticmethod
    def metadata(directory, manifest, sources, label, repeat):
        return {"backend": "openai", "requested_model": MODEL, "returned_model": MODEL,
                "experiment": manifest["experiment"], "split": "regression", "repeat": repeat,
                "prompt_label": label, "prompt_file_sha256": manifest["files"][PROMPTS[label]],
                "manifest_sha256": file_hash(directory / "manifest.json"),
                "source_dataset_sha256": _digest(sources), "code_sha256": _code_digest()}

    def test_score_writes_full_metrics_and_pairing_without_network_or_settings(self):
        source = read_jsonl(ROOT / "data/raw/reports.jsonl")[0]
        gold = read_jsonl(ROOT / "data/gold/expected.jsonl")[0]
        # This controlled scorer test isolates a normalized-count regression;
        # it is not a model evaluation and has no extraction targets.
        gold["extraction_checks"] = []
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = {"experiment": "scope-evidence-v3", "model": MODEL, "prompts": PROMPTS,
                        "files": {path: f"hash-{label}" for label, path in PROMPTS.items()},
                        "groups": {"regression": []}, "repeats": {"regression": 2},
                        "reference_roles": {"regression": "known_regression_data"}}
            (directory / "manifest.json").write_text(json.dumps(manifest))
            for repeat in (1, 2):
                for label in PROMPTS:
                    observations = copy.deepcopy(gold["observations"])
                    if label == "v1":
                        next(o for o in observations if o["symptom"] == "vomiting")["count"] = 9
                    row = {"report_id": source["report_id"], "status": "ok", "error": None,
                           "error_code": None, "candidates": [], "observations": observations,
                           "metadata": self.metadata(directory, manifest, [source], label, repeat)}
                    (directory / f"regression-{label}-r{repeat}.predictions.jsonl").write_text(json.dumps(row) + "\n")
            with patch("scripts.run_prompt_v3.checked_manifest", return_value=manifest), \
                 patch("scripts.run_prompt_v3.sources_for", return_value=[source]), \
                 patch("scripts.run_prompt_v3.validate_fixtures", return_value=[gold]), \
                 patch("src.pipeline.load_settings", side_effect=AssertionError("No settings")), \
                 patch("src.experiment.load_settings", side_effect=AssertionError("No settings")), \
                 patch("socket.create_connection", side_effect=AssertionError("No network")), redirect_stdout(io.StringIO()):
                score(directory, "regression")
                before = (directory / "regression-v1-r1.metrics.json").read_bytes()
                with self.assertRaisesRegex(ValueError, "already exists"):
                    score(directory, "regression")
                self.assertEqual((directory / "regression-v1-r1.metrics.json").read_bytes(), before)
            metrics = json.loads((directory / "regression-v3-r1.metrics.json").read_text())
            self.assertEqual(metrics["reference_role"], "known_regression_data")
            self.assertEqual(metrics["fields"]["count"]["reference_known"]["correct"], 1)
            paired = json.loads((directory / "regression-r1.paired.json").read_text())
            self.assertEqual(paired["reports"][0]["classification"], "resolved_errors")
            self.assertEqual(len(list(directory.glob("*.metrics.json"))), 4)
            self.assertEqual(len(list(directory.glob("*.paired.json"))), 2)


if __name__ == "__main__":
    unittest.main()
