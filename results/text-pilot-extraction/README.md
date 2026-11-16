# First text-extraction baseline: five development reports

The original extraction model and prompt were run on all five reviewed pilot
texts. Each request received only one report's text and the extraction
instructions/schema. Seed facts, questionnaire answers, reference labels, and
the text-generation conversation were not supplied to the extractor.

**All key field values match the references. One report has incomplete supporting
evidence. Under the predeclared rule requiring both correct values and supporting
quotes, four of five reports pass completely.** This is a small, controlled
development result, not held-out or clinical accuracy.

## Configuration and saved files

- Model: `gpt-5.4-mini-2026-03-17`.
- Prompt: [`prompts/extraction.txt`](../../prompts/extraction.txt). Its exact
  system-prompt hash matches the original recorded extraction run.
- Existing current deterministic normalization resolves dates and applies field
  rules. Every pilot source has an empty questionnaire array.
- Five requests, one per report, one attempt each; no retries or outcome-based
  selection. No model training, prompt edits, source/reference edits, or dashboard
  changes were made for this run.
- Usage: 9,378 input tokens and 996 output tokens, 10,374 total.

| File | Role |
|---|---|
| [protocol.json](protocol.json) | Model, prompt, input/reference/runtime hashes and scoring rules frozen before requests |
| [predictions.jsonl](predictions.jsonl) | Actual saved extraction results: raw model response, candidates, normalized observations, errors, and usage metadata |
| [metrics.json](metrics.json) | Unmodified output of the existing automatic evaluator |
| [review.json](review.json) | Separate source-based review of evidence completeness and the time-phrase mismatch |
| [summary.json](summary.json) | Automatic field metrics and the explicitly identified agent-review results |

The existing filenames use the generic term `predictions`; in this project these
are **information-extraction results**, not predictions of future symptoms.

## Results

| Report | Expected vomiting count | Extracted count | Key values | Supporting evidence | Complete report |
|---|---:|---:|---|---|---|
| TP001 | 2 | 2 | Pass | Complete | Pass |
| TP002 | 0 | 0 | Pass | Complete | Pass |
| TP003 | Unknown | Unknown | Pass | Incomplete vomiting quote | Needs improvement |
| TP004 | 4 | 4 | Pass | Complete | Pass |
| TP005 | 1 | 1 | Pass | Complete | Pass |

TP004 and TP005 preserve the claims in their respective reports. Resolving their
cross-report conflict is a later aggregation task, not an extraction correction.

| Check | Result | Interpretation |
|---|---|---|
| Completed processing | 5/5 | API, schema, and current normalization checks completed |
| Symptom observation detection | 10 matched; 0 extra; 0 missing | Precision, recall, and F1 are 1.0 on these ten observations |
| Candidate semantic field expectations | 110/110 | Ten checks with eleven predeclared fields each; includes null values |
| Normalized core fields | 58/58 known; 32/32 null | No missing information was filled with an invented value in these fields |
| Known numeric vomiting counts | 4/4 | Values 2, 0, 4, and 1 were preserved |
| Unknown vomiting number | 1/1 | Occurrence remained present; count stayed null |
| Provided severity ratings | 9/9 | The absent vomiting case correctly has no severity rating |
| Exact supporting source substrings | 10/10 | Every retained quote occurs in its report |
| Quotes supporting every claimed field | 9/10 | Separate agent review found one incomplete quote |
| Complete reports including evidence | 4/5 | Applies the frozen rule; not an automatic field-score average |
| Exact `time_text` match | 9/10 | One shorter time phrase is recorded separately below |

All clocks and medication relations in this pilot are null. Preserving those
nulls does not demonstrate correct extraction of positive clock or medication
examples. Ten observations are also not ten independent patients.

## TP003: a correct rating with incomplete evidence

The source says:

> I have vomited today so far, but I don't know the number of episodes. The worst vomiting severity so far today is 2 out of 5

The model correctly extracted severity 2, scale maximum 5, and the
`worst_today_so_far` context, but retained only this quote:

> I have vomited today so far, but I don't know the number of episodes.

That quote supports occurrence and an unknown count, but omits the clause
supporting the rating. This is an **evidence-retention error**, not a fabricated
or numerically wrong severity. The unchanged automatic evaluator verifies source
substring validity and field values but does not detect this support omission.
The separate evidence review records it explicitly. Actual model output was not
repaired with the reference quote.

TP003's nausea `time_text` is `today`, while the reference uses `so far today`.
Its retained quote contains the full worst-so-far wording, its severity context
is correct, and its resolved date matches. The exact difference remains in
`metrics.json`; it is not silently erased or counted as a new date error.

## Verification and interpretation

Source, reference, prompt, and runtime fingerprints were checked before and after
the run. The five API response IDs are distinct, saved candidates match each raw
response, and no reference-assisted repair or rerun was performed. A separate
agent reviewed every candidate and normalized observation against the source.
This is agent review, not independent human clinical review.

The purpose of five examples is to verify the dataset/extraction/evaluation
procedure and expose concrete failure modes. Their controlled, repetitive
wording and prior use in development prevent generalization claims. The same
model also generated the synthetic texts in separate calls.

The next improvement should be a bounded prompt-engineering experiment focused
on evidence completeness, followed by broader and independently held-out cases.
No claim is made that fine-tuning is needed or that a longer prompt will improve
results. A changed prompt must be evaluated for new errors as well as fixes.

## Re-score the saved run without API calls

Choose a new output file:

```bash
python run_pipeline.py evaluate \
  --source data/text_pilot/reports.jsonl \
  --gold data/text_pilot/expected.jsonl \
  --predictions results/text-pilot-extraction/predictions.jsonl \
  --output artifacts/text-pilot-rescore.json
```

This reproduces the automatic metrics only. The separately documented evidence
review is not replaced by an automatic substring check.
