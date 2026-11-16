# Twenty fresh text cases: prepared, not extracted

**Status: 20 reviewed source/reference pairs; zero extraction calls.** This set
checks the frozen nausea-grouping prompt and current Python handling on new
synthetic cases. Preparing valid answers is not an extraction accuracy result.

The intended next extraction model is `gpt-5.4-mini-2026-03-17`, using
[`extraction_nausea_grouping.txt`](../../prompts/extraction_nausea_grouping.txt),
reasoning effort `none`, and a 2,048-output-token cap. The selected prompt and
runtime were frozen before text generation in [preparation.json](preparation.json).
This selects an experimental prompt for the next evaluation; it does not change
the CLI default or the dashboard dataset.

## What the counts mean

- **20 reports**: twenty separate fictional submissions, TH001–TH020.
- **31 candidate checks / 341 semantic field expectations**: source claims the model should preserve before normalization.
- **29 normalized observations**: two conflicting pairs are consolidated into one unresolved record per report. TH020 has no target symptoms and correctly has zero records.

These are different levels, not three competing dataset sizes. A single report
may contain several symptoms or several incompatible time contexts for one symptom.

## Files and field meanings

| File | Contents | Extraction input? |
| --- | --- | --- |
| [reports.jsonl](reports.jsonl) | English feedback plus submission metadata | Yes; only `text` enters the LLM |
| [expected.jsonl](expected.jsonl) | Independently authored candidate checks and normalized answers | No; scoring only |
| [seeds.jsonl](seeds.jsonl) | Fictional facts, scenario groups, and writing instructions used for generation | No |
| [editorial_review.json](editorial_review.json) | Eight disclosed pre-extraction edits, with original and final text | No |
| [preparation.json](preparation.json) | Frozen model/prompt/runtime and future evaluation rules | No |
| [review.md](review.md) | Source/label review, checks, limitations, and fingerprints | No |
| [Generation record](../../results/text-holdout-generation/) | One real generation request, raw response, texts, usage, and provenance | No |

Each JSONL line is one report. `report_id` links its text, seed, and answer;
`patient_id` is a fictional patient identifier. `reported_at` and `patient_timezone`
let Python resolve today/yesterday; they do not identify when a symptom occurred.
Every `questionnaire_answers` array is empty, so structured answers cannot silently
supply a field missed by extraction. `supersedes_report_id` is null throughout;
this set does not test correction chains.

The answer has two parts. `extraction_checks` identifies a supporting source
excerpt and the expected semantic candidate fields: symptom, assertion, count,
count scope, raw rating/scale/context, day reference, explicit date, exact clock,
and medication relation. `observations` specifies the final normalized records:
resolved date, eligible daily severity, original supporting evidence, and issues
such as unsupported scale or a conflict. Quotes and `time_text` need not use the
same boundaries as the reference if their content supports the same claim.

A current 2/5 rating can be extracted correctly while becoming normalized daily
severity null. The null means that this is not a daily-worst value, not that the
patient supplied no rating. The original candidate and source evidence retain it.

## Case map

