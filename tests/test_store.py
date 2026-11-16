"""SQLite preserves raw history and queries only the explicitly chosen run."""

import copy
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from datetime import date, timedelta
import unittest

from src.normalization import normalize_report
from src.pipeline import _digest
from src.store import (after_medication_change, connect, daily_records, import_run,
                       load_run, review_queue, save_analysis, weekly_counts)
from tests.test_normalization import candidate


def patient(**changes):
    value = {"patient_id": "P", "display_name": "Synthetic patient", "patient_timezone": "America/Chicago",
             "followup_start": "2026-07-04", "followup_end": "2026-07-05"}
    return {**value, **changes}


def source(identifier="R1", count=3, **changes):
    value = {"report_id": identifier, "patient_id": "P", "reported_at": "2026-07-04T20:00:00-05:00",
             "patient_timezone": "America/Chicago", "text": "", "supersedes_report_id": None,
             "questionnaire_answers": [{"symptom": "vomiting", "event_date": "2026-07-04", "count": count, "severity": None}]}
    return {**value, **changes}


def prediction(report, candidates=None):
    candidates = candidates or []
    return {"report_id": report["report_id"], "status": "ok", "candidates": candidates,
            "observations": normalize_report(report, candidates), "error": None, "error_code": None,
            "raw_response": None, "metadata": {"source_sha256": _digest(report)}}


