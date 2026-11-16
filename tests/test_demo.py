"""End-to-end stored-data checks without credentials or model requests."""

import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.dashboard import write_dashboard
from src.demo import ROOT, _csv, build, prepare_predictions
from src.pipeline import _digest, read_jsonl
from src import store


class DemoTests(unittest.TestCase):
    def test_offline_pipeline_preserves_corrections_unknowns_and_sql_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo"
            with patch("socket.create_connection", side_effect=AssertionError("No network")), \
                 patch("src.pipeline.load_settings", side_effect=AssertionError("No credentials")):
                summary = build(out)
            self.assertEqual((summary["patients"], summary["reports"], summary["followup_patient_days"]), (3, 71, 84))
            self.assertEqual(summary["model_requests"], 0)
            self.assertEqual(summary["metadata"]["cached_text_reports"], 10)
            self.assertEqual(summary["metadata"]["questionnaire_reports"], 61)
            self.assertEqual(summary["metadata"]["reviewed_evidence_reports"], 0)
            self.assertIn("plus structured questionnaires", summary["metadata"]["description"])
            connection = store.connect(out / "patient_reports.sqlite")
            try:
                rows = {(r["patient_id"], r["event_date"]): r for r in store.daily_records(connection, "longitudinal-v1")}
                self.assertEqual(rows["P002", "2026-11-04"]["vomiting_count"], 2)
                self.assertEqual(rows["P001", "2026-11-03"]["vomiting_count"], 0)
                self.assertIsNone(rows["P001", "2026-11-03"]["nausea_severity"])
                self.assertIsNone(rows["P003", "2026-11-07"]["vomiting_count"])
                self.assertEqual(rows["P001", "2026-11-10"]["count_status"], "review")
                self.assertIsNone(rows["P001", "2026-11-10"]["vomiting_count"])
                self.assertEqual(rows["P003", "2026-11-01"]["count_status"], "missing")
                self.assertIsNone(rows["P003", "2026-11-01"]["vomiting_count"])
                stored = store.load_run(connection, "longitudinal-v1")
                original = next(p for p in stored["predictions"] if p["report_id"] == "R005")
                self.assertEqual(next(o["count"] for o in original["observations"] if o["symptom"] == "vomiting"), 3)
                self.assertEqual(len(store.weekly_counts(connection, "longitudinal-v1")), 15)
                medication_rows = store.after_medication_change(connection, "longitudinal-v1")
                self.assertTrue(any(r["report_id"] == "R003" and r["timing_status"] == "after" for r in medication_rows))
                self.assertTrue(any(r["report_id"] == "R010" and r["timing_status"] == "indeterminate" for r in medication_rows))
                self.assertFalse(any(r["report_id"] == "R005" for r in medication_rows))
                self.assertFalse(store.import_run(connection, run_id="longitudinal-v1", **stored))
                self.assertEqual(connection.execute("SELECT count(*) FROM reports").fetchone()[0], 71)
            finally:
                connection.close()
            self.assertIn('"vomiting_count": 2', (out / "dashboard.html").read_text())
            with self.assertRaisesRegex(ValueError, "already exists"):
                build(out)

    def test_uncached_text_and_changed_source_never_become_empty_success(self):
        cache = ROOT / "results/gpt54mini-dev-v1/predictions.jsonl"
        source = read_jsonl(ROOT / "data/raw/reports.jsonl")[0]
        for changed in ({**source, "report_id": "NEW-TEXT"}, {**source, "text": source["text"] + " Extra update."}):
            with self.subTest(report=changed["report_id"]), self.assertRaises(ValueError):
                prepare_predictions([changed], cache)

    def test_stale_cached_normalized_values_are_recomputed_from_candidates(self):
        source = read_jsonl(ROOT / "data/raw/reports.jsonl")[0]
        saved = copy.deepcopy(read_jsonl(ROOT / "results/gpt54mini-dev-v1/predictions.jsonl")[0])
        next(o for o in saved["observations"] if o["symptom"] == "vomiting")["count"] = 999
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache.jsonl"
            cache.write_text(json.dumps(saved) + "\n")
            result = prepare_predictions([source], cache)[0]
            self.assertEqual(next(o["count"] for o in result["observations"] if o["symptom"] == "vomiting"), 2)
            self.assertEqual(result["metadata"]["model_requests"], 0)

    def _reviewed_example(self):
        source = next(r for r in read_jsonl(ROOT / "data/text_validation/reports.jsonl")
                      if r["report_id"] == "TV007")
        saved = next(r for r in read_jsonl(ROOT / "results/text-validation-nausea/reviewed-evidence/predictions.jsonl")
                     if r["report_id"] == "TV007")
        return source, saved

    def test_reviewed_quote_is_reapplied_without_trusting_cached_values(self):
        source, saved = self._reviewed_example()
        next(o for o in saved["observations"] if o["symptom"] == "nausea")["severity"] = 1
        original = copy.deepcopy(saved)
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache.jsonl"
            cache.write_text(json.dumps(saved) + "\n")
            result = prepare_predictions([source], cache)[0]
        self.assertEqual(result["status"], "ok")
        nausea = next(o for o in result["observations"] if o["symptom"] == "nausea")
        self.assertEqual(nausea["severity"], 5)
        self.assertEqual(nausea["evidence"], [{"path": "text", "value": source["text"]}])
        self.assertEqual(result["candidates"], saved["candidates"])
        self.assertEqual(result["raw_response"], saved["raw_response"])
        self.assertEqual(result["evidence_review"]["review"], saved["evidence_review"]["review"])
        self.assertEqual(result["metadata"]["original_inference_metadata"], saved["metadata"])
        self.assertEqual(result["metadata"]["processing_mode"], "reviewed_candidate_replay")
        self.assertEqual(result["metadata"]["model_requests"], 0)
        self.assertEqual(saved, original)

    def test_unreviewed_noncontiguous_quote_stays_failed(self):
        source, saved = self._reviewed_example()
        saved.pop("evidence_review")
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache.jsonl"
            cache.write_text(json.dumps(saved) + "\n")
            result = prepare_predictions([source], cache)[0]
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "normalization_error")
        self.assertEqual(result["observations"], [])

    def test_reviewed_cache_rejects_changed_hash_source_or_candidate(self):
        for alteration in ("envelope", "review_hash", "source_hash", "candidate"):
            source, saved = self._reviewed_example()
            envelope = saved["evidence_review"]
            if alteration == "envelope":
                envelope["kind"] = "unreviewed"
            elif alteration == "review_hash":
                envelope["review_sha256"] = "changed"
            elif alteration == "source_hash":
                envelope["review"]["source_sha256"] = "changed"
                envelope["review_sha256"] = _digest(envelope["review"])
            else:
                next(c for c in saved["candidates"] if c["symptom"] == "nausea")["severity_value"] = 1
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as tmp:
                cache = Path(tmp) / "cache.jsonl"
                cache.write_text(json.dumps(saved) + "\n")
                with self.assertRaises(ValueError):
                    prepare_predictions([source], cache)

    def test_all_text_build_preserves_review_and_labels_its_data_source(self):
        source, saved = self._reviewed_example()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            dataset = directory / "sources"
            dataset.mkdir()
            (dataset / "reports.jsonl").write_text(json.dumps(source) + "\n")
            (dataset / "patients.json").write_text(json.dumps([{
                "patient_id": source["patient_id"], "display_name": "Fictional text patient",
                "patient_timezone": source["patient_timezone"],
                "followup_start": "2026-11-14", "followup_end": "2026-11-14",
            }]))
            (dataset / "medication_changes.json").write_text("[]\n")
            cache = directory / "cache.jsonl"
            cache.write_text(json.dumps(saved) + "\n")
            with patch("socket.create_connection", side_effect=AssertionError("No network")), \
                 patch("src.pipeline.load_settings", side_effect=AssertionError("No credentials")):
                summary = build(directory / "demo", dataset, cache, "all-text-review")
            self.assertEqual(summary["failed_reports"], 0)
            self.assertEqual(summary["metadata"]["cached_text_reports"], 1)
            self.assertEqual(summary["metadata"]["questionnaire_reports"], 0)
            self.assertEqual(summary["metadata"]["reviewed_evidence_reports"], 1)
            self.assertIn("all reports use saved LLM text extractions", summary["metadata"]["description"])
            self.assertEqual(summary["model_requests"], 0)
            connection = store.connect(directory / "demo/patient_reports.sqlite", read_only=True)
            try:
                stored = store.load_run(connection, "all-text-review")
                self.assertEqual(stored["predictions"][0]["evidence_review"]["review"], saved["evidence_review"]["review"])
                day = store.daily_records(connection, "all-text-review")[0]
                self.assertEqual((day["vomiting_count"], day["nausea_severity"]), (2, 5))
            finally:
                connection.close()

    def test_dashboard_source_text_cannot_terminate_the_data_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dashboard.html"
            write_dashboard(path, {"text": "</script><script>alert('source')</script>"})
            html = path.read_text()
            self.assertNotIn("</script><script>alert", html)
            self.assertIn("\\u003c/script>", html)
            with self.assertRaises(FileExistsError):
                write_dashboard(path, {})

    def test_csv_source_labels_do_not_execute_as_spreadsheet_formulas(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.csv"
            _csv(path, [{"label": "  =1+1", "zero": 0, "unknown": None, "negative": -2}])
            with path.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row, {"label": "'  =1+1", "zero": "0", "unknown": "", "negative": "-2"})


if __name__ == "__main__":
    unittest.main()