| Report | Focus | Expected behavior |
| --- | --- | --- |
| TH001 | Ordinary vomiting | One vomiting record: today-to-submission count 2, worst severity 3/5. No nausea record. |
| TH002 | Ordinary nausea | One nausea record: worst severity 1/5 today so far. The occurrence and rating belong together; nausea count and scope are null. |
| TH003 | Keep symptom values separate | Two records: nausea 4/5; vomiting count 3 and worst severity 2/5. Do not exchange the ratings. |
| TH004 | Zero versus unmentioned | One absent vomiting record with count 0. Nausea is unmentioned, so there is no nausea record. |
| TH005 | Unknown is not zero | Vomiting is present with count null and worst severity 2/5; flag count_unknown. Nausea worst severity is 3/5. |
| TH006 | No rating supplied | One present nausea record. Severity is null because no number was stated; do not invent a score or a missing-score issue. |
| TH007 | Rating before count | One vomiting record: count 1 and worst severity 4/5 today so far, despite the reversed sentence order. |
| TH008 | Interleaved vomiting facts | Two records: vomiting count 4 and worst severity 5/5; nausea worst severity 2/5. The intervening nausea sentence does not split the vomiting facts. |
| TH009 | Interleaved nausea facts | Two records: nausea worst severity 3/5; vomiting count 1 and worst severity 2/5. Do not add an unscored nausea duplicate. |
| TH010 | Two explicit denials | Two absent records: vomiting count 0 and nausea count null. Both severities are null. Nausea has no episode-count field. |
| TH011 | Current versus daily worst | Two nausea candidates: current 2/5 and worst today 4/5. Preserve both contexts. The current score remains in the candidate/evidence; its normalized daily severity is null with unsupported_severity_context. The daily record has severity 4. |
| TH012 | Morning versus daily worst | Two nausea candidates: morning 2/5 and worst today 4/5. Morning severity is not a daily-worst measure: normalized severity null with unsupported_severity_context. Keep the daily score 4 separately. |
| TH013 | Yesterday versus today | Two vomiting records: the complete total on 2026-11-09 is 1 with day_total; the partial cumulative value on 2026-11-10 is 2 with day_to_date. No ratings are supplied. |
| TH014 | Clock event versus daily count | Two vomiting records on 2026-11-11: one episode at 08:10 with event scope; cumulative count 3 with day_to_date scope and no invented event clock. Do not add these into 4. |
| TH015 | Medication relation belongs to one symptom | Morning nausea retains Medication B / after_taking and no invented clock. Separately, vomiting count is 2 and worst severity is 3/5 today so far; it receives no medication relation. Timing does not establish causation. |
| TH016 | Conflicting daily ratings | Two raw nausea candidates preserve 2/5 and 4/5 for the same daily-worst window. One normalized nausea record remains present with severity null, conflicting_sources on severity, and both evidence spans. Do not choose or average. |
| TH017 | Conflicting daily counts | Two raw vomiting candidates preserve counts 2 and 5 for the same cutoff. One normalized record remains present with count null and conflicting_sources on count. This is a conflict, not a missing count or an update to sum. |
| TH018 | Different rating scale | Raw nausea rating remains 7 out of 10, worst today so far. Normalized severity is null with unsupported_scale; do not convert 7/10 into a five-point value. |
| TH019 | Meal does not supply a date | Vomiting count 1 has window scope after lunch. event_date is null with date_unknown, despite a known submission date. No clock or severity is supplied. |
| TH020 | No target symptom | No nausea or vomiting is mentioned. Correct candidates and observations are empty arrays; do not fabricate symptom absence. |

## Preparation and future evaluation boundary

One generation request produced all twenty texts. Twelve were accepted verbatim;
eight received documented edits before label authoring or extraction. Most edits
restore a missing day/worst-rating anchor or make each conflicting claim explicit;
TH019 removes an unnatural phrase while leaving the date unknown. No numeric seed
fact was changed. No report was discarded or regenerated based on model performance.
The raw generation remains available.

A separate agent authored references from the final texts and written data contract;
another agent reviewed sources and labels. Neither extraction nor normalization
was run to manufacture the expected answers. Schema/provenance validation is an
offline data check, not a model test. See [review.md](review.md) for the record.

For the later run, keep this source/reference pair and the extraction setup frozen.
Run every report once, keep failures, and report both automatic results and any
separately reviewed acceptance. A source-verified harmless quotation omission is
an evidence-format exception, not automatically a factual extraction error. Any
exception still retains its original output and review provenance. Wrong values,
negation, dates, symptom attribution, or unresolved conflicts cannot be ignored
as formatting. Do not change the answers to match model output.

This is a small targeted synthetic validation set with broader semantic coverage,
not independently sampled patient data or a final clinical benchmark. Much wording
still repeats “today so far”; generation and extraction use the same model family.
It omits correction chains, multi-day allocation, timezone boundaries, and hypothetical
reports. If its results are used to tune the prompt/runtime, reclassify it as
known development/regression data before making further generalization claims.

## Read each report with its answer

### TH001: Ordinary vomiting

> I’ve vomited two times today so far, and the worst today has been 3 out of 5.

One vomiting record: today-to-submission count 2, worst severity 3/5. No nausea record.

### TH002: Ordinary nausea

> I’ve had nausea today so far. The worst it’s been today is 1 out of 5.

One nausea record: worst severity 1/5 today so far. The occurrence and rating belong together; nausea count and scope are null.

### TH003: Keep symptom values separate

> I’ve had nausea today, and the worst today so far is 4 out of 5. I’ve vomited three times today so far, with the worst vomiting today so far at 2 out of 5.

Two records: nausea 4/5; vomiting count 3 and worst severity 2/5. Do not exchange the ratings.

### TH004: Zero versus unmentioned

> I haven’t vomited today so far.

One absent vomiting record with count 0. Nausea is unmentioned, so there is no nausea record.

### TH005: Unknown is not zero

