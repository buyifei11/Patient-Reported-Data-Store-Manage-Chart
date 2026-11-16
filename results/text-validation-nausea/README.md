# Daily nausea: separate Python and prompt experiments

**Keep the Python fix. Keep the new prompt experimental.** Offline replay repairs
TV007 and TV009 without changing the model's saved output. The subsequent prompt
run removes duplicate candidates but produces a noncontiguous quote in TV007,
which correctly fails validation. No retries, reference-assisted repairs, model
fine-tuning, or dashboard input replacements were performed.

These are ten known synthetic development/regression reports with 15 expected
observations. Results on them do not measure general accuracy on unseen reports.

## Results at each stage

| Measure | Saved compact prompt | Same output + Python fix | New prompt + fixed Python |
| --- | ---: | ---: | ---: |
| New model requests in this experiment | 0 | 0 | 10 |
| Raw candidates (15 expected) | 17 | 17 | 15 |
| Normalized observations (15 expected) | 17 | 15 | 13 |
| Normalized core fields correct | 126/135 | 135/135 | 117/135 |
| Reports with correct normalized values and structure | 8/10 | 10/10 | 9/10 |
| Direct unique-candidate field checks | 143/165 | 143/165 | 165/165 |
| Existing automatic candidate field checks | 154/165 | 154/165 | 154/165 |
| Valid retained quotes for populated claims | 17/17 | 17/17 | 14/15 |
| Frozen whole-report pass, including raw candidates and evidence | 8/10 | 8/10 | 9/10 |

The two report-level scores answer different questions. Python replay makes all
ten normalized reports correct, but the original raw duplicate candidates remain
visible and still fail the stricter whole-report rule. New-prompt candidate
values are correct, yet one quote is invalid; the daily pipeline therefore
cannot use that report. A value-only score of 165/165 is not perfect extraction.

The automatic evaluator requires source-supported quote alignment. It cannot
match the new TV007 nausea candidate because its quote is not a source substring.
The separate, predeclared direct-value diagnostic compares a symptom only when
exactly one candidate exists; it reveals correct values without excusing invalid
evidence. Original automatic metrics and their denominators remain unchanged.
Equivalent literal timing spans are reviewed separately from the nine normalized
core fields. All failed reports remain in the denominator.

## Step 1: deterministic repair

Previously, the unscored nausea compatibility gate treated every `now` as a
current-only observation. Thus `today up to now` failed to join a compatible
daily-worst rating. The fix masks only explicit `today ... now` cumulative
phrases in a temporary comparison string and checks remaining qualifiers.
It does not rewrite the original candidate, quoted evidence, or timing text.

The saved TV007 and TV009 candidates now yield one nausea observation each,
retaining the union of their evidence. These are the only changed reports in
the ten-report replay. All original candidates, raw responses, and extraction
metadata are preserved. A separate `normalization_replay` field identifies the
new runtime; original response IDs and token usage do not represent new calls.

Eight new test methods cover cumulative phrasing, questionnaire reconciliation,
current ratings, morning/narrower cutoffs, different dates, clock times,
medication relations, conflicting ratings/assertions, and both saved failures.
The focused suite passed 57 tests; the full offline suite passed 236 tests.
An independent read-only review found no blocking issue.

"Right now 1/5" and "worst today 3/5" stay separate. The current score remains
in the raw candidate and evidence; normalized daily severity is null with
`unsupported_severity_context` for that current-only observation. Two conflicting
daily-worst ratings retain the existing conflict policy: one unresolved daily
observation, null severity, `conflicting_sources`, and all evidence. Neither
rating becomes a usable selected value.

This is a narrow compatibility fix, not universal semantic verification. The
pre-existing branch for a candidate already labeled `worst_today_so_far` still
trusts that model-provided context; contradictory contexts require separate work.

## Step 2: one prompt rule

The [new prompt](../../prompts/extraction_nausea_grouping.txt) adds exactly one
29-word bullet to the compact prompt:

> For nausea, combine an occurrence description and a worst-so-far-today rating into one complete candidate when they cover the same interval; do not add a separate unscored occurrence candidate.

Both comparison arms use the fixed Python runtime. The model remains
`gpt-5.4-mini-2026-03-17`, reasoning effort `none`, maximum output 2,048 tokens.
Ten requests ran once each in source order. Only patient text enters each
stateless extraction request. Sources, references, model settings, scoring
criteria, other prompt instructions, and the default prompt are unchanged.
The ten calls used 23,377 input and 1,692 output tokens (25,069 total).

TV007 contains three sentences: nausea occurrence, vomiting count/rating, then
nausea rating. The new model output quotes sentence 1 followed directly by
sentence 3, deleting sentence 2. This is not one continuous source substring.
The existing report-level rejection policy consequently withholds both of that
report's normalized observations, while preserving both raw candidates and the
exact model response. The other nine reports pass. TV006 and TV008 have some
wider-than-necessary quotes, but they remain continuous and support their claims.

The observed tradeoff is fewer duplicates and one evidence regression. With
one saved baseline and one new attempt, this does not prove that the additional
instruction causes the regression or reliably reduces duplicates. Prefer the
fixed Python handling of the saved compact output for this comparison; do not
promote the new prompt based on this run. The project's default
`prompts/extraction.txt` remains unchanged.

## Audit files and reproduction

- [protocol.json](protocol.json): frozen before Python changes; hashes original data, code, and comparator artifacts.
- [python-replay/](python-replay/): replayed predictions, metrics, before/after changes, and zero-call summary.
- [prompt/protocol.json](prompt/protocol.json): fixed runtime and new prompt frozen before calls.
- [prompt/predictions.jsonl](prompt/predictions.jsonl): all ten responses, including the failure.
- [prompt/review.json](prompt/review.json): source/evidence review independently checked for every candidate.
- [comparison.json](comparison.json): all three stages and artifact hashes.

Replay offline into a new directory (never overwrite the saved experiment):

```bash
python scripts/replay_daily_nausea.py --output artifacts/nausea-replay
```

Recalculate saved model-output metrics without any API request:

```bash
python run_pipeline.py evaluate \
  --source data/text_validation/reports.jsonl \
  --gold data/text_validation/expected.jsonl \
  --predictions results/text-validation-nausea/prompt/predictions.jsonl \
  --output artifacts/nausea-prompt-metrics.json
```

The replay checks the frozen inputs and all original runtime modules except the
intentionally revised normalizer. Its current runtime hash is recorded. It
never reads gold to modify candidates or normalization; gold is used only for
scoring after processing.
