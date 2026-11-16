"""Contract tests cover source context, strict parsing, and correction links."""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import unittest

from pydantic import ValidationError

from src.schema import CandidateBatch, GoldRecord, NormalizedObservation, SourceReport, local_date, validate_sources


ROOT = Path(__file__).resolve().parents[1]


def source(**changes):
    return {
        "report_id": "source-a",
        "patient_id": "patient-a",
        "reported_at": "2026-11-02T20:00:00-06:00",
        "patient_timezone": "America/Chicago",
        "text": "I felt nauseous today.",
        "questionnaire_answers": [],
        "supersedes_report_id": None,
    } | changes


def answer(**changes):
    return {"symptom": "vomiting", "event_date": "2026-11-02", "count": 1, "severity": None} | changes


def candidate(**changes):
    return {
        "symptom": "nausea", "assertion": "present", "count": None, "count_scope": None,
        "severity_value": None, "severity_scale_max": None, "severity_context": None,
        "time_text": "today", "day_reference": "today", "explicit_date": None,
        "clock_time": None, "quote": "I felt nauseous today.", "medication_relation": None,
    } | changes


def observation(**changes):
    return {
        "observation_id": "source-a-O1", "symptom": "nausea", "assertion": "present",
        "count": None, "count_scope": None, "severity": None, "event_date": "2026-11-02",
        "event_time": None, "time_text": "today", "date_basis": "relative_text", "medication_relation": None,
        "evidence": [{"path": "text", "value": "I felt nauseous today."}], "issues": [],
    } | changes


