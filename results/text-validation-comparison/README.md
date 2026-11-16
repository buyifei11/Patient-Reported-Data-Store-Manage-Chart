# Ten-report validation: original versus evidence-focused prompt

**The evidence-focused prompt improved quote support and whole-report quality in
this run, but did not achieve complete extraction correctness.** Whole reports
passing the frozen checks increased from **2/10 to 8/10**. All 17 quotes emitted
by the candidate support their own claims, but two reports still split a single
daily symptom observation into separate count and severity records.

TV003 remains fragmented in both runs. TV006 newly fragments with the candidate,
while TV001's fragmentation is resolved. The record-structure regression in TV006
must remain visible alongside the evidence improvement. Neither prompt nor the
runtime was changed after inspecting these results.

## Controlled comparison

- Ten newly authored [reviewed validation texts](../../data/text_validation/README.md),
  15 expected symptom observations, and 165 declared candidate-field expectations.
- Both prompts were frozen before these texts were generated. Sources and labels
  were reviewed before extraction and remained unchanged throughout this comparison.
- Same model: `gpt-5.4-mini-2026-03-17`, reasoning effort `none`, strict structured
  output, maximum 2,048 output tokens per request, and the same current runtime.
- Original prompt: `prompts/extraction.txt`. Candidate:
  `prompts/extraction_evidence.txt`, which adds a general evidence-completeness block.
- Twenty actual extraction requests: one per report per prompt. Each arm ran in
  source order; the independent arms ran concurrently. No failures or retries.
- Each stateless model request received only the patient text and extraction
  instructions/schema. Seeds, references, questionnaires, report metadata, and
  the text-generation conversation were not supplied to the model. The existing
  normalizer used submission metadata and empty questionnaire arrays afterward.
- A [protocol](protocol.json) fixed the metrics, evidence criteria, denominators,
  and additional unique-symptom diagnostic before any extraction call.

## Results and denominators

| Check | Original prompt | Evidence-focused prompt |
|---|---:|---:|
| Completed reports | 10/10 | 10/10 |
| Emitted candidates | 19 | 17 |
| Normalized observations / expected | 17 / 15 | 17 / 15 |
| Matched / extra / missing observations | 15 / 2 / 0 | 15 / 2 / 0 |
| Observation precision / recall / F1 | 88.2% / 100% / 93.8% | 88.2% / 100% / 93.8% |
| Automatic candidate-field checks, using evidence-overlap matching | 150/165 | 161/165 |
| Whole candidate checks passing the automatic evaluator | 12/15 | 13/15 |
| Known normalized core fields | 85/89 | 85/89 |
| Null normalized core fields | 46/46 | 46/46 |
| Quotes that are exact source substrings | 19/19 | 17/17 |
| Quotes supporting their own emitted claims | **13/19** | **17/17** |
| Reference observations with exactly one candidate, complete values, and complete evidence | 7/15 | 13/15 |
| Whole reports passing all frozen requirements | **2/10** | **8/10** |
| Exact `time_text` equality, diagnostic only | 5/15 | 8/15 |

The quoted-evidence denominator is the number of actual candidates, which differs
between arms. **17/17 supported quotes does not mean 100% extraction accuracy.**
A count-only record can quote its count correctly while omitting a required rating.
The reference-coverage and whole-report checks expose those omissions and fragments.
The normalized core metric also does not penalize extra records by itself; read it
with observation detection and whole-report outcomes.

The core fields are symptom, assertion, count, count scope, severity, event date,
event time, date basis, and medication relation. Scores include many null values;
field totals are not independent patient examples. Both runs have two extra
`count_unknown` issue flags on fragmented severity-only vomiting records, while
correctly retaining TV010's genuinely unknown count.

All observed `time_text` differences are compatible source phrases such as
"today", "so far today", and "today up to now". Their date meaning is preserved.
They are recorded separately; they do not excuse missing count, severity, or
evidence. Evidence support was reviewed against source text by the main agent and
a separate agent, not scored solely by substring matching or clinical reviewers.

## Case-by-case result

| Report | Original prompt | Evidence-focused prompt |
|---|---|---|
| TV001 | Fail: count and score split into two records | Pass: count 3 and score 1/5 combined with full evidence |
| TV002 | Pass | Pass |
| TV003 | Fail: count and score split | Fail: same split remains |
| TV004 | Fail: duplicate candidates; one quote omits count evidence | Pass: count 2 and score 4/5 combined with full evidence |
| TV005 | Fail: duplicate candidates; one quote omits rating evidence | Pass: one complete nausea candidate |
| TV006 | Fail: vomiting quote omits rating evidence | Fail: quotes now supported, but count and score split |
| TV007 | Fail: nausea quote omits rating evidence | Pass: correct values and complete evidence |
| TV008 | Fail: vomiting quote omits rating evidence | Pass: the quote spans the parenthetical aside |
| TV009 | Pass | Pass |
| TV010 | Fail: vomiting quote omits rating evidence | Pass: unknown count and known rating both supported |

