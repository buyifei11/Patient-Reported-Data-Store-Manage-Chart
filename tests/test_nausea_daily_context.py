"""Daily nausea grouping must preserve distinct contexts and unresolved evidence."""

import copy
from pathlib import Path
import unittest

from src.normalization import normalize_report
from src.pipeline import read_jsonl
from tests.test_normalization import answer, issues, nausea, report


ROOT = Path(__file__).resolve().parents[1]
DAILY = "My worst nausea so far today was 3 out of 5."


def daily_rating(quote=DAILY, value=3):
    return nausea(quote, severity_value=value, severity_scale_max=5,
                  severity_context="worst_today_so_far", time_text="so far today")


class NauseaDailyContextTests(unittest.TestCase):
    def test_explicit_cumulative_occurrence_and_score_combine_without_mutation(self):
        for timing in ("today up to now", "today up until now", "today until now", "today through now"):
            first = f"I have felt nauseous {timing}."
            source = report(first + " " + DAILY)
            candidates = [nausea(first, time_text=timing), daily_rating()]
            original = copy.deepcopy((source, candidates))
            with self.subTest(timing=timing):
                result = normalize_report(source, candidates)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["severity"], 3)
                self.assertEqual(result[0]["issues"], [])
                self.assertEqual({e["value"] for e in result[0]["evidence"]}, {first, DAILY})
                self.assertEqual(normalize_report(source, candidates[::-1]), result)
                self.assertEqual((source, candidates), original)

    def test_cumulative_occurrence_can_reconcile_with_daily_questionnaire(self):
        text = "I have felt nauseous today up to now."
        result = normalize_report(report(text, [answer("nausea", severity=3)]),
                                  [nausea(text, time_text="today up to now")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["severity"], 3)
        self.assertIn({"path": "text", "value": text}, result[0]["evidence"])
        self.assertTrue(any(e["path"].endswith(".severity") for e in result[0]["evidence"]))

    def test_current_score_is_separate_and_original_value_survives(self):
        first = "My nausea right now today is 1 out of 5."
        candidates = [nausea(first, time_text="right now today", severity_value=1,
                             severity_scale_max=5, severity_context="current"), daily_rating()]
        original = copy.deepcopy(candidates)
        result = normalize_report(report(first + " " + DAILY), candidates)
        self.assertEqual(len(result), 2)
        current = next(o for o in result if o["time_text"] == "right now today")
        self.assertIsNone(current["severity"])
        self.assertIn(("severity", "unsupported_severity_context"), issues(current))
        self.assertEqual(current["evidence"], [{"path": "text", "value": first}])
        self.assertEqual([o["severity"] for o in result if o is not current], [3])
        self.assertEqual(candidates, original)

    def test_current_morning_and_residual_cutoffs_remain_separate(self):
        for timing in ("right now today", "currently today", "this morning today",
                       "today up to now this morning", "today up to now after breakfast",
                       "today up to now since 09:00", "today up to now as of 09:00"):
            first = f"I felt nauseous {timing}."
            with self.subTest(timing=timing):
                result = normalize_report(report(first + " " + DAILY),
                                          [nausea(first, time_text=timing), daily_rating()])
                self.assertEqual(len(result), 2)
                self.assertEqual(sorted(o["severity"] or 0 for o in result), [0, 3])

    def test_different_day_clock_and_medication_remain_separate(self):
        cases = [
            ("I felt nauseous yesterday.", dict(time_text="yesterday", day_reference="yesterday")),
            ("I felt nauseous today at 14:20.", dict(time_text="today at 14:20", clock_time="14:20")),
            ("I felt nauseous today up to now after taking Medication A.",
             dict(time_text="today up to now", medication_relation={"medication": "Medication A", "relation": "after_taking"})),
        ]
        for first, changes in cases:
            with self.subTest(first=first):
                result = normalize_report(report(first + " " + DAILY), [nausea(first, **changes), daily_rating()])
                self.assertEqual(len(result), 2)
                self.assertEqual(sorted(o["severity"] or 0 for o in result), [0, 3])

    def test_conflicting_daily_ratings_stay_unresolved_with_all_evidence(self):
        first = "I have felt nauseous today up to now."
        other = "My worst nausea so far today was 5 out of 5."
        candidates = [nausea(first, time_text="today up to now"), daily_rating(), daily_rating(other, 5)]
        original = copy.deepcopy(candidates)
        result = normalize_report(report(" ".join((first, DAILY, other))), candidates)
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["severity"])
        self.assertIn(("severity", "conflicting_sources"), issues(result[0]))
        self.assertEqual({e["value"] for e in result[0]["evidence"]}, {first, DAILY, other})
        self.assertEqual(candidates, original)

    def test_conflicting_assertion_is_not_a_supported_daily_score(self):
        first = "No nausea today up to now."
        result = normalize_report(report(first + " " + DAILY),
                                  [nausea(first, assertion="absent", time_text="today up to now"), daily_rating()])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["assertion"], "uncertain")
        self.assertIsNone(result[0]["severity"])
        self.assertEqual(issues(result[0]), {("assertion", "conflicting_sources"), ("severity", "conflicting_sources")})
        self.assertEqual(len(result[0]["evidence"]), 2)

    def test_saved_duplicate_cases_keep_raw_candidates_and_all_nausea_evidence(self):
        sources = {r["report_id"]: r for r in read_jsonl(ROOT / "data/text_validation/reports.jsonl")}
        for saved in read_jsonl(ROOT / "results/text-validation-compact/predictions.jsonl"):
            if saved["report_id"] not in {"TV007", "TV009"}:
                continue
            original = copy.deepcopy(saved)
            with self.subTest(report_id=saved["report_id"]):
                result = normalize_report(sources[saved["report_id"]], saved["candidates"])
                self.assertEqual(len(result), 2)
                daily = [o for o in result if o["symptom"] == "nausea"]
                self.assertEqual(len(daily), 1)
                self.assertEqual(daily[0]["severity"], 5 if saved["report_id"] == "TV007" else 3)
                self.assertEqual({e["value"] for e in daily[0]["evidence"]},
                                 {c["quote"] for c in saved["candidates"] if c["symptom"] == "nausea"})
                self.assertEqual(saved, original)
