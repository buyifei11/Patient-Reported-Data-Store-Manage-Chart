"""Behavioral aggregation checks with controlled normalized source claims."""

import copy
import unittest

from src.aggregation import aggregate


def patient():
    return {"patient_id": "P", "display_name": "Synthetic patient", "patient_timezone": "America/Chicago",
            "followup_start": "2026-11-01", "followup_end": "2026-11-04"}


def report(report_id, day="2026-11-01", hour=20, target=None):
    return {"report_id": report_id, "patient_id": "P", "reported_at": f"{day}T{hour:02d}:00:00-06:00",
            "patient_timezone": "America/Chicago", "text": "Synthetic controlled claim.",
            "questionnaire_answers": [], "supersedes_report_id": target}


def observation(identifier="O1", count=2, scope="day_to_date", symptom="vomiting", day="2026-11-01",
                assertion="present", severity=None, issues=None, timing="so far today"):
    return {"observation_id": identifier, "symptom": symptom, "assertion": assertion,
            "count": count, "count_scope": scope, "severity": severity, "event_date": day,
            "event_time": None, "time_text": timing, "date_basis": "relative_text" if day else "unknown",
            "medication_relation": None, "evidence": [{"path": "text", "value": "Synthetic controlled claim."}],
            "issues": issues or []}


def nausea(identifier="N1", severity=4, **kwargs):
    return observation(identifier, count=None, scope=None, symptom="nausea", severity=severity, **kwargs)


def prediction(source, observations=None, status="ok"):
    return {"report_id": source["report_id"], "status": status, "observations": observations or [],
            "candidates": [], "error_code": None if status == "ok" else "normalization_error"}


def day(result, value="2026-11-01"):
    return next(row for row in result["daily"] if row["event_date"] == value)


