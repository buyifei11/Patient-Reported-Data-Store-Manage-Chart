"""Integration boundaries: failures, secrets, and reference-free extraction."""

from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.llm import ExtractionError
from pydantic import ValidationError

from src.pipeline import ROOT, load_settings, main, process_report, read_jsonl, validate_fixtures, validate_predictions
from src.schema import validate_sources


def report():
    return {
        "report_id": "T1", "patient_id": "P1",
        "reported_at": "2026-11-15T20:00:00-06:00", "patient_timezone": "America/Chicago",
        "text": "I have vomited once in total so far today.",
        "questionnaire_answers": [{"symptom": "vomiting", "event_date": "2026-11-15", "count": 0, "severity": None}],
        "supersedes_report_id": None,
    }


def candidate():
    return {
        "symptom": "vomiting", "assertion": "present", "count": 1, "count_scope": "day_to_date",
        "severity_value": None, "severity_scale_max": None, "severity_context": None,
        "time_text": "so far today", "day_reference": "today", "explicit_date": None,
        "clock_time": None, "quote": report()["text"], "medication_relation": None,
    }


class PipelineTests(unittest.TestCase):
    def test_fixture_validation_without_model(self):
        sources = validate_sources(read_jsonl(ROOT / "data/raw/reports.jsonl"))
        gold = validate_fixtures(sources, read_jsonl(ROOT / "data/gold/expected.jsonl"))
        self.assertEqual((len(sources), sum(len(row["observations"]) for row in gold)), (10, 15))

    def test_pre_reconciliation_value_is_preserved(self):
        seen = []
        def extractor(text):
            seen.append(text)
            return {"candidates": [candidate()], "metadata": {}, "raw_response": "test-only output"}
        result = process_report(report(), extractor, {})
        self.assertEqual(seen, [report()["text"]])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["candidates"][0]["count"], 1)
        self.assertIsNone(result["observations"][0]["count"])
        self.assertEqual(result["observations"][0]["assertion"], "uncertain")

    def test_extraction_failure_is_not_successful_empty(self):
        def fail(text):
            raise ExtractionError("invalid_json", "Invalid model JSON", raw_response="broken")
        result = process_report(report(), fail, {})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "invalid_json")
        self.assertEqual(result["raw_response"], "broken")

    def test_normalization_failure_retains_candidates(self):
        value = candidate()
        value["quote"] = "Invented text"
        result = process_report(report(), lambda text: {"candidates": [value], "metadata": {}, "raw_response": "raw"}, {})
        self.assertEqual(result["error_code"], "normalization_error")
        self.assertEqual(result["candidates"], [value])
        self.assertEqual(result["observations"], [])

    def test_successful_empty_report(self):
        source = report()
        source.update(text="I picked up my groceries.", questionnaire_answers=[])
        result = process_report(source, lambda text: {"candidates": [], "metadata": {}, "raw_response": '{"candidates":[]}'}, {})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["observations"], [])

    def test_saved_prediction_schema_is_checked(self):
        result = process_report(report(), lambda text: {"candidates": [candidate()], "metadata": {}, "raw_response": "raw"}, {})
        result["observations"][0]["issues"] = [{}]
        with self.assertRaises(ValidationError):
            validate_predictions([report()], [result])

    def test_predictions_from_changed_source_are_rejected(self):
        result = process_report(report(), lambda text: {"candidates": [candidate()], "metadata": {}, "raw_response": "raw"}, {})
        changed = report()
        changed["text"] = "A different source."
        with self.assertRaisesRegex(ValueError, "different source"):
            validate_predictions([changed], [result])

    def test_env_parser_has_no_shell_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("OPENAI_API_KEY='literal-$(not-executed)'\nOPENAI_MODEL=local-value\n")
            with patch.dict(os.environ, {"OPENAI_MODEL": "environment-value"}, clear=True):
                settings = load_settings(path)
            self.assertEqual(settings["OPENAI_API_KEY"], "literal-$(not-executed)")
            self.assertEqual(settings["OPENAI_MODEL"], "environment-value")

    def test_extract_cli_never_reads_gold(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.jsonl"
            with patch("src.pipeline.extract_local", return_value={"candidates": [], "metadata": {}, "raw_response": '{"candidates":[]}'}), \
                 patch("src.pipeline.load_settings", return_value={}), \
                 patch("src.pipeline.validate_fixtures", side_effect=AssertionError("Gold read during extraction")), \
                 redirect_stdout(io.StringIO()):
                result = main(["extract", "--provider", "ollama", "--model", "test-model", "--limit", "1", "--output", str(path)])
            self.assertEqual(result, 0)
            self.assertEqual(len(read_jsonl(path)), 1)
            self.assertEqual(read_jsonl(path)[0]["metadata"]["selected_report_count"], 1)

    def test_existing_output_is_preserved_without_model_call(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.jsonl"
            path.write_text("original")
            with patch("src.pipeline.extract_local") as extractor, \
                 patch("src.pipeline.load_settings", return_value={}), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main(["extract", "--provider", "ollama", "--model", "test-model", "--output", str(path)])
            self.assertEqual(raised.exception.code, 2)
            extractor.assert_not_called()
            self.assertEqual(path.read_text(), "original")

    def test_service_failure_stops_before_requesting_remaining_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.jsonl"
            with patch("src.pipeline.extract_local", side_effect=ExtractionError("network_error", "Unavailable")) as extractor, \
                 patch("src.pipeline.load_settings", return_value={}), redirect_stdout(io.StringIO()):
                result = main(["extract", "--provider", "ollama", "--model", "test-model", "--limit", "2", "--output", str(path)])
            self.assertEqual(result, 1)
            self.assertEqual(extractor.call_count, 1)
            rows = read_jsonl(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "error")

    def test_missing_key_fails_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.jsonl"
            with patch("src.pipeline.load_settings", return_value={}), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main(["extract", "--provider", "openai", "--model", "test-model", "--output", str(path)])
            self.assertEqual(raised.exception.code, 2)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
