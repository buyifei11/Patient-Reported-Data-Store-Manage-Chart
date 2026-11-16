# First development run

Run: `gpt54mini-dev-v1`, 2026-11-15. Model requested and returned: `gpt-5.4-mini-2026-03-17`.

This is one real API run on the 10 synthetic development reports. The model received the generic extraction prompt, candidate schema, and each report's text. It did not receive reference answers, questionnaire answers, or other reports. Code handled questionnaire reconciliation and calendar arithmetic after extraction. There were no retries, no prompt revisions after seeing these outputs, and no edits to the source or gold dataset.

## Results

| Measure | Result | Interpretation |
| --- | --- | --- |
| Completed and normalized reports | 10/10 | No transport, JSON, schema, or normalization failure. |
| Matched symptom observations | 15/15, no extras | Mention detection precision, recall, and F1 are 1.0; this does not mean all fields are correct. |
| Assertion accuracy | 15/15 | Present, absent, hypothetical, and reconciled uncertain values match. |
| Known count accuracy | 7/7 | Separate from the 8 reference-null counts. |
| Known count-scope accuracy | 9/9 | Separate from 6 null scopes. |
| Known severity accuracy | 2/2 | A very small denominator; not broad evidence of rating extraction quality. |
| Known date accuracy | 13/14 (92.9%) | One real temporal interpretation error. |
| Known exact clock time | 1/1 | One example only. |
| Known medication relationship | 1/1 | One temporal association, not a causal conclusion. |
| Targeted extraction checks | 3/3 | Text values were preserved before questionnaire conflicts were resolved. |
| Reference-null fields overfilled | 0/56 | No scored null field was filled with an unsupported non-null value. |
| Issue detection | 5 correct, 1 extra, 0 missing | Precision 83.3%, recall 100%, F1 90.9%. |
| Exact `time_text` agreement | 12/15 | Three differences are source-excerpt boundaries, discussed below. |

No pooled overall accuracy is reported. Different fields have different denominators, and many are legitimately null. See [evaluation.md](evaluation.md) for exact metric definitions and observation matching.

## Error analysis

**R010: a real date error.** The source says `I am worried I might vomit tonight.` The model correctly produced `assertion=hypothetical`, `count=null`, and `time_text=tonight`, but set `day_reference=unknown`. Code therefore retained `event_date=null`, `date_basis=unknown`, and added `date_unknown`. The reference date is November 8 in the patient's timezone. The three mismatch entries for date, date basis, and the extra issue flag share one underlying temporal-anchor error. The model did not turn the hypothetical symptom into an actual vomiting episode.

The next targeted improvement is to clarify same-day expressions such as `tonight` in the generic extraction instructions, then evaluate separately authored cases after freezing that revision. The first run is preserved as observed; it has not been rerun or silently repaired to obtain a perfect score.

**R002, R005, and R006: excerpt-boundary differences.** The model preserved `at its worst so far today`; the reference uses `so far today`. Both are exact source substrings and agree on the relevant day and severity context. The evaluator reports all three as exact-string mismatches for transparency, but they are not interpreted as three additional semantic date errors. The reference answers were not changed to match the model's wording.

## Usage and artifacts

The API reported 18,479 input tokens, of which 14,976 were cached, and 1,354 output tokens. Reasoning tokens were zero. Summed report elapsed time was 16.83 seconds; median report elapsed time was 1.62 seconds. These include local request/normalization overhead and describe this one small sequential run, not a latency benchmark.

At the [listed model prices](https://developers.openai.com/api/docs/models/gpt-5.4-mini) checked on the run date, uncached input at $0.75/M, cached input at $0.075/M, and output at $4.50/M imply approximately **$0.00984** for these token counts. This is a calculated estimate, not an invoice or a guaranteed future charge.

- [Actual predictions and run metadata](../results/gpt54mini-dev-v1/predictions.jsonl)
- [Full metrics and mismatch details](../results/gpt54mini-dev-v1/metrics.json)
- [Model-selection rationale](model_selection.md)

The published synthetic snapshot preserves candidate and normalized values, exact assistant text, hashes, model identity, usage, and timings. Provider response IDs are omitted. Original local run files remain in ignored `data/processed/` and `artifacts/` folders. Scoring the saved snapshot makes no model calls and requires no API key.

## What this establishes

The pipeline can run a structured-output model, validate its response, reconcile questionnaire conflicts, and expose specific errors against development references. The model is a reasonable candidate for further evaluation on this bounded task; this run does not establish superiority over another model, held-out performance, clinical validity, or readiness for real patient records. In particular, the severity and medication examples are too few to support general conclusions.

SQLite, correction-aware cross-report aggregation, SQL queries, charts, and the full four-week dataset are not part of this milestone.
