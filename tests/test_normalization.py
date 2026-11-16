"""Boundary tests for deterministic normalization, independent of model output."""

import copy
import unittest

from src.normalization import NormalizationError, normalize_report


def report(text, answers=None, **changes):
    value = {
        "report_id": "TEST-REPORT",
        "patient_id": "TEST-PATIENT",
        "reported_at": "2026-07-04T20:00:00-05:00",
        "patient_timezone": "America/Chicago",
        "text": text,
        "questionnaire_answers": answers or [],
        "supersedes_report_id": None,
    }
    value.update(changes)
    return value


def candidate(quote, **changes):
    value = {
        "symptom": "vomiting",
        "assertion": "present",
        "count": 1,
        "count_scope": "event",
        "severity_value": None,
        "severity_scale_max": None,
        "severity_context": None,
        "time_text": "today",
        "day_reference": "today",
        "explicit_date": None,
        "clock_time": None,
        "quote": quote,
        "medication_relation": None,
    }
    value.update(changes)
    return value


def nausea(quote, **changes):
    value = candidate(quote, symptom="nausea", count=None, count_scope=None)
    value.update(changes)
    return value


def answer(symptom="vomiting", count=None, severity=None):
    return {"symptom": symptom, "event_date": "2026-07-04", "count": count, "severity": severity}


def issues(observation):
    return {(issue["field"], issue["code"]) for issue in observation["issues"]}


