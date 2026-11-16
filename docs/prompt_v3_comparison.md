# Scope and evidence prompt comparison: results

**Keep v1 as the default.** V3 improves literal evidence retention and several
normalized outputs, but it introduces repeated count-scope errors and fails the
predeclared adoption gate. It remains an explicitly selectable experimental
prompt. This is a completed prompt-engineering experiment, not training or a
claim that the baseline is reliable.

## What was compared

Both arms used `gpt-5.4-mini-2026-03-17`, the same schema, evaluator, client settings,
and current normalizer including the midnight-to-submission fix. V3 combines v2's
temporal clarification with claim grouping, scope instructions, and literal
evidence-copying instructions. This measures the combined prompt revision, not
the separate causal contribution of each instruction.

There were **280 actual requests**, with no retries: two prompts, two rounds,
50 known regression reports plus 20 fresh validation reports. These represent
70 distinct reports, 83 reference observations, and 63 targeted extraction checks.
The fresh prompt was locked before case inspection; labels were reviewed and
corrected before inference. All inputs and runtime files were frozen before
calls. No prompt, source, label, or runtime change followed the results.

See the [frozen protocol](prompt_v3_experiment.md),
[manifest](../results/scope-evidence-v3/manifest.json), and
[new-case review](../data/heldout_v3/review.md).

## Measured results

Failed reports remain in the denominators. Completion means extraction and
normalization finished; it does not mean every field is correct. Known-field
scores below compare normalized observations. Candidate scope checks inspect
selected pre-reconciliation claims and can still be evaluated after normalization
fails. The denominators differ because the measures inspect different stages.

| Known regression measure | v1 r1 | v3 r1 | v1 r2 | v3 r2 |
| --- | ---: | ---: | ---: | ---: |
| Completed reports | 47/50 | 48/50 | 45/50 | 48/50 |
| Known count scopes | 31/36 | 29/36 | 30/36 | 30/36 |
| Known counts | 24/28 | 25/28 | 23/28 | 26/28 |
| Known dates | 53/56 | 54/56 | 47/56 | 54/56 |
| Candidate scope checks | 18/22 | 19/22 | 18/22 | 20/22 |
| All targeted checks | 34/41 | 37/41 | 34/41 | 38/41 |
| Observation F1 | 0.967 | 0.975 | 0.931 | 0.975 |

| Fresh validation measure | v1 r1 | v3 r1 | v1 r2 | v3 r2 |
| --- | ---: | ---: | ---: | ---: |
| Completed reports | 15/20 | 18/20 | 14/20 | 20/20 |
| Known count scopes | 10/16 | 9/16 | 9/16 | 11/16 |
| Known counts | 8/13 | 11/13 | 7/13 | 13/13 |
| Known dates | 10/20 | 18/20 | 11/20 | 19/20 |
| Candidate scope checks | 15/16 | 12/16 | 14/16 | 12/16 |
| All targeted checks | 18/22 | 15/22 | 18/22 | 17/22 |
| Assertion agreement | 14/22 | 19/22 | 13/22 | 21/22 |
| Observation F1 | 0.718 | 0.884 | 0.703 | 0.933 |
| Matched reference-null fields overfilled | 1/79 | 2/79 | 1/79 | 2/79 |

V3's 20/20 completion in fresh round 2 is therefore not perfect extraction.
Its pre-reconciliation scope checks are worse in both fresh rounds, even when
more completed reports improve end-to-end scores. Fresh round 1's normalized
scope agreement also declines, independently failing the adoption gate.

Across both splits and rounds, **16/140 baseline outputs** were first rejected
for a nonliteral/out-of-quote `time_text` or a missing quoted day/calendar anchor;
**0/140 v3 outputs** received those first rejection reasons. This is a concrete
improvement in the implemented evidence checks, not a complete evidence-accuracy
metric. It excludes semantic clock-time errors and failures hidden behind an
earlier rejection. Some unsupported claims still pass the current grounder.

## Paired findings

Stable gains in both rounds:

- **H002:** v3 preserves the stated count of two bouts within one window; v1
  splits it into count-one event records.
- **H012, T009, T019, T020:** v3 retains the calendar/time support needed by the
  candidate rather than quoting only the symptom clause, avoiding the baseline
  normalization failures.
- **D001, H004, T012:** hypothetical `tonight` statements resolve to today while
  remaining hypothetical with null observed counts.
- **H010:** v3 retains the multi-sentence evidence and multi-day window count, so
  normalization succeeds. However, its `time_text` is the location phrase
  `on the back of a community-center schedule`, not a temporal expression.
  This remains a semantic error, not harmless excerpt-boundary variation.

Material regressions that prevent promotion:

