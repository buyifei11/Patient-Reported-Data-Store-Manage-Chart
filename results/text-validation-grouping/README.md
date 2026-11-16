# Same-context grouping prompt: bounded regression comparison

**This candidate does not improve overall correctness in the observed run.**
It removes fragmented count/rating candidates, but complete reports decrease
from **8/10 to 7/10** compared with the saved evidence-focused prompt. Two stitched
quotes and one invalid nausea field cause three reports to fail normalization.
The candidate is retained as an experiment and is not promoted to the default.

## What changed

The new [grouping prompt](../../prompts/extraction_grouping.txt) starts from
[`extraction_evidence.txt`](../../prompts/extraction_evidence.txt). It clarifies
one ambiguous separation sentence and adds a grouping block:

- Gather complementary fields for one symptom and one explicitly supported
  observation context into one candidate, regardless of clause/sentence order.
- Keep a cumulative count so far today and that symptom's worst-so-far-today
  rating together when their context is compatible.
- Preserve a complete, exact, contiguous evidence span, including any intervening
  other-symptom text without transferring that symptom's values.
- Keep different dates, events, windows, reporting cutoffs, rating contexts,
  assertions, medication contexts, and conflicting values separate. Never add
  counts or select a preferred value to resolve disagreement.

Field definitions and the earlier evidence-completeness block are unchanged.
No report IDs, patient texts, reference answers, or numeric examples were inserted.
A separate agent reviewed the concrete prompt diff before extraction.

The ten cases are now **known development/regression material** because their
earlier failures guided this change. The historical `text_validation` folder name
and seed split labels remain unchanged for provenance; this is not fresh validation.

## Frozen setup

The same ten texts, reference answers, model `gpt-5.4-mini-2026-03-17`, reasoning
effort `none`, 2,048-output-token limit, schema, normalizer, evaluator, and review
rules were retained. The [protocol](protocol.json) was frozen before inference
and fingerprints all saved comparison artifacts and unchanged prompts.

Ten actual new extraction calls were made: one per report, with no retries or
output repairs. The baseline was the saved evidence-focused arm in the
[previous comparison](../text-validation-comparison/README.md); it was not rerun.
Each model call received only patient text and the extraction instructions/schema.
Questionnaire arrays remained empty. Reference answers were used only for scoring.

All ten model calls returned schema-valid candidate batches. Seven reports then
passed normalization; three failed deterministic field/provenance checks. These
are model-output failures caught by the pipeline, not API connectivity failures.

## Results

| Check | Saved evidence prompt | New grouping prompt |
|---|---:|---:|
| Reports completing the full pipeline | 10/10 | **7/10** |
| Whole reports correct, including structure and evidence | **8/10** | **7/10** |
| Emitted candidates / expected observations | 17 / 15 | 15 / 15 |
| Accepted normalized observations | 17 | 9 |
| Extra / missing normalized observations | 2 / 0 | **0 / 6** |
| Exact contiguous source quotes | 17/17 | **13/15** |
| Valid, complete supporting evidence | 17/17 | **12/15** |
| Automatic candidate fields, with quote-overlap matching | 161/165 | 142/165 |
| Direct unique-candidate semantic fields | 143/165 | 164/165 |
| Known normalized core fields | 85/89 | 54/89 |
| Null normalized core fields | 46/46 | 27/46 |

Fifteen candidates do not establish complete extraction: candidate contents and
source provenance must also be valid. The direct diagnostic shows that grouping
and field assignment mostly improved, but it deliberately does not excuse invalid
quotes. The full-pipeline results are worse. Failed reports remain in all relevant
reference denominators; their valid companion candidates were not selectively
salvaged to inflate downstream metrics.

The normalized observation precision/recall/F1 change from 88.2%/100%/93.8% to
100%/60%/75%. Precision alone looks better because rejected reports produce no
accepted observations; recall and whole-report outcomes reveal the loss.

## Per-report outcome

| Report | Saved evidence prompt | Grouping prompt |
|---|---|---|
| TV001 | Pass | Pass; `time_text` is unnecessarily long but source-exact |
| TV002 | Pass | Pass |
| TV003 | Fail: count and score split | **Pass: count 1 and score 3/5 in one record** |
| TV004 | Pass | Pass |
| TV005 | Pass | Pass |
| TV006 | Fail: count and score split | **Fail: grouped fields, but noncontiguous quote** |
| TV007 | Pass | **Fail: noncontiguous nausea quote** |
| TV008 | Pass | Pass |
| TV009 | Pass | Pass |
| TV010 | Pass | **Fail: invalid nausea count scope** |

