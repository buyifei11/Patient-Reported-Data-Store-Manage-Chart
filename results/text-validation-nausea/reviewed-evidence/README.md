# Accept a verified harmless quotation omission

TV007's nausea facts are correct. The model joined two original nausea sentences
while omitting the intervening vomiting sentence. That omission changes neither
the nausea meaning nor its worst-so-far-today rating of 5/5. Following source
review and the user's decision, this is accepted as an evidence-format exception.
It is not a reason for another prompt revision or model rerun.

The original strict experiment remains **9/10**. The separate reviewed result
contains **10/10 accepted reports, 15 observations, and 135/135 correct normalized
core fields**: nine automatic passes plus one source-reviewed exception.
No symptom, count, rating, date, or other semantic candidate field was changed.
These are known synthetic examples, not an estimate of accuracy on unseen data.

## What changed

- [review.json](review.json) binds the decision to the exact source and candidate hashes, records the original fragments, the complete original source span, and the reason acceptance is appropriate.
- A separate offline replay restores the intervening source sentence in a working evidence copy before normalization. It does not use reference answers to repair anything.
- [predictions.jsonl](predictions.jsonl) preserves every original raw candidate, response, and extraction metadata field. TV007 includes explicit `evidence_review` provenance; the other nine rows are unchanged.
- [metrics.json](metrics.json) and [summary.json](summary.json) distinguish reviewed normalized results from original strict extraction scores. The raw candidate score remains 154/165 under the unchanged quote matcher.

The production normalizer, evaluator, and prompts are unchanged. Unknown text,
wrong values, changed source content, and unreviewed quote failures do not receive
this exception. The replay verifies literal provenance; semantic equivalence was
established by source review, not by the fragment-matching code. Five new boundary
tests and the full 241-test offline suite pass.

## Replay without model calls

```bash
python scripts/replay_reviewed_evidence.py \
  --source data/text_validation/reports.jsonl \
  --predictions results/text-validation-nausea/prompt/predictions.jsonl \
  --review results/text-validation-nausea/reviewed-evidence/review.json \
  --output artifacts/reviewed-evidence-predictions.jsonl
```

Use a new output path. Existing artifacts are never overwritten. This is an
explicit reviewed replay, not a broad automatic recovery system or an update to
the original experiment's scoring criteria.
