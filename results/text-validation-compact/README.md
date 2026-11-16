# Compact vomiting-grouping prompt: comparison and diagnosis

**The compact prompt passes 8/10 complete reports: better than the previous
grouping run's 7/10, but tied with the saved evidence-focused run's 8/10.**
It repairs vomiting grouping, continuous quotations, and nausea count scope.
Two nausea duplicates remain, in TV007 and TV009, so this is not a clean overall
improvement. The candidate is not promoted to the default prompt.

## Why the earlier results appeared to worsen

On these same ten reports, complete passes were **2/10 → 8/10 → 7/10** before this
run. The evidence instructions improved quote support; the longer grouping block
then improved candidate grouping while introducing two stitched quotes and one
invalid nausea scope. Three whole-report rejections removed six downstream
observations. No model weights, model version, reference answers, or runtime changed.

The broad phrase about a symptom's cumulative count could have blurred a
vomiting-only rule, and combining facts was accompanied by joining quote fragments.
These are plausible mechanisms consistent with the outputs, not proven causes.
One attempt per prompt does not establish that prompt length caused the failures.

## Bounded change and setup

The [compact prompt](../../prompts/extraction_grouping_compact.txt) starts from the
evidence prompt, clarifies one separation sentence, and adds four focused rules:

- Combine vomiting count and worst-so-far rating only within the same interval.
- Preserve distinct contexts and conflicting claims; never add counts.
- Keep nausea `count` and `count_scope` null, including daily nausea ratings.
- Copy one uninterrupted source slice, including all intervening characters.

The added block, including its heading, shrinks from **326 to 146 words**; the full
prompt shrinks from 1,106 to 926. These are whitespace word counts, not tokenizer
counts. Existing field definitions and evidence rules are unchanged. This changes
length, specificity, and copying instructions together, so their effects cannot
be separated by this experiment.

The [protocol](protocol.json) was frozen before ten actual new calls: one per
report with `gpt-5.4-mini-2026-03-17`, reasoning effort `none`, and a 2,048-output-token
limit. The same texts, labels, runtime, evaluator, and review rules were used.
Only text and extraction instructions/schema entered the model; questionnaires
were empty. Both comparators are saved runs, with no API reruns, retries, or output
repairs. These ten synthetic cases are already known development/regression data.

## Observed results

| Check | Saved evidence | Saved long grouping | Compact grouping |
|---|---:|---:|---:|
| Reports completing the pipeline | 10/10 | 7/10 | 10/10 |
| Complete reports including evidence and structure | 8/10 | 7/10 | **8/10** |
| Emitted candidates / expected observations | 17 / 15 | 15 / 15 | **17 / 15** |
| Accepted normalized observations | 17 | 9 | **17** |
| Valid contiguous evidence supporting populated claims | 17/17 | 12/15 | **17/17** |
| Automatic candidate-field checks | 161/165 | 142/165 | 154/165 |
| Strict unique-candidate field diagnostic | 143/165 | 164/165 | 143/165 |
| Normalized core fields | 131/135 | 81/135 | 126/135 |

All 17 compact-run quotes are exact continuous source spans supporting their
populated claims. This does not excuse omitted ratings or duplicate records.
The unscored nausea candidates in TV007/TV009 remain extraction-completeness
defects. There are 13 uniquely matched complete reference groups out of 15.

| Report | Compact outcome | What changed |
|---|---|---|
| TV003 | Pass | Vomiting count 1 and severity 3/5 are together with both sentences |
| TV006 | Pass | Count 4 and severity 3/5 are together; intervening nausea text is retained |
| TV007 | Fail | Quotes are valid, but nausea appears as unscored and scored records |
| TV009 | Fail | Two nausea records use identical evidence but different severity fields |
| TV010 | Pass | Nausea count/scope are null; unknown vomiting count and known score remain |

TV001, TV002, TV004, TV005, and TV008 also pass. Relative to the evidence run,
TV003/TV006 improve and TV007/TV009 regress. Relative to long grouping,
TV006/TV010 improve, TV009 regresses, and TV007 fails for a changed reason.

