"""Offline scoring tests. Copied references here test the scorer, not an LLM."""

import copy
import json
from pathlib import Path
import unittest

from src.evaluation import evaluate_predictions


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(relative_path):
    return [json.loads(line) for line in (ROOT / relative_path).read_text().splitlines() if line.strip()]


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.sources = read_jsonl("data/raw/reports.jsonl")
        self.gold = read_jsonl("data/gold/expected.jsonl")
        # A controlled oracle for unit tests only; production never builds
        # predictions from gold, and these are not model-performance results.
        self.predictions = [
            {"report_id": record["report_id"], "status": "ok", "error": None,
             "observations": copy.deepcopy(record["observations"]),
             "candidates": [{**copy.deepcopy(check["expected_fields"]),
                             "quote": check["source"]["value"]}
                            for check in record["extraction_checks"]]}
            for record in self.gold
        ]

    def score(self):
        return evaluate_predictions(self.sources, self.gold, self.predictions)

    def test_controlled_correct_outputs(self):
        result = self.score()
        self.assertEqual(result["report_completion"]["ok"], 10)
        self.assertEqual(result["observation_detection"]["true_positive"], 15)
        self.assertEqual(result["observation_detection"]["f1"], 1)
        self.assertEqual(result["fields"]["count"]["reference_known"],
                         {"correct": 7, "total": 7, "accuracy": 1})
        self.assertEqual(result["fields"]["count"]["reference_null"]["total"], 8)
        self.assertEqual(result["fields"]["severity"]["reference_known"]["total"], 2)
        self.assertEqual(result["issue_detection"]["true_positive"], 5)
        self.assertEqual(result["extraction_checks"]["passed"], 3)
        self.assertEqual(result["mismatches"], [])
        json.dumps(result, allow_nan=False)

    def test_wrong_count_does_not_change_detection(self):
        self.predictions[0]["observations"][0]["count"] = 99
        result = self.score()
        self.assertEqual(result["observation_detection"]["f1"], 1)
        self.assertEqual(result["fields"]["count"]["reference_known"]["correct"], 6)
        wrong = [m for m in result["mismatches"] if m.get("field") == "count"]
        self.assertEqual([(m["expected"], m["predicted"]) for m in wrong], [(2, 99)])

    def test_null_only_outputs_cannot_hide_known_field_failures(self):
        nullable = ("count", "count_scope", "severity", "event_date", "event_time",
                    "time_text", "medication_relation")
        for report in self.predictions:
            for observation in report["observations"]:
                for field in nullable:
                    observation[field] = None
        result = self.score()
        self.assertEqual(result["fields"]["count"]["reference_known"]["accuracy"], 0)
        self.assertEqual(result["fields"]["severity"]["reference_known"]["accuracy"], 0)
        self.assertEqual(result["fields"]["event_date"]["reference_known"]["accuracy"], 0)
        self.assertEqual(result["fields"]["count"]["reference_null"]["accuracy"], 1)

    def test_missing_report_stays_in_denominators(self):
        self.predictions.pop(0)
        result = self.score()
        self.assertEqual(result["report_completion"]["missing"], 1)
        self.assertEqual(result["report_completion"]["rate"], 0.9)
        self.assertEqual(result["observation_detection"]["false_negative"], 2)
        self.assertEqual(result["assertion_accuracy"]["correct"], 13)
        self.assertEqual(result["assertion_accuracy"]["total"], 15)
        self.assertEqual(result["extraction_checks"]["passed"], 2)
        self.assertEqual(result["extraction_checks"]["total"], 3)
        self.assertEqual(result["fields"]["count"]["reference_null"]["correct"], 7)

    def test_error_does_not_score_partial_or_stale_output_as_success(self):
        self.predictions[0]["status"] = "error"
        self.predictions[0]["error"] = "Invalid model JSON"
        result = self.score()
        self.assertEqual(result["report_completion"]["error"], 1)
        self.assertEqual(result["observation_detection"]["false_negative"], 2)
        self.assertEqual(result["extraction_checks"]["passed"], 2)
        self.assertTrue(any(m.get("error") == "Invalid model JSON" for m in result["mismatches"]))

    def test_normalization_failure_preserves_completed_extraction_checks(self):
        self.predictions[0].update(status="error", error_code="normalization_error",
                                   error="Normalization failed", observations=[])
        result = self.score()
        self.assertEqual(result["report_completion"]["error"], 1)
        self.assertEqual(result["report_completion"]["rate"], 0.9)
        self.assertEqual(result["observation_detection"]["false_negative"], 2)
        self.assertEqual(result["fields"]["count"]["reference_known"]["correct"], 6)
        self.assertEqual(result["extraction_checks"]["passed"], 3)
        self.predictions[0]["candidates"][0]["count"] = None
        result = self.score()
        self.assertEqual(result["extraction_checks"]["passed"], 2)

    def test_other_failure_codes_do_not_score_retained_candidates(self):
        for code in (None, "invalid_schema", "invalid_json", "network_error"):
            with self.subTest(code=code):
                self.predictions[0].update(status="error", error_code=code,
                                           error="Extraction failed", observations=[])
                result = self.score()
                self.assertEqual(result["extraction_checks"]["passed"], 2)
                self.assertEqual(result["observation_detection"]["false_negative"], 2)

    def test_successful_empty_report_is_distinct_from_failure(self):
        sources = [{"report_id": "empty", "text": "Good morning.", "questionnaire_answers": []}]
        gold = [{"report_id": "empty", "observations": [], "extraction_checks": []}]
        prediction = {"report_id": "empty", "status": "ok", "observations": [],
                      "candidates": [], "error": None}
        result = evaluate_predictions(sources, gold, [prediction])
        self.assertEqual(result["report_completion"]["rate"], 1)
        self.assertIsNone(result["observation_detection"]["recall"])
        prediction.update(status="error", error="Timeout")
        result = evaluate_predictions(sources, gold, [prediction])
        self.assertEqual(result["report_completion"]["rate"], 0)
        self.assertEqual(result["mismatches"][0]["kind"], "report_failure")

    def test_duplicate_observation_is_false_positive(self):
        duplicate = copy.deepcopy(self.predictions[0]["observations"][0])
        duplicate["observation_id"] = "unrelated-id"
        self.predictions[0]["observations"].append(duplicate)
        result = self.score()
        self.assertEqual(result["observation_detection"]["true_positive"], 15)
        self.assertEqual(result["observation_detection"]["false_positive"], 1)
        self.assertEqual(result["observation_detection"]["precision"], 15 / 16)

    def test_extra_symptom_and_its_issues_are_false_positives(self):
        extra = copy.deepcopy(self.predictions[0]["observations"][1])
        extra["issues"] = [{"field": "count", "code": "count_unknown"}]
        self.predictions[2]["observations"].append(extra)
        result = self.score()
        self.assertEqual(result["observation_detection"]["false_positive"], 1)
        self.assertEqual(result["issue_detection"]["false_positive"], 1)

    def test_identifiers_and_array_order_are_not_targets(self):
        self.predictions.reverse()
        for report in self.predictions:
            report["observations"].reverse()
            for observation in report["observations"]:
                observation["observation_id"] = "same-display-label"
                observation["evidence"].reverse()
                observation["issues"].reverse()
        result = self.score()
        self.assertEqual(result["observation_detection"]["f1"], 1)
        self.assertEqual(result["mismatches"], [])

    def test_issues_match_field_and_code_together(self):
        self.predictions[8]["observations"][0]["issues"] = [
            {"field": "severity", "code": "conflicting_sources"}]
        result = self.score()
        self.assertEqual(result["issue_detection"]["true_positive"], 3)
        self.assertEqual(result["issue_detection"]["false_negative"], 2)
        self.assertEqual(result["issue_detection"]["false_positive"], 1)

    def test_r009_checks_candidate_before_reconciliation(self):
        result = self.score()
        self.assertEqual(result["extraction_checks"]["passed"], 3)
        self.assertIsNone(self.predictions[8]["observations"][0]["count"])
        self.predictions[8]["candidates"][0]["count"] = None
        result = self.score()
        self.assertEqual(result["extraction_checks"]["passed"], 2)
        self.assertEqual(result["fields"]["count"]["reference_null"]["accuracy"], 1)
        failure = next(m for m in result["mismatches"] if m["kind"] == "extraction_check")
        self.assertEqual(failure["report_id"], "R009")
        self.assertEqual(failure["differences"][0]["expected"], 1)

    def test_check_requires_the_relevant_source_quote(self):
        self.predictions[0]["candidates"][0]["quote"] = "I felt nauseous all morning today."
        result = self.score()
        self.assertEqual(result["extraction_checks"]["passed"], 2)
        self.assertEqual(result["extraction_checks"]["fields"]["count"]["correct"], 1)

    def test_unknown_overfill_is_counted_separately(self):
        self.predictions[6]["observations"][0]["event_date"] = "2026-11-05"
        self.predictions[7]["observations"][0]["count"] = 3
        result = self.score()
        self.assertEqual(result["unknown_overfill"]["errors"], 2)
        self.assertEqual(result["fields"]["count"]["reference_null"]["overfilled"], 1)
        self.assertEqual(result["fields"]["event_date"]["reference_null"]["accuracy"], 0)

    def test_missing_field_is_not_a_correct_null(self):
        del self.predictions[0]["observations"][0]["severity"]
        result = self.score()
        self.assertEqual(result["fields"]["severity"]["missing_predictions"], 1)
        self.assertEqual(result["fields"]["severity"]["reference_null"]["correct"], 12)

    def test_boolean_does_not_equal_zero(self):
        self.predictions[1]["observations"][1]["count"] = False
        result = self.score()
        self.assertEqual(result["fields"]["count"]["reference_known"]["correct"], 6)

    def repeated_symptom_fixture(self):
        phrases = ["I vomited once yesterday.", "I vomited twice today."]
        source = {"report_id": "repeat", "text": " ".join(phrases), "questionnaire_answers": []}
        observations = []
        for i, phrase in enumerate(phrases):
            observation = copy.deepcopy(self.gold[2]["observations"][0])
            observation.update(observation_id=f"repeat-{i}", count=i + 1,
                               evidence=[{"path": "text", "value": phrase}])
            observations.append(observation)
        reference = {"report_id": "repeat", "observations": observations, "extraction_checks": []}
        prediction = {"report_id": "repeat", "status": "ok", "error": None,
                      "observations": copy.deepcopy(observations), "candidates": []}
        return source, reference, prediction

    def test_repeat_symptoms_align_by_evidence_not_best_count(self):
        source, reference, prediction = self.repeated_symptom_fixture()
        prediction["observations"][0]["count"] = 2
        prediction["observations"][1]["count"] = 1
        prediction["observations"].reverse()
        result = evaluate_predictions([source], [reference], [prediction])
        self.assertEqual(result["observation_detection"]["true_positive"], 2)
        self.assertEqual(result["fields"]["count"]["reference_known"]["correct"], 0)

    def test_repeat_symptoms_accept_different_overlapping_excerpts(self):
        source, reference, prediction = self.repeated_symptom_fixture()
        for observation in prediction["observations"]:
            observation["evidence"][0]["value"] = observation["evidence"][0]["value"][2:-1]
        prediction["observations"].reverse()
        result = evaluate_predictions([source], [reference], [prediction])
        self.assertEqual(result["observation_detection"]["true_positive"], 2)
        self.assertEqual(result["fields"]["count"]["reference_known"]["correct"], 2)

    def test_ambiguous_provenance_does_not_choose_best_values(self):
        source, reference, prediction = self.repeated_symptom_fixture()
        for observation in prediction["observations"]:
            observation["evidence"] = [{"path": "text", "value": source["text"]}]
        result = evaluate_predictions([source], [reference], [prediction])
        self.assertEqual(result["observation_detection"]["false_negative"], 2)
        self.assertEqual(result["observation_detection"]["false_positive"], 2)
        self.assertEqual(len(result["matching"]["ambiguous_groups"]), 1)

    def test_duplicate_and_unknown_report_ids_raise(self):
        for target in (self.sources, self.gold, self.predictions):
            with self.subTest(target=target[0].keys()):
                target.append(copy.deepcopy(target[0]))
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    self.score()
                target.pop()
        self.predictions[0]["report_id"] = "unrecognized"
        with self.assertRaisesRegex(ValueError, "Unknown prediction"):
            self.score()

    def test_missing_or_extra_gold_report_raises(self):
        self.gold.pop()
        with self.assertRaisesRegex(ValueError, "must match exactly"):
            self.score()

    def test_stale_gold_evidence_raises(self):
        self.gold[0]["observations"][0]["evidence"][0]["value"] = "Unrelated edited source."
        with self.assertRaisesRegex(ValueError, "gold evidence"):
            self.score()

    def test_malformed_status_raises_instead_of_disappearing(self):
        self.predictions[0]["status"] = "success"
        with self.assertRaisesRegex(ValueError, "status must"):
            self.score()

    def test_empty_evaluation_has_no_invented_perfect_score(self):
        result = evaluate_predictions([], [], [])
        self.assertIsNone(result["report_completion"]["rate"])
        self.assertIsNone(result["observation_detection"]["f1"])
        self.assertIsNone(result["fields"]["count"]["reference_known"]["accuracy"])


if __name__ == "__main__":
    unittest.main()
