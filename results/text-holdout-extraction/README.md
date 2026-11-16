# First extraction on twenty frozen text cases

**18 of 20 reports are fully correct; two semantic field errors remain.** All
twenty requests completed and normalized successfully. Technical completion is
not the same as correct extraction. No quote-format exception, reviewed replay,
retry, prompt change, runtime change, or label repair was used.

## Results

| Measure | Result | Meaning |
| --- | ---: | --- |
| Technical report completion | 20/20 | No failed or missing processing results |
| Fully correct reports | 18/20 | Raw claims, normalized records, issues, and supporting evidence agree |
| Correct normalized reports | 19/20 | One raw context error does not change its normalized daily result |
| Candidate semantic fields | 339/341 (99.4%) | Two errors across 31 claims and 11 fields per claim |
| Complete candidate checks | 29/31 | TH005 scope and TH012 context each fail one claim |
| Normalized core fields | 260/261 (99.6%) | 158/159 known values and 102/102 null values correct |
| Observation detection | 29 matched, 0 missing, 0 extra | Correct record structure, including zero observations in TH020 |
| Issue flags | 7 correct, 0 missing, 0 extra | Unknown count/date, unsupported rating context/scale, and conflicts preserved |
| Exact continuous quotes | 31/31 | No skipped or invented quotation spans |

Field accuracy includes many expected nulls, so it must be read with the report
score and the concrete errors below. The 20 reports are a small targeted synthetic
validation set, not a measure of accuracy on real patient populations.

## Two real errors

### TH005: an unknown count still has a known scope

The source states:

> I’ve vomited today so far, but I can’t recall the number.

The candidate correctly preserves occurrence and `count=null`, but emits
`count_scope=null` instead of `day_to_date`. The patient does not know the number;
the period being reported is nevertheless known. This scope omission survives
normalization and could affect daily classification or reconciliation. No episode
count was invented, and the missing-count issue is correct.

### TH012: morning is not the current moment

The source states:

> This morning, my nausea was 2 out of 5.

The candidate emits `severity_context=current` instead of `other`, although it
retains `time_text="This morning"` and the correct numeric rating. This is a real
context error, not an acceptable quotation-format difference.

The frozen normalizer excludes both `current` and `other` ratings from its
daily-worst severity field. Consequently, the morning observation still has
normalized severity null and `unsupported_severity_context`, while the separate
daily-worst score remains 4/5. The normalized report is correct despite the raw
candidate error; that does not erase the extraction failure.

Neither error was waived or repaired. Both remain visible in the saved output.

## Evidence and time-span review

All 31 quotes are exact continuous source spans. Thirty support every populated
candidate claim; TH012's quote does not support the erroneous `current` label.
TH005's quote supports the populated claims, but its candidate omits a known
scope. Thus literal quote validity alone does not imply complete factual accuracy.

TH003 uses `time_text="today"` where the reference uses `today so far`. Its full
quote and `worst_today_so_far` context retain the daily-worst meaning, so this
literal span difference is harmless. Exact timing-text agreement is 28/29; the
semantic report score accepts this difference under the frozen review policy.
Wider-than-necessary supporting quotes in TH009 and an incidental conjunction in
TH010 are also valid. No reviewed-evidence exception is needed in this run.

The broader cases worked as intended: current versus daily-worst values stayed
separate in TH011; yesterday and today retained different scopes/dates; the 08:10
event was not added to the daily total; the medication relation stayed with nausea;
both conflicting pairs retained their source values and became unresolved records;
7/10 was not converted to a five-point rating; an unknown date remained unknown;
and TH020 produced empty arrays without fabricated symptom denials.

## Frozen setup and validation

- Twenty new reports were generated and reference-labeled before any extraction.
  Eight pre-extraction text edits are disclosed in the preparation record.
- Model: `gpt-5.4-mini-2026-03-17`; prompt:
  [`extraction_nausea_grouping.txt`](../../prompts/extraction_nausea_grouping.txt).
  Reasoning effort: `none`; maximum output: 2,048 tokens.
- Twenty requests ran once each in source order. Each request received only the
  report text plus frozen instructions/schema. No seeds, gold, questionnaires, or
  submission metadata entered the model. Python resolved relative dates afterward.
- Input usage: 46,553 tokens; output usage: 3,003; total: 49,556.
- Source, reference, prompt, schema/runtime, and review-adapter fingerprints match
  the preparation freeze. The default prompt and dashboard inputs are unchanged.
- Root review and two separate read-only audits verified all candidate evidence,
  fields, response provenance, unique response IDs, and report-level conclusions.
  Independent recomputation reproduced the saved metrics exactly.
- There were no runtime changes, so this evaluation did not add behavioral tests
  or rerun unrelated suites. Schema/provenance and result checks were performed.

`metrics.json` retains the evaluator's legacy `development_fixtures` role label.
The actual role and first-run provenance are explicitly recorded in `protocol.json`
and `summary.json`; the metric engine and labels were not edited to improve scores.

## Files and offline reproduction

| File | Purpose |
| --- | --- |
| [protocol.json](protocol.json) | Pre-request freeze, metrics, policy, and denominators |
| [predictions.jsonl](predictions.jsonl) | All twenty raw responses, candidates, normalized outputs, and metadata |
| [metrics.json](metrics.json) | Unchanged evaluator output, including every mismatch |
| [review.json](review.json) | Candidate-by-candidate source review and error impact |
| [summary.json](summary.json) | Aggregate and per-report results with provenance |

Recalculate automatic scores without model requests; choose a new output path:

```bash
python run_pipeline.py evaluate \
  --source data/text_holdout/reports.jsonl \
  --gold data/text_holdout/expected.jsonl \
  --predictions results/text-holdout-extraction/predictions.jsonl \
  --output artifacts/text-holdout-metrics.json
```

## Decision and limits

Preserve this first frozen result and its two known semantic limitations. Do not
keep retuning or rerunning these twenty cases within this evaluation. The result
supports moving to the longitudinal text pipeline with traceable outputs and
review visibility, rather than claiming perfect extraction or silently promoting
the experimental prompt to the CLI default.

One attempt per report gives no stability estimate. The texts are controlled,
AI-assisted, and generated by the same model family; correction chains, multi-day
allocation, timezone boundaries, and hypothetical reports are not covered. If
these outcomes later inform tuning, treat this set as known regression data for
that development; preserve its first-run validation result separately.