> I’ve vomited today so far, but I can’t recall the number. The worst vomiting today so far has been 2 out of 5. I’ve also had nausea today so far, and the worst nausea today so far has been 3 out of 5.

Vomiting is present with count null and worst severity 2/5; flag count_unknown. Nausea worst severity is 3/5.

### TH006: No rating supplied

> I’ve had nausea today so far.

One present nausea record. Severity is null because no number was stated; do not invent a score or a missing-score issue.

### TH007: Rating before count

> My worst vomiting today so far is 4 out of 5. I’ve thrown up once today so far.

One vomiting record: count 1 and worst severity 4/5 today so far, despite the reversed sentence order.

### TH008: Interleaved vomiting facts

> I’ve vomited four times today so far. My worst nausea today so far has been 2 out of 5. The worst vomiting today so far is 5 out of 5.

Two records: vomiting count 4 and worst severity 5/5; nausea worst severity 2/5. The intervening nausea sentence does not split the vomiting facts.

### TH009: Interleaved nausea facts

> I’ve had nausea today so far. I’ve vomited once today so far, and the worst vomiting today so far is 2 out of 5. The worst nausea today so far is 3 out of 5.

Two records: nausea worst severity 3/5; vomiting count 1 and worst severity 2/5. Do not add an unscored nausea duplicate.

### TH010: Two explicit denials

> I haven’t vomited today so far, and I haven’t had nausea today so far.

Two absent records: vomiting count 0 and nausea count null. Both severities are null. Nausea has no episode-count field.

### TH011: Current versus daily worst

> Today my nausea is 2 out of 5 right now. The worst nausea today so far has been 4 out of 5.

Two nausea candidates: current 2/5 and worst today 4/5. Preserve both contexts. The current score remains in the candidate/evidence; its normalized daily severity is null with unsupported_severity_context. The daily record has severity 4.

### TH012: Morning versus daily worst

> This morning, my nausea was 2 out of 5. The worst nausea today so far has been 4 out of 5.

Two nausea candidates: morning 2/5 and worst today 4/5. Morning severity is not a daily-worst measure: normalized severity null with unsupported_severity_context. Keep the daily score 4 separately.

### TH013: Yesterday versus today

> Yesterday, I vomited once for the whole day. Today so far, I’ve vomited twice.

Two vomiting records: the complete total on 2026-11-09 is 1 with day_total; the partial cumulative value on 2026-11-10 is 2 with day_to_date. No ratings are supplied.

### TH014: Clock event versus daily count

> I vomited once today at 08:10. I’ve vomited three times today so far.

Two vomiting records on 2026-11-11: one episode at 08:10 with event scope; cumulative count 3 with day_to_date scope and no invented event clock. Do not add these into 4.

### TH015: Medication relation belongs to one symptom

> This morning, I had nausea after taking Medication B. I’ve vomited twice today so far, and the worst vomiting today so far is 3 out of 5.

Morning nausea retains Medication B / after_taking and no invented clock. Separately, vomiting count is 2 and worst severity is 3/5 today so far; it receives no medication relation. Timing does not establish causation.

### TH016: Conflicting daily ratings

> One note says, "My worst nausea today so far was 2 out of 5." The other says, "My worst nausea today so far was 4 out of 5." Both cover the same period, and I can’t confirm which score is right.

Two raw nausea candidates preserve 2/5 and 4/5 for the same daily-worst window. One normalized nausea record remains present with severity null, conflicting_sources on severity, and both evidence spans. Do not choose or average.

### TH017: Conflicting daily counts

> One entry says, "I’ve vomited twice today so far." Another says, "I’ve vomited five times today so far." Both refer to the same cutoff, and I can’t confirm the number.

Two raw vomiting candidates preserve counts 2 and 5 for the same cutoff. One normalized record remains present with count null and conflicting_sources on count. This is a conflict, not a missing count or an update to sum.

### TH018: Different rating scale

> My worst nausea today so far is 7 out of 10.

Raw nausea rating remains 7 out of 10, worst today so far. Normalized severity is null with unsupported_scale; do not convert 7/10 into a five-point value.

### TH019: Meal does not supply a date

> I vomited once after lunch.

Vomiting count 1 has window scope after lunch. event_date is null with date_unknown, despite a known submission date. No clock or severity is supplied.

### TH020: No target symptom

> I wrote an appointment in a calendar and charged my phone.

No nausea or vomiting is mentioned. Correct candidates and observations are empty arrays; do not fabricate symptom absence.