## Why the nausea duplicates survive normalization

The [diagnosis record](diagnosis.json) confirms two interacting defects:

1. The model emits a nausea occurrence candidate with null severity, plus a
   nausea candidate carrying the daily rating, for the same report context.
2. The occurrence-only candidate has `severity_context=null` and
   `time_text="today up to now"`. The fallback nausea compatibility gate in
   [normalization.py](../../src/normalization.py) excludes the bare word `now`.
   The rated candidate passes an earlier `worst_today_so_far` branch. Only the
   latter enters daily grouping; the unscored record remains separate.

Exact-object deduplication cannot remove the pair because its fields differ.
This is a confirmed handling gap for these explicit cumulative phrases, not a
reason to merge every same-day nausea claim. A genuinely current-only statement
still needs to remain distinct from a daily summary.

TV009 then creates a scoring ambiguity: both nausea records have identical quotes,
but one has severity null and the other 3. The frozen evaluator cannot uniquely
align the reference without selecting a candidate by the answer being graded.
It correctly preserves the ambiguity instead of choosing the scored duplicate.

Consequently, automatic observation matching reports **14 matched, 3 extra, and
1 missing**, although the output contains 17 records against 15 expected. TV007
contributes one extra; TV009 contributes two extras and an unmatched reference.
The automatic candidate score is 154/165 because TV009's 11 checks are unmatched.
The stricter unique-candidate diagnostic gives neither duplicated nausea group
credit, yielding 143/165. All uniquely matched groups have correct declared values.

Normalized core scores are 84/89 known and 42/46 null fields. Exact `time_text`
agreement is 8/15: six differences preserve compatible source timing, and one
reference is unmatched. TV001 includes a trailing comma; it is source-exact and
does not change the date meaning. The genuine TV010 `count_unknown` issue is retained.

## Severity and targeted next step

This is a **moderate data-quality defect** worth resolving before expanding the
new text outputs. It leaves extra symptom rows and affects observation counts
and evaluation. It is not an observed increase in the numerical daily severity:
the existing [daily severity aggregation](../../src/aggregation.py) excludes null
scores and uses supported known values, so a null-score duplicate does not add to
the valid 5/5 or 3/5 score. That conclusion comes from code inspection; no dashboard
rebuild or deployment was performed in this experiment.

A separate narrow normalization change should recognize explicit cumulative-today
phrases without treating `right now`, morning-only, or other distinct contexts
as daily summaries. Any duplicate/subsumption policy must require compatible
report, symptom, assertion, context, values, and evidence, retain raw candidates,
and preserve conflicts rather than select a preferred score.

Before accepting such a change, test current-versus-daily and morning-versus-daily
claims, different dates/clocks, medication-specific contexts, differing assertions,
and conflicting known ratings. Replay these saved outputs offline and report raw
extraction and normalized metrics separately. Do not rewrite model responses,
relax quote checks, or change matching to hide duplicates. **This runtime remedy
has not been implemented in this run.**

## Artifacts and limits

- [protocol.json](protocol.json): frozen comparison and pre-run analysis.
- [predictions.jsonl](predictions.jsonl): all ten actual model outputs and metadata.
- [metrics.json](metrics.json): unchanged automatic evaluator output.
- [review.json](review.json): per-candidate evidence and timing review.
- [summary.json](summary.json) and [comparison.json](comparison.json): totals,
  comparator outcomes, and provenance.
- [diagnosis.json](diagnosis.json): compatibility-gate findings and proposed controls.

The default prompt, historical outputs, source texts, labels, and runtime remain
unchanged. No new result was selected by retrying. Source-based review was checked
by a separate agent, not independent human clinical annotators. Ten known,
controlled synthetic texts and single attempts do not establish generalization,
stability, or protection against merging genuinely different contexts. There are
no such negative controls in this set, and no default promotion is justified here.

This run used 22,987 input and 1,847 output tokens (24,834 total), versus 26,887
total for the long grouping run and 22,738 for the saved evidence run.