def analysis(reports, *, first_count=3, effective=None):
    daily = []
    for index in range(2):
        day = date(2026, 7, 4) + timedelta(days=index)
        count = first_count if index == 0 else None
        daily.append({"patient_id": "P", "event_date": day.isoformat(), "week_start": "2026-06-29",
                      "vomiting_count": count, "count_basis": "day_to_date" if count is not None else None,
                      "count_status": "usable" if count is not None else "missing", "nausea_severity": None,
                      "nausea_status": "missing", "vomiting_severity": None, "vomiting_severity_status": "missing",
                      "report_count": len(reports) if index == 0 else 0,
                      "source_report_ids": [r["report_id"] for r in reports] if index == 0 else [], "review_reasons": []})
    return {"daily": daily, "review": [], "corrections": [],
            "effective_report_ids": effective if effective is not None else [r["report_id"] for r in reports]}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)

    def ingest(self, reports=None, predictions=None, patients=None, changes=None, run_id="demo", metadata=None):
        reports = reports if reports is not None else [source()]
        return import_run(self.db, run_id=run_id, patients=patients or [patient()], reports=reports,
                          predictions=predictions if predictions is not None else [prediction(r) for r in reports],
                          medication_changes=changes or [], metadata=metadata)

    def test_read_only_connection_does_not_initialize_an_existing_database(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "unrelated ? database.sqlite"
            with sqlite3.connect(path) as original:
                original.execute("CREATE TABLE sentinel(value TEXT)")
                original.execute("INSERT INTO sentinel VALUES ('preserved')")
            original.close()
            before = path.read_bytes()
            connection = connect(path, read_only=True)
            try:
                self.assertEqual(connection.execute("SELECT value FROM sentinel").fetchone()[0], "preserved")
                self.assertEqual([row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")], ["sentinel"])
                with self.assertRaises(sqlite3.OperationalError):
                    connection.execute("CREATE TABLE unexpected(value INTEGER)")
                with self.assertRaises(sqlite3.OperationalError):
                    connection.execute("DELETE FROM sentinel")
            finally:
                connection.close()
            self.assertEqual(path.read_bytes(), before)
            missing = Path(temporary) / "missing.sqlite"
            with self.assertRaises(sqlite3.OperationalError):
                connect(missing, read_only=True)
            self.assertFalse(missing.exists())

    def test_read_only_connection_supports_stored_queries(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "reports.sqlite"
            writer = connect(path)
            r = source()
            try:
                import_run(writer, run_id="demo", patients=[patient()], reports=[r],
                           predictions=[prediction(r)], medication_changes=[])
                save_analysis(writer, "demo", analysis([r]))
            finally:
                writer.close()
            reader = connect(path, read_only=True)
            try:
                self.assertEqual(weekly_counts(reader, "demo")[0]["reported_vomiting_count"], 3)
                self.assertEqual(load_run(reader, "demo")["reports"], [r])
                self.assertEqual(after_medication_change(reader, "demo"), [])
                self.assertEqual(review_queue(reader, "demo"), [])
                with self.assertRaises(sqlite3.OperationalError):
                    reader.execute("DELETE FROM runs")
            finally:
                reader.close()

    def test_identical_reimport_is_idempotent_and_loaded_records_are_exact(self):
        reports = [source()]
        predictions = [prediction(reports[0])]
        self.assertTrue(self.ingest(reports, predictions, metadata={"source": "test"}))
        self.assertFalse(self.ingest(reports, predictions, metadata={"source": "test"}))
        loaded = load_run(self.db, "demo")
        self.assertEqual(loaded["reports"], reports)
        self.assertEqual(loaded["predictions"], predictions)
        self.assertEqual(loaded["metadata"], {"source": "test"})
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 1)
        self.assertEqual(self.db.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_changed_run_and_report_ids_are_rejected_without_overwriting(self):
        self.ingest()
        changed = source(count=4)
        with self.assertRaisesRegex(ValueError, "existing run_id"):
            self.ingest([changed])
        with self.assertRaisesRegex(ValueError, "existing report_id"):
            self.ingest([changed], run_id="different-run")
        self.assertEqual(load_run(self.db, "demo")["reports"][0]["questionnaire_answers"][0]["count"], 3)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)

    def test_conflict_rolls_back_other_new_sources_in_the_batch(self):
        self.ingest()
        new_patient = patient(patient_id="NEW", display_name="Another fictional patient")
        new = source("NEW-REPORT", patient_id="NEW")
        changed = source(count=5)
        with self.assertRaises(ValueError):
            self.ingest([new, changed], patients=[patient(), new_patient], run_id="failed")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM patients").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM reports").fetchone()[0], 1)

    def test_stale_source_hash_and_failed_observations_are_rejected(self):
        r = source()
        wrong = prediction(r)
        wrong["metadata"]["source_sha256"] = "stale"
        with self.assertRaises(ValueError):
            self.ingest([r], [wrong])
        failed = prediction(r)
        failed.update(status="error", error="failed", error_code="normalization_error")
        with self.assertRaisesRegex(ValueError, "failed report"):
            self.ingest([r], [failed])
        failed["observations"] = []
        self.ingest([r], [failed])
        self.assertEqual(load_run(self.db, "demo")["predictions"][0]["status"], "error")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 0)

    def test_stale_evidence_is_rejected(self):
        r = source()
        wrong = prediction(r)
        wrong["observations"][0]["evidence"][0]["value"] = "invented"
        with self.assertRaisesRegex(ValueError, "evidence"):
            self.ingest([r], [wrong])

    def test_replacement_history_is_preserved_and_effective_query_omits_old(self):
        first = source(count=3)
        replacement = source("R2", count=2, reported_at="2026-07-04T21:00:00-05:00", supersedes_report_id="R1")
        change = {"change_id": "M1", "patient_id": "P", "medication": "Fictional A",
                  "changed_at": "2026-07-03T20:00:00-05:00", "change_type": "start"}
        self.ingest([replacement, first], changes=[change])
        derived = analysis([replacement, first], first_count=2, effective=["R2"])
        derived["corrections"] = [{"report_id": "R2", "target_report_id": "R1", "status": "applied", "reason": None}]
        save_analysis(self.db, "demo", derived)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 2)
        self.assertEqual([r["report_id"] for r in after_medication_change(self.db, "demo")], ["R2"])
        self.assertEqual(weekly_counts(self.db, "demo")[0]["reported_vomiting_count"], 2)

    def test_missing_days_are_not_zeros_and_explicit_zero_is_counted(self):
        r = source(count=0)
        self.ingest([r])
        self.assertTrue(save_analysis(self.db, "demo", analysis([r], first_count=0)))
        self.assertFalse(save_analysis(self.db, "demo", analysis([r], first_count=0)))
        week = weekly_counts(self.db, "demo")[0]
        self.assertEqual(week["reported_vomiting_count"], 0)
        self.assertEqual((week["followup_days"], week["count_covered_days"], week["missing_count_days"]), (2, 1, 1))
        self.assertEqual(week["count_coverage"], 0.5)
        self.assertEqual(week["partial_count_days"], 1)
        self.assertIsNone(daily_records(self.db, "demo")[1]["vomiting_count"])
        save_analysis(self.db, "demo", analysis([r], first_count=None))
        self.assertIsNone(weekly_counts(self.db, "demo")[0]["reported_vomiting_count"])

    def test_analysis_requires_complete_followup_and_invalid_replace_rolls_back(self):
        r = source()
        self.ingest([r])
        original = analysis([r])
        save_analysis(self.db, "demo", original)
        short = copy.deepcopy(original)
        short["daily"].pop()
        with self.assertRaisesRegex(ValueError, "every registered"):
            save_analysis(self.db, "demo", short)
        invalid = copy.deepcopy(original)
        invalid["daily"][0]["count_status"] = "review"
        with self.assertRaisesRegex(ValueError, "Only usable"):
            save_analysis(self.db, "demo", invalid)
        self.assertEqual(daily_records(self.db, "demo"), original["daily"])

    def test_runs_are_explicit_and_do_not_silently_select_latest(self):
        r = source()
        self.ingest([r], run_id="first")
        self.ingest([r], run_id="second", metadata={"version": "new"})
        save_analysis(self.db, "first", analysis([r], first_count=3))
        save_analysis(self.db, "second", analysis([r], first_count=None))
        self.assertEqual(weekly_counts(self.db, "first")[0]["reported_vomiting_count"], 3)
        self.assertIsNone(weekly_counts(self.db, "second")[0]["reported_vomiting_count"])
        with self.assertRaisesRegex(ValueError, "Unknown run"):
            load_run(self.db, "absent")

    def test_medication_order_uses_offsets_and_date_only_is_indeterminate(self):
        exact_text = "I vomited today at 15:25."
        exact = source("EXACT", text=exact_text, questionnaire_answers=[])
        same_day = source("DAY", count=2)
        earlier_text = "I vomited today at 14:20."
        earlier = source("BEFORE", text=earlier_text, questionnaire_answers=[])
        equal_text = "I vomited today at 15:00."
        equal = source("EQUAL", text=equal_text, questionnaire_answers=[])
        predictions = [prediction(exact, [candidate(exact_text, clock_time="15:25")]), prediction(same_day),
                       prediction(earlier, [candidate(earlier_text, clock_time="14:20")]),
                       prediction(equal, [candidate(equal_text, clock_time="15:00")])]
        changes = [{"change_id": "M1", "patient_id": "P", "medication": "Fictional A",
                    "changed_at": "2026-07-04T22:00:00+02:00", "change_type": "dose_change"}]
        reports = [exact, same_day, earlier, equal]
        self.ingest(reports, predictions, changes=changes)
        save_analysis(self.db, "demo", analysis(reports, first_count=None))
        result = {r["report_id"]: r["timing_status"] for r in after_medication_change(self.db, "demo")}
        self.assertEqual(result, {"EXACT": "after", "DAY": "indeterminate", "EQUAL": "at_change_time"})

    def test_review_queue_preserves_unknown_date_and_reason(self):
        r = source()
        self.ingest([r])
        derived = analysis([r])
        item = {"patient_id": "P", "report_id": "R1", "observation_id": "R1-O1", "event_date": None,
                "field": "event_date", "reason": "date_unknown"}
        derived["review"] = [item]
        save_analysis(self.db, "demo", derived)
        self.assertEqual(review_queue(self.db, "demo"), [item])

    def test_ambiguous_clock_is_not_assumed_after_change(self):
        from src.store import _bounds
        observation = {"event_date": "2026-11-01", "event_time": "01:30"}
        lower, upper, precision = _bounds(observation, "America/Chicago")
        self.assertEqual(precision, "ambiguous_local_time")
        self.assertEqual(lower, "2026-11-01T06:30:00.000000Z")
        self.assertEqual(upper, "2026-11-01T07:30:00.000000Z")


if __name__ == "__main__":
    unittest.main()