class AggregationTests(unittest.TestCase):
    def test_missing_days_absence_and_hypothetical_are_not_interchangeable(self):
        absent, fear = report("A", "2026-11-02"), report("B", "2026-11-03")
        result = aggregate([patient()], [absent, fear], [
            prediction(absent, [observation(count=0, assertion="absent", day="2026-11-02")]),
            prediction(fear, [observation(count=None, scope=None, assertion="hypothetical", day="2026-11-03")]),
        ])
        self.assertEqual(len(result["daily"]), 4)
        self.assertIsNone(day(result)["vomiting_count"])
        self.assertEqual(day(result)["count_status"], "missing")
        self.assertEqual(day(result, "2026-11-02")["vomiting_count"], 0)
        self.assertEqual(day(result, "2026-11-02")["count_status"], "usable")
        self.assertIsNone(day(result, "2026-11-03")["vomiting_count"])
        self.assertEqual(day(result, "2026-11-03")["report_count"], 1)

    def test_cumulative_snapshots_and_partials_are_never_summed(self):
        morning, event, evening = report("A", hour=9), report("B", hour=12), report("C", hour=20)
        result = aggregate([patient()], [morning, event, evening], [
            prediction(morning, [observation(count=2)]),
            prediction(event, [observation(count=1, scope="event")]),
            prediction(evening, [observation(count=3)]),
        ])
        self.assertEqual(day(result)["vomiting_count"], 3)
        self.assertEqual(day(result)["count_basis"], "day_to_date")
        self.assertEqual(day(result)["source_report_ids"], ["A", "B", "C"])
        self.assertIn("unresolved_count_relationship", day(result)["review_reasons"])

    def test_standalone_windows_and_events_do_not_become_daily_totals(self):
        sources = [report("A", hour=9), report("B", hour=15)]
        result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=1, scope="event")]),
                                                 prediction(sources[1], [observation(count=2, scope="window")])])
        self.assertIsNone(day(result)["vomiting_count"])
        self.assertEqual(day(result)["count_status"], "review")
        self.assertEqual(len(result["review"]), 2)

    def test_decreasing_cumulative_count_requires_review(self):
        sources = [report("A", hour=9), report("B", hour=20)]
        result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=3)]),
                                                 prediction(sources[1], [observation(count=2)])])
        self.assertIsNone(day(result)["vomiting_count"])
        self.assertIn("decreasing_or_conflicting_cumulative_count", day(result)["review_reasons"])

    def test_unknown_latest_count_does_not_fall_back_to_older_number(self):
        sources = [report("A", hour=9), report("B", hour=20)]
        result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=2)]),
            prediction(sources[1], [observation(count=None, issues=[{"field": "count", "code": "count_unknown"}])])])
        self.assertIsNone(day(result)["vomiting_count"])
        self.assertIn("latest_daily_count_unresolved", day(result)["review_reasons"])

    def test_later_known_summary_can_resolve_earlier_unknown_quantity(self):
        sources = [report("A", hour=9), report("B", hour=20)]
        result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=None)]),
                                                 prediction(sources[1], [observation(count=3)])])
        self.assertEqual(day(result)["vomiting_count"], 3)

    def test_conflict_blocks_count_but_not_independent_severity(self):
        source = report("A")
        result = aggregate([patient()], [source], [prediction(source, [
            observation(count=None, issues=[{"field": "count", "code": "conflicting_sources"}]), nausea(),
        ])])
        self.assertIsNone(day(result)["vomiting_count"])
        self.assertEqual(day(result)["nausea_severity"], 4)
        self.assertEqual(day(result)["nausea_status"], "usable")

    def test_completed_total_replaces_partial_count_without_adding(self):
        sources = [report("A", hour=20), report("B", "2026-11-02", hour=9)]
        result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=2)]),
            prediction(sources[1], [observation(count=3, scope="day_total", timing="yesterday")])])
        self.assertEqual(day(result)["vomiting_count"], 3)
        self.assertEqual(day(result)["count_basis"], "day_total")

    def test_completed_total_below_prior_claim_or_conflicting_totals_require_review(self):
        for prior_scope, prior_count in (("day_to_date", 4), ("day_total", 4)):
            with self.subTest(prior_scope=prior_scope):
                sources = [report("A", "2026-11-02", hour=9), report("B", "2026-11-02", hour=20)]
                result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=prior_count, scope=prior_scope)]),
                    prediction(sources[1], [observation(count=3, scope="day_total")])])
                self.assertIsNone(day(result)["vomiting_count"])
                self.assertEqual(day(result)["count_status"], "review")

    def test_complete_correction_removes_old_count_and_preserves_other_symptom(self):
        earlier, original, corrected = report("A", hour=9), report("B", hour=20), report("C", hour=21, target="B")
        sources = [corrected, earlier, original]
        predictions = [prediction(earlier, [observation(count=2)]),
                       prediction(original, [observation(count=3), nausea()]),
                       prediction(corrected, [observation(count=2), nausea()])]
        original_inputs = copy.deepcopy((sources, predictions))
        result = aggregate([patient()], sources, predictions)
        self.assertEqual(result["effective_report_ids"], ["A", "C"])
        self.assertEqual(result["corrections"], [{"report_id": "C", "target_report_id": "B", "status": "applied", "reason": None}])
        self.assertEqual(day(result)["vomiting_count"], 2)
        self.assertEqual(day(result)["nausea_severity"], 4)
        self.assertEqual((sources, predictions), original_inputs)

    def test_incomplete_correction_leaves_original_effective(self):
        sources = [report("A", hour=20), report("B", hour=21, target="A")]
        result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=3), nausea()]),
                                                 prediction(sources[1], [observation(count=2)])])
        self.assertEqual(result["effective_report_ids"], ["A"])
        self.assertEqual(result["corrections"][0]["reason"], "incomplete_replacement")
        self.assertEqual(day(result)["vomiting_count"], 3)
        self.assertEqual(day(result)["nausea_severity"], 4)

    def test_replacement_cannot_silently_omit_a_previously_supplied_rating(self):
        sources = [report("A", hour=20), report("B", hour=21, target="A")]
        result = aggregate([patient()], sources, [prediction(sources[0], [nausea()]),
                                                 prediction(sources[1], [nausea(severity=None)])])
        self.assertEqual(result["effective_report_ids"], ["A"])
        self.assertEqual(result["corrections"][0]["reason"], "incomplete_replacement")

    def test_changed_date_in_replacement_requires_review_in_this_mvp(self):
        sources = [report("A"), report("B", "2026-11-02", target="A")]
        result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=2)]),
            prediction(sources[1], [observation(count=2, day="2026-11-02")])])
        self.assertEqual(result["effective_report_ids"], ["A"])
        self.assertEqual(result["corrections"][0]["reason"], "incomplete_replacement")
        self.assertEqual(day(result)["vomiting_count"], 2)
        self.assertIsNone(day(result, "2026-11-02")["vomiting_count"])

    def test_failed_replacement_does_not_deactivate_original_or_block_its_value(self):
        sources = [report("A", hour=20), report("B", hour=21, target="A")]
        result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=3)]),
                                                 prediction(sources[1], status="error")])
        self.assertEqual(result["effective_report_ids"], ["A"])
        self.assertEqual(result["corrections"][0]["reason"], "failed_replacement")
        self.assertEqual(day(result)["vomiting_count"], 3)

    def test_branching_replacements_are_both_rejected(self):
        sources = [report("A", hour=18), report("B", hour=20, target="A"), report("C", hour=21, target="A")]
        result = aggregate([patient()], sources, [prediction(source, [observation(count=count)])
                                                 for source, count in zip(sources, (3, 2, 1))])
        self.assertEqual(result["effective_report_ids"], ["A"])
        self.assertTrue(all(value["reason"] == "branching_correction" for value in result["corrections"]))
        self.assertEqual(day(result)["vomiting_count"], 3)

    def test_valid_correction_chain_is_order_independent(self):
        sources = [report("C", hour=21, target="B"), report("A", hour=18), report("B", hour=20, target="A")]
        result = aggregate([patient()], sources, [prediction(source, [observation(count=count)])
                                                 for source, count in zip(sources, (1, 3, 2))])
        self.assertEqual(result["effective_report_ids"], ["C"])
        self.assertEqual(day(result)["vomiting_count"], 1)

    def test_equal_timestamp_conflicting_daily_claims_do_not_use_array_order(self):
        source = report("A")
        values = [observation("O1", count=2), observation("O2", count=3)]
        first = aggregate([patient()], [source], [prediction(source, values)])
        second = aggregate([patient()], [source], [prediction(source, list(reversed(values)))])
        self.assertIsNone(day(first)["vomiting_count"])
        self.assertEqual(first, second)

    def test_earlier_cutoff_and_current_snapshot_in_same_report_are_ordered(self):
        source = report("A")
        result = aggregate([patient()], [source], [prediction(source, [
            observation("O1", count=3), observation("O2", count=1, timing="By 09:00 today"),
        ])])
        self.assertEqual(day(result)["vomiting_count"], 3)

    def test_unparsed_earlier_cutoff_is_not_silently_treated_as_current(self):
        for timing in ("as of 10am today", "until 10am today", "through 10am today",
                       "up to 10am today", "until 23:00 today", "through 99:00 today"):
            with self.subTest(timing=timing):
                sources = [report("A", hour=19), report("B", hour=20)]
                result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=3)]),
                    prediction(sources[1], [observation(count=4, timing=timing)])])
                self.assertIsNone(day(result)["vomiting_count"])
                self.assertIn("snapshot_endpoint_unresolved", day(result)["review_reasons"])

    def test_through_noon_cutoff_is_ordered_before_later_current_count(self):
        sources = [report("A", hour=18), report("B", hour=20)]
        result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=3)]),
            prediction(sources[1], [observation(count=4, timing="through noon today")])])
        self.assertIsNone(day(result)["vomiting_count"])
        self.assertIn("decreasing_or_conflicting_cumulative_count", day(result)["review_reasons"])

    def test_explicit_current_endpoint_remains_usable(self):
        for timing in ("since midnight today up to the time of this report", "from midnight today through now",
                       "from midnight today until this submission", "from midnight today to this message"):
            with self.subTest(timing=timing):
                source = report("A")
                result = aggregate([patient()], [source], [prediction(source, [observation(count=3, timing=timing)])])
                self.assertEqual(day(result)["vomiting_count"], 3)

    def test_unknown_positive_count_contradicts_later_daily_zero(self):
        for zero_scope in ("day_to_date", "day_total"):
            with self.subTest(zero_scope=zero_scope):
                sources = [report("A", hour=9), report("B", "2026-11-02" if zero_scope == "day_total" else "2026-11-01")]
                result = aggregate([patient()], sources, [
                    prediction(sources[0], [observation(count=None, issues=[{"field": "count", "code": "count_unknown"}])]),
                    prediction(sources[1], [observation(count=0, scope=zero_scope, assertion="absent")]),
                ])
                self.assertIsNone(day(result)["vomiting_count"])
                self.assertEqual(day(result)["count_status"], "review")
                self.assertIn("reported_occurrence_conflicts_with_zero", day(result)["review_reasons"])

    def test_known_occurrence_in_partial_claim_cannot_be_erased_by_daily_zero(self):
        for scope in ("event", "window"):
            for count in (None, 1):
                with self.subTest(scope=scope, count=count):
                    sources = [report("A", hour=9), report("B", hour=20)]
                    result = aggregate([patient()], sources, [
                        prediction(sources[0], [observation(count=count, scope=scope)]),
                        prediction(sources[1], [observation(count=0, assertion="absent"), nausea()]),
                    ])
                    self.assertIsNone(day(result)["vomiting_count"])
                    self.assertIn("reported_occurrence_conflicts_with_zero", day(result)["review_reasons"])
                    self.assertEqual(day(result)["nausea_severity"], 4)

    def test_completed_zero_does_not_erase_unresolved_daily_source_conflict(self):
        sources = [report("A", hour=9), report("B", "2026-11-02")]
        result = aggregate([patient()], sources, [
            prediction(sources[0], [observation(count=None, assertion="uncertain",
                issues=[{"field": "count", "code": "conflicting_sources"}])]),
            prediction(sources[1], [observation(count=0, scope="day_total", assertion="absent")]),
        ])
        self.assertIsNone(day(result)["vomiting_count"])
        self.assertIn("daily_count_conflict", day(result)["review_reasons"])

    def test_explicit_correction_resolves_positive_claim_before_zero_check(self):
        sources = [report("A", hour=9), report("B", hour=20, target="A")]
        result = aggregate([patient()], sources, [prediction(sources[0], [observation(count=None)]),
            prediction(sources[1], [observation(count=0, assertion="absent")])])
        self.assertEqual(result["effective_report_ids"], ["B"])
        self.assertEqual(day(result)["vomiting_count"], 0)
        self.assertEqual(day(result)["count_status"], "usable")

    def test_decreasing_worst_daily_severity_requires_review(self):
        sources = [report("A", hour=9), report("B", hour=20)]
        result = aggregate([patient()], sources, [prediction(sources[0], [nausea(severity=4)]),
                                                 prediction(sources[1], [nausea(severity=2), observation(count=3)])])
        self.assertIsNone(day(result)["nausea_severity"])
        self.assertEqual(day(result)["nausea_status"], "review")
        self.assertEqual(day(result)["vomiting_count"], 3)

    def test_rejected_text_scale_does_not_invalidate_independent_eligible_form_score(self):
        source = report("A")
        value = nausea(severity=4, issues=[{"field": "severity", "code": "unsupported_scale"}])
        result = aggregate([patient()], [source], [prediction(source, [value])])
        self.assertEqual(day(result)["nausea_severity"], 4)
        self.assertEqual(day(result)["nausea_status"], "usable")
        self.assertIn("unsupported_scale", day(result)["review_reasons"])

    def test_failed_or_missing_extraction_is_not_empty_success(self):
        for status in ("error", "missing"):
            with self.subTest(status=status):
                sources = [report("A", hour=9), report("B", hour=20)]
                predictions = [prediction(sources[0], [observation(count=2)])]
                if status == "error":
                    predictions.append(prediction(sources[1], [observation(count=9)], status="error"))
                result = aggregate([patient()], sources, predictions)
                self.assertIsNone(day(result)["vomiting_count"])
                self.assertEqual(day(result)["count_status"], "review")
                self.assertTrue(any(row["reason"] in {"extraction_failed", "missing_extraction"} for row in result["review"]))

    def test_unknown_dates_and_outside_followup_remain_reviewable_not_allocated(self):
        source = report("A")
        result = aggregate([patient()], [source], [prediction(source, [
            observation("O1", day=None, scope="window"), observation("O2", day="2026-10-31"),
        ])])
        self.assertTrue(all(row["vomiting_count"] is None for row in result["daily"]))
        self.assertEqual({row["reason"] for row in result["review"]}, {"date_unallocated", "outside_followup"})

    def test_input_identifier_and_followup_errors_fail_explicitly(self):
        source = report("A")
        with self.assertRaises(ValueError):
            aggregate([patient()], [source], [prediction(source), prediction(source)])
        with self.assertRaises(ValueError):
            aggregate([], [source], [])
        with self.assertRaises(ValueError):
            aggregate([{**patient(), "followup_end": "2026-10-30"}], [], [])
        with self.assertRaises(ValueError):
            aggregate([patient()], [report("B", target="missing")], [])


if __name__ == "__main__":
    unittest.main()