TV003 improves; TV007 and TV010 regress. TV006 remains a failure, although the
failure mechanism changes. No incorrect non-null count or severity number,
cross-symptom rating transfer, invented date, clock, or medication relation was
found in the emitted candidates.

## Why the three reports fail

### TV006: correct combined values, invalid evidence

The source contains three sentences in this order:

> I’ve vomited 4 times so far today. I’ve had nausea today up to now, and my worst nausea severity today up to now is 1 out of 5. The worst vomiting severity so far today is 3 out of 5.

The model correctly combines vomiting count 4 and severity 3, but returns:

> I’ve vomited 4 times so far today. The worst vomiting severity so far today is 3 out of 5.

It deleted the intervening nausea sentence and joined nonadjacent fragments.
That string is not an exact contiguous substring of the source. The unchanged
normalizer rejects it. The grouping prompt explicitly prohibited this, so this
is an instruction-following failure, not permission to change the evidence rule.

### TV007: the same stitching error for nausea

The retained quote is:

> I’ve had nausea today up to now. My nausea is 5 out of 5 at its worst so far today.

The actual source has a vomiting sentence between those two sentences. The model
again joins nonadjacent text. A full source span, or the independently sufficient
final nausea sentence, would have been valid; neither was retained here.

### TV010: count scope transferred to a symptom that has no count

The nausea candidate contains `count_scope="day_to_date"`, but this contract
requires nausea `count` and `count_scope` to be null. Its daily severity context
does not establish an episode-count scope. The vomiting candidate correctly
retains its unknown cumulative count and known score; it does not repair the
invalid nausea field. The normalizer rejects the report.

The pipeline treats each report atomically at this stage. Each rejected report
contains two expected observations, producing six missing normalized observations
in total. All raw candidates and failure records remain available for inspection.

## How the diagnostics differ

The predeclared direct diagnostic compares the 11 semantic fields of a uniquely
matched symptom candidate, including retained candidates on normalization errors.
It finds **164/165**: TV010 nausea's count scope is the sole wrong semantic field.

The unchanged automatic evaluator additionally uses reference-quote overlap for
matching. TV006 vomiting and TV007 nausea have noncontiguous quotes and therefore
fail to align, losing 11 checks each. Combined with the count-scope error, its
score is **142/165**. These are different diagnostics, not competing estimates
of overall patient-level accuracy. Complete-report acceptance remains 7/10.

Exact normalized `time_text` agreement is 4/15, compared with 8/15 previously.
Six references have no accepted observation because their reports failed; five
accepted observations use a different source span. The latter preserve compatible
today timing. TV001's long phrase is awkward but source-exact and not a semantic
date error. Failed evidence and invalid scope are assessed separately.

## Verification and saved artifacts

- [protocol.json](protocol.json): fixed scope, model, hashes, and review rules.
- [predictions.jsonl](predictions.jsonl): all ten actual raw responses, candidates,
  accepted observations or failures, response IDs, and usage metadata.
- [metrics.json](metrics.json): unchanged automatic evaluator output.
- [review.json](review.json): independent source-based review, invalid evidence,
  the field error, timing diagnostics, and offline failure reproduction.
- [summary.json](summary.json) and [comparison.json](comparison.json): current
  totals, saved-baseline comparison, per-report outcomes, and fingerprints.

Checks confirmed ten new distinct response IDs, exact agreement between saved
assistant JSON and candidates, reproducible metrics, and unchanged source,
reference, runtime, old prompts, and previous-result hashes. Offline replay with
the unchanged normalizer reproduced all seven accepted outputs and all three
failures. The review was performed by the main agent and a separate reviewing
agent; it is not independent human clinical annotation. No runtime code changed.

This run used 25,217 input and 1,670 output tokens, 26,887 total. The saved evidence
run used 22,738 total tokens. The expanded prompt adds overhead without improving
whole-report correctness in this run.

## Decision and limits

Keep this as a documented unsuccessful overall experiment. The saved
evidence-focused prompt remains the better comparison result on these cases;
the repository default and dashboard are unchanged. The targeted fragmentation
problem improved, but this candidate is not ready to replace the earlier option.

A next bounded revision could shorten the added grouping instructions, anchor
count grouping specifically to vomiting, and reinforce that grouping fields never
permits joining disconnected evidence fragments. That revision has not been made
or run here. A single run does not establish which wording caused each regression.

These are ten controlled, AI-assisted synthetic cases already used for tuning,
with one attempt per prompt. They contain no distinct-date/window/medication
negative controls, so no broad protection against inappropriate merging has been
demonstrated. Further tuning requires fresh cases for an independent evaluation.