class NormalizationTests(unittest.TestCase):
    def test_unknown_count_and_explicit_absence_are_different(self):
        unknown = "I vomited today but cannot recall how many times."
        missing = normalize_report(report(unknown), [candidate(unknown, count=None, count_scope="day_to_date")])[0]
        absent = "No vomiting at all today."
        zero = normalize_report(report(absent), [candidate(absent, assertion="absent", count=None, count_scope="day_to_date")])[0]
        self.assertIsNone(missing["count"])
        self.assertIn(("count", "count_unknown"), issues(missing))
        self.assertEqual(zero["count"], 0)
        self.assertEqual(zero["assertion"], "absent")
        self.assertEqual(zero["issues"], [])

    def test_hypothetical_does_not_create_an_observed_count(self):
        text = "I worry I might vomit tonight."
        result = normalize_report(report(text), [candidate(text, assertion="hypothetical", count=None, count_scope=None, time_text="tonight")])[0]
        self.assertEqual(result["assertion"], "hypothetical")
        self.assertIsNone(result["count"])
        self.assertEqual(result["issues"], [])

    def test_report_timezone_sets_relative_day_across_utc_boundary(self):
        text = "I vomited once yesterday."
        source = report(text, reported_at="2026-07-05T01:00:00+00:00")
        result = normalize_report(source, [candidate(text, day_reference="yesterday", time_text="yesterday")])[0]
        self.assertEqual(result["event_date"], "2026-07-03")
        self.assertEqual(result["date_basis"], "relative_text")
        self.assertIsNone(result["event_time"])

    def test_completed_day_total_is_preserved(self):
        text = "I vomited twice in total yesterday."
        result = normalize_report(report(text), [candidate(text, count=2, count_scope="day_total", day_reference="yesterday", time_text="yesterday")])[0]
        self.assertEqual((result["event_date"], result["count"], result["count_scope"]), ("2026-07-03", 2, "day_total"))

    def test_today_cannot_be_a_completed_day_total(self):
        text = "I vomited twice today."
        with self.assertRaises(NormalizationError):
            normalize_report(report(text), [candidate(text, count=2, count_scope="day_total")])

    def test_future_actual_date_is_rejected(self):
        text = "I vomited once on 2026-07-05."
        with self.assertRaises(NormalizationError):
            normalize_report(report(text), [candidate(text, day_reference="explicit", explicit_date="2026-07-05", time_text="2026-07-05")])

    def test_future_actual_clock_time_is_rejected(self):
        text = "I vomited today at 23:10."
        with self.assertRaises(NormalizationError):
            normalize_report(report(text), [candidate(text, clock_time="23:10", time_text="today at 23:10")])

    def test_undated_window_is_not_attached_to_submission_day(self):
        text = "I vomited once after breakfast."
        result = normalize_report(report(text), [candidate(text, count_scope="window", day_reference="unknown", time_text="after breakfast")])[0]
        self.assertIsNone(result["event_date"])
        self.assertIsNone(result["event_time"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(issues(result), {("event_date", "date_unknown")})

    def test_multiday_count_is_not_split_or_allocated_to_today(self):
        text = "I vomited four times over the last three days."
        result = normalize_report(report(text), [candidate(text, count=4, count_scope="window", day_reference="multiple_days", time_text="over the last three days")])[0]
        self.assertEqual(result["count"], 4)
        self.assertIsNone(result["event_date"])
        self.assertEqual(issues(result), {("event_date", "unsupported_time_range")})

    def test_wrong_severity_scale_does_not_remove_count_or_date(self):
        text = "I vomited twice in total today; my worst vomiting today was 7 out of 10."
        result = normalize_report(report(text), [candidate(text, count=2, count_scope="day_to_date", severity_value=7, severity_scale_max=10, severity_context="worst_today_so_far")])[0]
        self.assertEqual((result["count"], result["event_date"]), (2, "2026-07-04"))
        self.assertIsNone(result["severity"])
        self.assertEqual(issues(result), {("severity", "unsupported_scale")})

    def test_current_severity_cannot_become_worst_daily_severity(self):
        text = "My nausea is currently 3 out of 5 today."
        result = normalize_report(report(text), [nausea(text, severity_value=3, severity_scale_max=5, severity_context="current")])[0]
        self.assertIsNone(result["severity"])
        self.assertEqual(issues(result), {("severity", "unsupported_severity_context")})

    def test_unknown_score_context_is_preserved_as_issue(self):
        text = "Nausea was 3 out of 5 today."
        result = normalize_report(report(text), [nausea(text, severity_value=3, severity_scale_max=5, severity_context="unknown")])[0]
        self.assertIsNone(result["severity"])
        self.assertEqual(issues(result), {("severity", "severity_context_unknown")})

    def test_historical_score_is_not_today_score(self):
        text = "Nausea was 3 out of 5 at worst yesterday."
        result = normalize_report(report(text), [nausea(text, day_reference="yesterday", time_text="yesterday", severity_value=3, severity_scale_max=5, severity_context="worst_today_so_far")])[0]
        self.assertIsNone(result["severity"])
        self.assertEqual(issues(result), {("severity", "unsupported_severity_context")})

    def test_eligible_severity_conflict_affects_only_severity(self):
        text = "My nausea at its worst so far today was 2 out of 5."
        source = report(text, [answer("nausea", severity=4)])
        result = normalize_report(source, [nausea(text, severity_value=2, severity_scale_max=5, severity_context="worst_today_so_far")])[0]
        self.assertEqual(result["assertion"], "present")
        self.assertEqual(result["event_date"], "2026-07-04")
        self.assertIsNone(result["severity"])
        self.assertEqual(issues(result), {("severity", "conflicting_sources")})
        self.assertEqual(len(result["evidence"]), 4)

    def test_zero_positive_conflict_affects_presence_and_count(self):
        text = "I vomited twice in total so far today."
        source = report(text, [answer(count=0)])
        result = normalize_report(source, [candidate(text, count=2, count_scope="day_to_date")])[0]
        self.assertEqual(result["assertion"], "uncertain")
        self.assertIsNone(result["count"])
        self.assertEqual(result["count_scope"], "day_to_date")
        self.assertEqual(issues(result), {("assertion", "conflicting_sources"), ("count", "conflicting_sources")})
        self.assertEqual(result["evidence"][-1], {"path": "questionnaire_answers.0.count", "value": 0})

    def test_two_positive_counts_conflict_only_on_count(self):
        text = "I vomited twice in total so far today."
        result = normalize_report(report(text, [answer(count=4)]), [candidate(text, count=2, count_scope="day_to_date")])[0]
        self.assertEqual(result["assertion"], "present")
        self.assertIsNone(result["count"])
        self.assertEqual(issues(result), {("count", "conflicting_sources")})

    def test_text_daily_claims_are_reconciled_without_questionnaire(self):
        first = "I vomited twice in total so far today."
        second = "My total today is three vomiting episodes."
        result = normalize_report(report(first + " " + second), [
            candidate(first, count=2, count_scope="day_to_date"),
            candidate(second, count=3, count_scope="day_to_date"),
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["assertion"], "present")
        self.assertIsNone(result[0]["count"])
        self.assertEqual(issues(result[0]), {("count", "conflicting_sources")})
        self.assertEqual(len(result[0]["evidence"]), 2)

    def test_daily_restatement_is_not_an_additional_count(self):
        first = "I vomited twice in total so far today."
        second = "Two vomiting episodes in total today."
        result = normalize_report(report(first + " " + second), [
            candidate(first, count=2, count_scope="day_to_date"),
            candidate(second, count=2, count_scope="day_to_date"),
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["count"], 2)
        self.assertEqual(result[0]["issues"], [])
        self.assertEqual(len(result[0]["evidence"]), 2)

    def test_earlier_daily_snapshot_is_not_forced_to_conflict_with_current_total(self):
        earlier = "I had vomited twice in total by noon today."
        current = "I have now vomited three times in total so far today."
        result = normalize_report(report(earlier + " " + current, [answer(count=3)]), [
            candidate(earlier, count=2, count_scope="day_to_date", time_text="by noon today"),
            candidate(current, count=3, count_scope="day_to_date", time_text="so far today"),
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual(sorted(value["count"] for value in result), [2, 3])
        self.assertTrue(all(not value["issues"] for value in result))
        self.assertEqual(sorted(len(value["evidence"]) for value in result), [1, 4])

    def test_questionnaire_can_fill_unknown_count(self):
        text = "I vomited today but cannot remember how many times."
        result = normalize_report(report(text, [answer(count=3)]), [candidate(text, count=None, count_scope="day_to_date")])[0]
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["issues"], [])
        self.assertEqual(len(result["evidence"]), 4)

    def test_day_start_through_submission_reconciles_conflicting_counts(self):
        for timing in (
            "from midnight today through this submission",
            "from midnight today until now",
            "from midnight today to now",
            "FROM MIDNIGHT TODAY THROUGH THIS SUBMISSION",
        ):
            with self.subTest(timing=timing):
                text = f"I count five vomiting episodes {timing}."
                source = report(text, [answer(count=3)])
                values = [candidate(text, count=5, count_scope="day_to_date", time_text=timing)]
                original = copy.deepcopy((source, values))
                result = normalize_report(source, values)
                self.assertEqual(len(result), 1)
                observation = result[0]
                self.assertEqual(observation["assertion"], "present")
                self.assertIsNone(observation["count"])
                self.assertEqual(observation["count_scope"], "day_to_date")
                self.assertEqual(observation["time_text"], timing)
                self.assertEqual(issues(observation), {("count", "conflicting_sources")})
                self.assertEqual(observation["evidence"], [
                    {"path": "text", "value": text},
                    {"path": "questionnaire_answers.0.symptom", "value": "vomiting"},
                    {"path": "questionnaire_answers.0.event_date", "value": "2026-07-04"},
                    {"path": "questionnaire_answers.0.count", "value": 3},
                ])
                self.assertEqual((source, values), original)

    def test_day_start_range_preserves_agreement_and_zero_positive_conflict(self):
        text = "I count five vomiting episodes from midnight today through this submission."
        for form_count, expected_count, assertion, expected_issues in (
            (5, 5, "present", set()),
            (0, None, "uncertain", {("count", "conflicting_sources"), ("assertion", "conflicting_sources")}),
        ):
            with self.subTest(form_count=form_count):
                result = normalize_report(report(text, [answer(count=form_count)]), [
                    candidate(text, count=5, count_scope="day_to_date"),
                ])
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["count"], expected_count)
                self.assertEqual(result[0]["assertion"], assertion)
                self.assertEqual(issues(result[0]), expected_issues)

    def test_day_start_with_earlier_endpoint_remains_separate(self):
        for timing in (
            "by noon today", "as of 10 today", "at midnight today",
            "from midnight today through noon", "from midnight today until 10:00",
            "from midnight today to breakfast",
        ):
            with self.subTest(timing=timing):
                text = f"I had two vomiting episodes {timing}."
                result = normalize_report(report(text, [answer(count=3)]), [
                    candidate(text, count=2, count_scope="day_to_date", time_text=timing),
                ])
                self.assertEqual(len(result), 2)
                self.assertEqual(sorted(o["count"] for o in result), [2, 3])
                self.assertTrue(all(not o["issues"] for o in result))

    def test_current_day_range_does_not_override_other_snapshot_qualifiers(self):
        text = ("By noon today I had two vomiting episodes. "
                "I am now counting from midnight today through this submission.")
        result = normalize_report(report(text, [answer(count=3)]), [
            candidate(text, count=2, count_scope="day_to_date", time_text="By noon today"),
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual(sorted(o["count"] for o in result), [2, 3])
        self.assertTrue(all(not o["issues"] for o in result))

    def test_current_day_range_does_not_rewrite_extracted_window_scope(self):
        text = "I count five vomiting episodes from midnight today through this submission."
        result = normalize_report(report(text, [answer(count=3)]), [
            candidate(text, count=5, count_scope="window"),
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual({(o["count"], o["count_scope"]) for o in result}, {(3, "day_to_date"), (5, "window")})
        self.assertTrue(all(not o["issues"] for o in result))

    def test_day_start_range_uses_local_date_for_questionnaire_reconciliation(self):
        text = "I count five vomiting episodes from midnight today through this submission."
        form = {**answer(count=3), "event_date": "2026-11-13"}
        source = report(text, [form], reported_at="2026-11-12T23:20:00Z", patient_timezone="Asia/Tokyo")
        result = normalize_report(source, [candidate(text, count=5, count_scope="day_to_date")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["event_date"], "2026-11-13")
        self.assertIsNone(result[0]["count"])
        self.assertEqual(issues(result[0]), {("count", "conflicting_sources")})

    def test_day_start_range_reconciles_text_claims_without_questionnaire(self):
        first = "I count five vomiting episodes from midnight today through this submission."
        second = "I have vomited three times in total so far today."
        result = normalize_report(report(first + " " + second), [
            candidate(first, count=5, count_scope="day_to_date"),
            candidate(second, count=3, count_scope="day_to_date"),
        ])
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["count"])
        self.assertEqual(issues(result[0]), {("count", "conflicting_sources")})
        self.assertEqual(len(result[0]["evidence"]), 2)

    def test_valid_form_severity_does_not_hide_rejected_text_score(self):
        text = "My nausea at its worst today was 6 out of 10."
        result = normalize_report(report(text, [answer("nausea", severity=3)]), [nausea(text, severity_value=6, severity_scale_max=10, severity_context="worst_today_so_far")])[0]
        self.assertEqual(result["severity"], 3)
        self.assertEqual(issues(result), {("severity", "unsupported_scale")})
        self.assertEqual(len(result["evidence"]), 4)

    def test_questionnaire_only_supports_multiple_symptoms(self):
        result = normalize_report(report("", [answer(count=0), answer("nausea", severity=2)]), [])
        self.assertEqual(len(result), 2)
        self.assertEqual([value["symptom"] for value in result], ["nausea", "vomiting"])
        self.assertEqual([value["date_basis"] for value in result], ["questionnaire", "questionnaire"])
        self.assertEqual(result[1]["count"], 0)
        self.assertEqual(result[0]["evidence"][-1]["path"], "questionnaire_answers.1.severity")

    def test_empty_questionnaire_answer_is_not_explicit_absence(self):
        result = normalize_report(report("", [answer()]), [])
        self.assertEqual(result, [])

    def test_event_and_daily_questionnaire_remain_separate(self):
        text = "I vomited once today at 14:20."
        result = normalize_report(report(text, [answer(count=3)]), [candidate(text, time_text="today at 14:20", clock_time="14:20")])
        self.assertEqual(len(result), 2)
        self.assertEqual([value["count"] for value in result], [1, 3])
        self.assertEqual([value["count_scope"] for value in result], ["event", "day_to_date"])
        self.assertTrue(all(not value["issues"] for value in result))

    def test_morning_nausea_and_daily_questionnaire_remain_separate(self):
        text = "I felt nauseous this morning."
        result = normalize_report(report(text, [answer("nausea", severity=3)]), [nausea(text, time_text="this morning")])
        self.assertEqual(len(result), 2)
        self.assertEqual(sorted(value["severity"] or 0 for value in result), [0, 3])

    def test_invented_provenance_is_rejected(self):
        text = "I vomited once today."
        invalid = [
            candidate("I vomited twice today."),
            candidate(text, time_text="this morning"),
            candidate(text, clock_time="14:20"),
            candidate(text, medication_relation={"medication": "Medication Z", "relation": "after_taking"}),
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(NormalizationError):
                normalize_report(report(text), [value])

    def test_invented_relative_and_explicit_dates_are_rejected(self):
        text = "I vomited once after lunch."
        invalid = [
            candidate(text, time_text="after lunch"),
            candidate(text, day_reference="yesterday", time_text="after lunch"),
            candidate(text, day_reference="explicit", explicit_date="2026-07-03", time_text="after lunch"),
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(NormalizationError):
                normalize_report(report(text), [value])

    def test_english_calendar_date_and_twelve_hour_time(self):
        text = "I vomited once on July 3, 2026 at 2:20 pm."
        result = normalize_report(report(text), [candidate(text, day_reference="explicit", explicit_date="2026-07-03", clock_time="14:20", time_text="July 3, 2026 at 2:20 pm")])[0]
        self.assertEqual((result["event_date"], result["event_time"], result["date_basis"]), ("2026-07-03", "14:20", "explicit_text"))

    def test_midnight_and_noon_require_correct_meridiem(self):
        for marker, expected, incorrect in (("am", "00:30", "12:30"), ("pm", "12:30", "00:30")):
            text = f"I vomited today at 12:30 {marker}."
            with self.subTest(marker=marker):
                result = normalize_report(report(text), [candidate(text, clock_time=expected)])[0]
                self.assertEqual(result["event_time"], expected)
                with self.assertRaises(NormalizationError):
                    normalize_report(report(text), [candidate(text, clock_time=incorrect)])

    def test_approximate_numeric_clock_is_not_an_exact_event_time(self):
        for timing in ("around 14:20", "approximately 14:20", "14:20 or so", "14:20-ish"):
            text = f"I vomited today at {timing}."
            with self.subTest(timing=timing):
                with self.assertRaises(NormalizationError):
                    normalize_report(report(text), [candidate(text, clock_time="14:20")])
                result = normalize_report(report(text), [candidate(text, time_text=f"today at {timing}")])[0]
                self.assertIsNone(result["event_time"])
                self.assertEqual(result["time_text"], f"today at {timing}")

    def test_medication_relation_keeps_label_without_inventing_time(self):
        text = "I felt nauseous after taking Medication Z this morning."
        relation = {"medication": "Medication Z", "relation": "after_taking"}
        result = normalize_report(report(text), [nausea(text, time_text="this morning", medication_relation=relation)])[0]
        self.assertEqual(result["medication_relation"], relation)
        self.assertIsNone(result["event_time"])

    def test_identifiers_are_independent_of_candidate_array_order(self):
        first = "I felt nauseous today."
        second = "I vomited once yesterday."
        source = report(first + " " + second)
        candidates = [nausea(first), candidate(second, day_reference="yesterday", time_text="yesterday")]
        original = copy.deepcopy((source, candidates))
        forward = normalize_report(source, candidates)
        backward = normalize_report(source, list(reversed(candidates)))
        self.assertEqual(forward, backward)
        self.assertEqual([value["observation_id"] for value in forward], ["TEST-REPORT-O1", "TEST-REPORT-O2"])
        self.assertEqual((source, candidates), original)

    def test_exact_duplicate_candidate_does_not_duplicate_source_claim(self):
        text = "I vomited once today."
        value = candidate(text)
        self.assertEqual(len(normalize_report(report(text), [value, copy.deepcopy(value)])), 1)


if __name__ == "__main__":
    unittest.main()
