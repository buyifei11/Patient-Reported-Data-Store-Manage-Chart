"""Review explanations preserve evidence attribution and field-level effects."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.aggregation import aggregate
from src.dashboard_review import review_details


ROOT = Path(__file__).resolve().parents[1]


class DashboardReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        patients = json.loads((ROOT / "data/longitudinal/patients.json").read_text())
        reports = [json.loads(line) for line in (ROOT / "data/longitudinal/reports.jsonl").read_text().splitlines()]
        predictions = [json.loads(line) for line in (ROOT / "results/longitudinal-demo/predictions.jsonl").read_text().splitlines()]
        cls.data = {"patients": patients, "reports": reports, "predictions": predictions,
                    **aggregate(patients, reports, predictions)}

    def test_severity_conflict_shows_both_values_without_discarding_valid_count(self):
        row = next(r for r in review_details(self.data) if r["report_id"] == "R002")
        self.assertEqual(row["detail"], "Nausea severity: text reports 2/5; questionnaire reports 3/5.")
        self.assertEqual(row["source_report_ids"], ["R002"])
        self.assertIn("nausea severity excluded", row["impact"])
        self.assertIn("vomiting count remains usable (0)", row["impact"])

    def test_cumulative_conflict_links_both_updates_and_preserves_inputs(self):
        data = deepcopy(self.data)
        before = deepcopy(data)
        row = next(r for r in review_details(data) if r["reason"] == "decreasing_or_conflicting_cumulative_count")
        self.assertEqual(row["source_report_ids"], ["L-P001-10-AM", "L-P001-10"])
        self.assertIn("4 (submitted at 10:00 in L-P001-10-AM)", row["detail"])
        self.assertIn("1 (submitted at 20:30 in L-P001-10)", row["detail"])
        self.assertIn("No correction was declared", row["detail"])
        self.assertEqual(row["impact"], "Daily vomiting count excluded pending review.")
        self.assertEqual(data, before)

    def test_negated_zero_remains_visible_in_a_decreasing_cumulative_conflict(self):
        data = deepcopy(self.data)
        prediction = next(r for r in data["predictions"] if r["report_id"] == "L-P001-10")
        observation = next(o for o in prediction["observations"] if o["symptom"] == "vomiting")
        observation.update(count=0, assertion="absent")
        row = next(r for r in review_details(data) if r["reason"] == "decreasing_or_conflicting_cumulative_count")
        self.assertIn("0 (submitted at 20:30 in L-P001-10)", row["detail"])

    def test_count_conflict_identifies_values_instead_of_using_unrelated_severity(self):
        rows = [r for r in review_details(self.data) if r["report_id"] == "R009"]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row["detail"], "Vomiting count: text reports 1; questionnaire reports 0.")
            self.assertEqual(row["impact"], "Daily vomiting count excluded pending review.")

    def test_candidate_for_another_quote_is_not_used_as_conflict_evidence(self):
        data = deepcopy(self.data)
        prediction = next(p for p in data["predictions"] if p["report_id"] == "R002")
        prediction["candidates"].insert(0, {"symptom": "nausea", "quote": "A different dated nausea claim.",
                                             "severity_value": 5, "severity_scale_max": 5})
        row = next(r for r in review_details(data) if r["report_id"] == "R002")
        self.assertIn("text reports 2/5", row["detail"])
        self.assertNotIn("5/5", row["detail"])

    def test_unknown_date_and_count_explain_the_actual_missing_information(self):
        rows = review_details(self.data)
        unknown_date = next(r for r in rows if r["report_id"] == "R007")
        self.assertIn("I vomited once after dinner.", unknown_date["detail"])
        self.assertEqual(unknown_date["impact"], "This observation is not assigned to a daily statistic.")
        hypothetical = next(r for r in rows if r["report_id"] == "R010")
        self.assertIn("Hypothetical symptom is excluded", hypothetical["impact"])
        unknown_count = next(r for r in rows if r["report_id"] == "R008" and r["reason"] == "count_unknown")
        self.assertIn("a few times", unknown_count["detail"])
        questionnaire = next(r for r in rows if r["report_id"] == "L-P003-14" and r["reason"] == "count_unknown")
        self.assertIn("questionnaire provides no numerical count", questionnaire["detail"])

    def test_issue_on_one_severity_source_does_not_claim_supported_daily_value_is_excluded(self):
        data = deepcopy(self.data)
        row = next(r for r in data["review"] if r["report_id"] == "R002")
        row["reason"] = "unsupported_severity_context"
        day = next(d for d in data["daily"] if d["patient_id"] == "P001" and d["event_date"] == "2026-11-03")
        day.update(nausea_status="usable", nausea_severity=3)
        explained = next(r for r in review_details(data) if r["report_id"] == "R002")
        self.assertEqual(explained["impact"], "Daily nausea severity remains usable (3/5) from supported evidence.")


if __name__ == "__main__":
    unittest.main()
