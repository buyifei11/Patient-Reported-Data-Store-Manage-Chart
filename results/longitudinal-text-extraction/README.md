# Frozen extraction of all 71 longitudinal texts

The frozen nausea-grouping prompt and `gpt-5.4-mini-2026-03-17` processed all
71 reports once. There were no retries, post-result prompt changes, prediction
edits, reference substitutions, or evidence exceptions. All questionnaire arrays
were empty. This is a **known synthetic integration dataset**, not a new held-out
test or clinical validation.

## Results

| Measure | Result | Interpretation |
|---|---:|---|
| Reports processed | 71/71 | No API, parsing, or normalization failures |
| Distinct reference candidate checks | 139/139 | All 1,529 checked raw semantic fields matched |
| Normalized observations | 137/137 | No missing or extra normalized observations |
| Normalized core fields | 1,233/1,233 | 803 known values and 430 intentional nulls correct |
| Reference issue flags | 6/6 | No missing or extra flags |
| Exact `time_text` wording | 135/137 | Two equivalent phrase-order differences remain |
| Reports with exact evaluated normalized fields | 69/71 | Includes literal `time_text` comparison |
| Reports with correct normalized core fields and issues | 71/71 | Excludes literal phrase wording |
| Exact raw candidate count | 70/71 reports | One repeated source claim emitted separately |
| Literal raw quotes | 140/140 | All are exact source substrings; no waiver |

Core fields are symptom, assertion, count, count scope, severity, event date,
event time, date basis, and medication relation. The reference-based candidate
checks do not penalize extra raw candidates; that is why raw candidate counts
are disclosed separately. Do not describe the whole pipeline as universally
100% accurate.

| Source cohort | Reports | Candidate checks | Normalized observations | Core fields |
|---|---:|---:|---:|---:|
| Original ten texts, including two form-to-text supplements | 10 | 17/17 | 15/15 | 135/135 |
| Former questionnaire-only follow-ups | 61 | 122/122 | 122/122 | 1,098/1,098 |

## Three disclosed differences

1. **TXT-R002:** the model emits four candidates for three distinct reference
   claims. Two separate sentences both say no vomiting today. Both zero claims
   are supported; Python merges them into one observation and retains both
   quotes. The conflicting nausea scores 2/5 and 3/5 remain unresolved. This
   duplicate adds no count and does not change the chart.
2. **TXT-R002, nausea:** the reference time phrase is `so far today`; the model
   retains `today so far`. Both phrases occur in the supporting statements and
   describe the same reporting interval.
3. **TXT-L-P003-20, vomiting:** the same phrase-order difference occurs. The
   count, scope, date, and severity remain correct.

The independent [source review](review.json) checks all 71 reports, all 140 raw
candidates and quotes, and the retained normalized evidence. It found no
unsupported populated semantic fields. Raw response candidates equal stored
candidates; no manual cleanup was applied to the predictions.

## Reproduce the evaluation

From the repository root, choose a new metrics path:

```bash
python run_pipeline.py evaluate --source data/longitudinal_text/reports.jsonl \
  --gold data/longitudinal_text/expected.jsonl \
  --predictions results/longitudinal-text-extraction/predictions.jsonl \
  --output artifacts/longitudinal-text-recheck.json
```

This makes no model requests. The original extraction command was:

```bash
python run_pipeline.py extract --source data/longitudinal_text/reports.jsonl \
  --provider openai --model gpt-5.4-mini-2026-03-17 \
  --prompt-file prompts/extraction_nausea_grouping.txt \
  --output results/longitudinal-text-extraction/predictions.jsonl
```

That output is immutable; use a new path if intentionally running again.
Extraction used **166,109 input + 13,794 output = 179,903 tokens** across 71
requests. The separate text-generation stage used three requests and 15,135
tokens. Offline normalization, evaluation, and dashboard building use no API.

## Artifact map and limits

- [protocol.json](protocol.json): configuration and input fingerprints frozen
  before extraction, including the one-attempt and scoring policies.
- [predictions.jsonl](predictions.jsonl): raw responses, candidates, observations,
  response IDs, usage, and source/prompt/runtime fingerprints.
- [metrics.json](metrics.json): unchanged automatic evaluator output and both
  literal mismatches.
- [summary.json](summary.json): cohort/per-report totals and raw-count differences.
- [review.json](review.json): independent source-based audit and interpretation.
- [All-text dashboard](../longitudinal-text-demo/README.md): actual saved-output
  integration, with no reference inputs.

The 63 generated supplements contain 37 unique raw strings. Scenarios are known,
language is controlled, and generator/extractor share a model family. These
results support this integration path, not broad generalization. The separate
[20-case run](../text-holdout-extraction/README.md) remains 18/20 fully correct:
TH005 omits an unknown count's daily scope, and TH012 labels a morning rating as
current. This run does not repair or erase those limitations. No fine-tuning was
performed.
