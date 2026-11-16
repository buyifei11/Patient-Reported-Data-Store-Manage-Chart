"""A source-reviewed evidence exception cannot silently repair values or provenance."""

import copy
import json
from pathlib import Path
import unittest

from scripts.replay_reviewed_evidence import reviewed_replay
from src.normalization import NormalizationError
from src.pipeline import _digest, read_jsonl

ROOT = Path(__file__).resolve().parents[1]


class ReviewedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.source = next(r for r in read_jsonl(ROOT / "data/text_validation/reports.jsonl") if r["report_id"] == "TV007")
        self.saved = next(r for r in read_jsonl(ROOT / "results/text-validation-nausea/prompt/predictions.jsonl") if r["report_id"] == "TV007")
        self.review = json.loads((ROOT / "results/text-validation-nausea/reviewed-evidence/review.json").read_text())

    def test_review_restores_evidence_without_changing_raw_output_or_values(self):
        original = copy.deepcopy((self.source, self.saved, self.review))
        result = reviewed_replay(self.source, self.saved, self.review)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["observations"]), 2)
        nausea = next(o for o in result["observations"] if o["symptom"] == "nausea")
        self.assertEqual(nausea["severity"], 5)
        self.assertEqual(nausea["evidence"], [{"path": "text", "value": self.source["text"]}])
        for key in ("candidates", "raw_response", "metadata"):
            self.assertEqual(result[key], self.saved[key])
        self.assertEqual((self.source, self.saved, self.review), original)

    def test_stale_source_or_changed_candidate_cannot_use_existing_review(self):
        self.source["text"] += " Correction: that score was 1 out of 5."
        with self.assertRaisesRegex(ValueError, "source hash"):
            reviewed_replay(self.source, self.saved, self.review)
        self.setUp()
        self.saved["candidates"][0]["severity_value"] = 1
        with self.assertRaisesRegex(ValueError, "unchanged candidate"):
            reviewed_replay(self.source, self.saved, self.review)

    def test_invented_or_reordered_evidence_is_not_accepted(self):
        self.review["accepted_source_span"] = self.saved["candidates"][0]["quote"]
        with self.assertRaisesRegex(ValueError, "continuous source span"):
            reviewed_replay(self.source, self.saved, self.review)
        self.setUp()
        self.review["original_fragments"].reverse()
        self.saved["candidates"][0]["quote"] = " ".join(self.review["original_fragments"])
        self.review["candidate_sha256"] = _digest(self.saved["candidates"][0])
        with self.assertRaisesRegex(ValueError, "original order"):
            reviewed_replay(self.source, self.saved, self.review)

    def test_other_normalization_errors_are_not_waived(self):
        self.saved["candidates"][0]["count_scope"] = "day_to_date"
        self.review["candidate_sha256"] = _digest(self.saved["candidates"][0])
        with self.assertRaises(NormalizationError):
            reviewed_replay(self.source, self.saved, self.review)

    def test_extraction_failures_cannot_be_converted_to_success(self):
        self.saved["error_code"] = "invalid_schema"
        with self.assertRaisesRegex(ValueError, "extraction failure"):
            reviewed_replay(self.source, self.saved, self.review)