class SchemaTests(unittest.TestCase):
    def test_existing_source_and_gold_fixtures_obey_contract(self):
        rows = [json.loads(line) for line in (ROOT / "data/raw/reports.jsonl").read_text().splitlines()]
        references = [json.loads(line) for line in (ROOT / "data/gold/expected.jsonl").read_text().splitlines()]
        self.assertEqual(validate_sources(rows), rows)
        for reference in references:
            with self.subTest(report_id=reference["report_id"]):
                self.assertEqual(GoldRecord.model_validate(reference).model_dump(mode="json"), reference)

    def test_required_nullable_fields_cannot_be_omitted(self):
        row = source()
        del row["supersedes_report_id"]
        with self.assertRaises(ValidationError):
            SourceReport.model_validate(row)
        item = candidate()
        del item["severity_scale_max"]
        with self.assertRaises(ValidationError):
            CandidateBatch.model_validate({"candidates": [item]})

    def test_extra_properties_are_rejected_at_nested_boundaries(self):
        for row in (source(extra="field"), source(questionnaire_answers=[answer(extra="field")])):
            with self.subTest(row=row), self.assertRaises(ValidationError):
                SourceReport.model_validate(row)
        with self.assertRaises(ValidationError):
            CandidateBatch.model_validate({"candidates": [candidate(extra="field")]})

    def test_counts_and_ratings_are_strict_integers(self):
        for value in ("1", True, 1.0, -1):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                SourceReport.model_validate(source(questionnaire_answers=[answer(count=value)]))
        for value in (0, 6, "3", True):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                SourceReport.model_validate(source(questionnaire_answers=[answer(severity=value)]))

    def test_questionnaire_count_and_absence_coherence(self):
        for q in (answer(symptom="nausea", count=1), answer(count=0, severity=2)):
            with self.subTest(q=q), self.assertRaises(ValidationError):
                SourceReport.model_validate(source(questionnaire_answers=[q]))

    def test_questionnaire_uses_patient_local_date_not_timestamp_date(self):
        row = source(reported_at="2026-11-03T01:00:00Z", questionnaire_answers=[answer()])
        self.assertEqual(local_date(row), date(2026, 11, 2))
        row["questionnaire_answers"][0]["event_date"] = "2026-11-03"
        with self.assertRaises(ValidationError):
            SourceReport.model_validate(row)

    def test_timezone_snapshot_is_applied_at_daylight_saving_boundary(self):
        self.assertEqual(local_date(source(reported_at="2026-11-01T04:30:00Z")), date(2026, 10, 31))
        self.assertEqual(local_date(source(reported_at="2026-11-02T05:30:00Z")), date(2026, 11, 1))

    def test_invalid_timezone_and_offsetless_timestamp_are_rejected(self):
        for changes in ({"patient_timezone": "Invalid/Zone"}, {"reported_at": "2026-11-02T20:00:00"},
                        {"reported_at": "2026-11-02"}, {"reported_at": "2026-11-02T20:00:00+00:99"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                SourceReport.model_validate(source(**changes))

    def test_duplicate_questionnaire_answers_are_rejected(self):
        with self.assertRaises(ValidationError):
            SourceReport.model_validate(source(questionnaire_answers=[answer(), answer(count=2)]))

    def test_calendar_dates_and_clock_times_must_exist(self):
        for changes in ({"explicit_date": "2026-02-30"}, {"explicit_date": "11/02/2026"},
                        {"clock_time": "25:00"}, {"clock_time": "12:60"}, {"clock_time": "9:00"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                CandidateBatch.model_validate({"candidates": [candidate(**changes)]})

    def test_noncanonical_candidate_severity_survives_for_normalization(self):
        item = candidate(severity_value=2, severity_scale_max=10, severity_context="current")
        validated = CandidateBatch.model_validate({"candidates": [item]})
        self.assertEqual(validated.model_dump()["candidates"][0], item)

    def test_unknown_symptoms_and_assertions_are_rejected(self):
        for changes in ({"symptom": "fatigue"}, {"assertion": "definitely"}, {"count_scope": "total"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                CandidateBatch.model_validate({"candidates": [candidate(**changes)]})

    def test_empty_valid_candidate_batch_is_distinct_from_missing_batch(self):
        self.assertEqual(CandidateBatch.model_validate({"candidates": []}).candidates, [])
        with self.assertRaises(ValidationError):
            CandidateBatch.model_validate({})

    def test_duplicate_report_ids_cannot_silently_overwrite(self):
        for second in (source(), source(text="Changed contents")):
            with self.subTest(second=second), self.assertRaises(ValueError):
                validate_sources([source(), second])

    def test_valid_corrections_preserve_both_versions_and_input_order(self):
        replacement = source(report_id="source-b", reported_at="2026-11-02T21:00:00-06:00", supersedes_report_id="source-a")
        rows = [replacement, source()]
        original = deepcopy(rows)
        self.assertEqual(validate_sources(rows), rows)
        self.assertEqual(rows, original)

    def test_correction_targets_must_exist_and_belong_to_same_patient(self):
        replacement = source(report_id="source-b", reported_at="2026-11-02T21:00:00-06:00", supersedes_report_id="source-a")
        for rows in ([replacement], [source(patient_id="different"), replacement]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_sources(rows)

    def test_self_references_future_targets_and_cycles_are_rejected(self):
        with self.assertRaises(ValidationError):
            SourceReport.model_validate(source(supersedes_report_id="source-a"))
        for stamp in ("2026-11-02T19:00:00-06:00", "2026-11-03T02:00:00Z"):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                validate_sources([source(), source(report_id="source-b", reported_at=stamp, supersedes_report_id="source-a")])
        with self.assertRaises(ValueError):
            validate_sources([source(supersedes_report_id="source-b"), source(report_id="source-b", supersedes_report_id="source-a")])

    def test_normalized_intrinsic_coherence(self):
        for changes in ({"count": 1}, {"count_scope": "event"}, {"severity": 0},
                        {"assertion": "absent", "severity": 2}, {"assertion": "hypothetical", "severity": 2},
                        {"event_date": None}, {"date_basis": "unknown"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                NormalizedObservation.model_validate(observation(**changes))

    def test_unknown_date_can_retain_known_clock_time(self):
        row = observation(event_date=None, event_time="14:20", date_basis="unknown")
        self.assertEqual(NormalizedObservation.model_validate(row).event_time, "14:20")

    def test_evidence_paths_and_values_are_strict(self):
        for evidence in ([], [{"path": "invented", "value": "value"}], [{"path": "text", "value": True}]):
            with self.subTest(evidence=evidence), self.assertRaises(ValidationError):
                NormalizedObservation.model_validate(observation(evidence=evidence))

    def test_gold_checks_reject_unknown_fields_and_wrong_value_types(self):
        for expected in ({"counts": 1}, {"count": "1"}, {"count": -1}, {"severity_context": "today"}):
            row = {"report_id": "source-a", "observations": [],
                   "extraction_checks": [{"source": {"path": "text", "value": "source text"}, "expected_fields": expected}]}
            with self.subTest(expected=expected), self.assertRaises(ValidationError):
                GoldRecord.model_validate(row)


if __name__ == "__main__":
    unittest.main()