Whole-report success requires completion, no missing/extra observations or
candidates, correct candidate fields and normalized core fields, matching issue
flags, and complete exact-source evidence. Exact time-phrase boundaries are a
separate diagnostic. The rule was fixed before either run.

## A repaired quote: TV010

Both runs correctly extract present vomiting, unknown cumulative count, and a
worst-so-far-today score of 4/5. The original retains only:

> I’ve vomited today up to now, but the cumulative count is unknown.

The candidate retains:

> I’ve vomited today up to now, but the cumulative count is unknown. The worst vomiting severity so far today is 4 out of 5.

The second sentence supplies the rating, scale, and context already claimed by
the original candidate. The new quote is actual model output, not a reviewer edit.
All six unsupported original quotes and their affected fields are listed in
[review.json](review.json).

## Remaining defect: complementary facts become separate records

For TV003, both prompts emit vomiting candidates equivalent to:

| Candidate | Count | Count scope | Severity | What its quote supports |
|---|---:|---|---:|---|
| First | 1 | `day_to_date` | null | Today's cumulative count |
| Second | null | null | 3/5 | Today's worst vomiting score |

The reference is one daily vomiting observation containing count 1 and severity 3.
The numbers are present across the two candidates, but no single candidate has
both. The existing normalizer's vomiting merge gate requires `day_to_date`; the
severity-only candidate has null count scope, so it stays separate and acquires
an inappropriate `count_unknown` issue. TV006's candidate run has the same problem
with count 4 and severity 3/5. No value was repaired using the references.

The current prompt stresses keeping distinct symptom/time contexts separate.
Its evidence extension says what to do **if** one candidate uses multiple sentences,
but does not clearly require complementary facts about the same daily symptom
context to form one candidate. This is a plausible instruction gap to examine;
these single runs do not prove a unique cause of the output variation.

## Keep alignment artifacts separate from field errors

The unchanged evaluator aligns candidates by symptom and quote overlap. In the
original TV007 output, nausea's 11 semantic values are correct, but its early
quote does not overlap the reference's final-sentence quote. The raw evaluator
therefore marks all 11 checks unmatched. That is an evidence/alignment failure,
not 11 invented field values.

A separate reviewer identified this possibility before extraction. The frozen
protocol adds a direct diagnostic: compare fields only if exactly one candidate
exists for the expected symptom. Missing or ambiguous groups receive no credit;
the scorer never chooses whichever candidate has the best answers.

| Direct diagnostic | Original | Evidence-focused |
|---|---:|---:|
| Uniquely matched symptom groups | 11/15 | 13/15 |
| Field checks correct under this strict rule | 121/165 | 143/165 |
| Ambiguous groups | TV001, TV003, TV004, TV005 | TV003, TV006 |

Every uniquely matched candidate has the correct 11 semantic values. The lower
direct totals reflect entire ambiguous groups receiving no credit; they are not
counts of numerically false claims. Both diagnostics and every mismatch remain
in the saved results. The automatic evaluator's historical `development_fixtures`
labels are also preserved; the protocol records this set's actual role as fresh
targeted synthetic validation at run time.

## Saved files, verification, and next step

- [protocol.json](protocol.json): frozen configuration and review rules.
- [baseline/predictions.jsonl](baseline/predictions.jsonl) and
  [evidence/predictions.jsonl](evidence/predictions.jsonl): actual candidates,
  raw assistant JSON, normalized observations, response IDs, and usage metadata.
- [baseline/metrics.json](baseline/metrics.json) and
  [evidence/metrics.json](evidence/metrics.json): unchanged evaluator output.
- [review.json](review.json): every emitted quote reviewed, timing differences,
  the persistent split, and the TV006 regression.
- [summary.json](summary.json): comparison totals, direct diagnostic, per-report
  decisions, and file fingerprints.

Verification confirmed 20 distinct response IDs, exact agreement between saved
raw assistant responses and candidates, reproducible automatic metrics, and
unchanged source/reference/prompt/runtime hashes. No extraction output was edited.
The original used 18,677 input + 1,810 output tokens (20,487 total); the candidate
used 20,897 + 1,841 (22,738 total). Total extraction usage was 43,225 tokens.

Automatic evaluation can be reproduced offline for either arm using a new output
path, for example:

```bash
python run_pipeline.py evaluate \
  --source data/text_validation/reports.jsonl \
  --gold data/text_validation/expected.jsonl \
  --predictions results/text-validation-comparison/evidence/predictions.jsonl \
  --output work/text-validation-evidence-metrics.json
```

The evidence-focused prompt is a useful direction, with an observed structure
regression and a persistent split still unresolved. The next bounded experiment
should clarify when complementary same-symptom, same-context facts belong together,
while retaining separation across genuinely different dates, windows, assertions,
or medication contexts. It should not indiscriminately merge all same-day records.
This comparison does not implement that change, replace the default prompt, or
rebuild the dashboard.

There are only ten controlled synthetic reports and one attempt per prompt per
report. The text generator and extractor share a model family; labels and review
are AI-assisted, not independent human clinical annotations. These results do not
estimate real-patient accuracy or sampling variability. If used for further prompt
tuning, the ten cases become development/regression material; a later independent
evaluation needs another untouched set.