- **R002, both rounds:** today's explicit absence becomes `day_total`, which
  incorrectly treats today as completed and fails the whole report. V1 succeeds.
- **R007, both rounds:** a meal-window count becomes `event`.
- **H009, T013, T014, both rounds:** a known daily or meal-window scope becomes
  null when the count is unknown. Unknown quantity does not erase stated scope.
- **T011, both rounds:** v3 changes an earlier daily cumulative snapshot to
  `window`; v1 retains its daily cumulative scope.
- **T010, both rounds:** v3 repairs the quote but changes the candidate scope from
  correct `window` to `event`. A recovered report can still contain a new error.
- **T001, fresh round 1:** v3 treats an interval's 06:00 start as an episode time;
  grounding rejects it. **T005, fresh round 1:** v3 supplies the first calendar
  date as `explicit_date` despite `day_reference: multiple_days`. Both recover
  in round 2, while the repeated scope errors above remain.

Other observed differences, including R008, D011, H007, and D016, are preserved in
the full metrics and paired reports. They were not selectively retried or used
to alter the frozen prompt.

## Shared limitations and metric blind spots

**D012 still fails under both prompts in both rounds.** V1 uses a single-day total
for several days. V3 fixes that scope but supplies `explicit_date` with
`multiple_days`, violating a cross-field rule. Its targeted check does not cover
`explicit_date`, so a passing check is not a successful pipeline result.

**T011 exposes another wording boundary in deterministic reconciliation.**
`Since midnight today up to the time of this report` describes the current daily
range, but the bounded normalizer only masks the previously supported `from`
form. All four outputs retain text count 3 and questionnaire count 4 separately
instead of recording their conflict. The contract-correct reference was retained;
this shared defect was not fixed during the frozen prompt comparison. It needs
a separately tested code change, not model training.

**Literal clock grounding does not prove an episode time.** T008 v3 correctly
groups count 2 within a window but assigns its 10:00 start as the event time in
both rounds. The grounder accepts the literal `from 10:00` anchor. All T011 runs
similarly assign the 09:00 cumulative cutoff as an event time. By contrast, its
`between` heuristic rejects T001's 06:00 assignment in v3 round 1. These are
inconsistent semantic protections; explicit range endpoints and snapshot cutoffs
need separate treatment from episode times.

**Numerical quote support is not comprehensively checked.** T017 baseline round 2
has plausible normalized fields, but its quote contains no support for the
candidate's rating of 3. V3 retains the full supporting span. The current scorer
and grounder do not fully measure this difference. Likewise, automated paired
reports omit `time_text` and `date_basis` diagnostics, so their `resolved_errors`
label is only a review aid; H010 shows why manual candidate review is still needed.

## Artifacts, usage, and reproduction

The [result directory](../results/scope-evidence-v3/) contains all eight exact
prediction files, eight full metric files, four paired reports, and a
[machine-readable summary](../results/scope-evidence-v3/summary.json). Candidates,
normalized observations, failures, prompt/model/source/code hashes, raw model
text, and usage are retained. Provider request IDs and credentials are omitted.

All 280 calls returned usage: **575,428 input tokens**, including **427,264 cached
input tokens**, **32,509 output tokens**, and zero reasoning tokens. There were
25 normalization failures, no service/configuration failures, and no retries.
V1 had 19 failures and v3 had 6; the failure-count reduction does not erase the
semantic regressions. Token usage is not a billing invoice or a population-level
performance benchmark.

To rescore the saved outputs without API calls, copy them into a new directory:

```bash
mkdir -p work/v3-review
cp results/scope-evidence-v3/manifest.json results/scope-evidence-v3/*.predictions.jsonl work/v3-review/
python scripts/run_prompt_v3.py score --directory work/v3-review --split regression
python scripts/run_prompt_v3.py score --directory work/v3-review --split heldout_v3
```

Scoring verifies frozen inputs and saved metadata and refuses to overwrite prior
metrics. The runner's `freeze` and `run` commands support a new full replication;
`run` makes paid API requests. Offline tests and scoring never load credentials
or call the model. The full offline suite passes **163 tests**.

## Decision and next bounded work

The frozen gate is not met. `prompts/extraction.txt` remains byte-identical to v1.
V3 stays available through `--prompt-file prompts/extraction_v3.txt`; it is not
silently enabled for the main pipeline.

The next code work should address current-day range variants and distinguish
range endpoints from episode times with boundary tests. A subsequent prompt
experiment should isolate evidence-copying changes from count-scope changes,
explicitly retain scope when quantity is unknown, and preserve today's absence
rule. These are follow-up hypotheses, not fixes implemented in this experiment.
Now that T001-T020 outputs have been inspected, using them for tuning makes them
known regression data. Any later independent evaluation needs new cases.
