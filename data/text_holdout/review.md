# Preparation and independent review record

**Status: prepared and reviewed, not extracted.** No prediction file or accuracy
result has been produced for TH001–TH020. This record is a pre-inference snapshot.

## Frozen setup and generation

- `preparation.json` froze the selected extraction prompt, model settings, runtime,
  review adapter, scenario seeds, and generation prompt before generation.
- The intended extractor is `gpt-5.4-mini-2026-03-17` with
  `prompts/extraction_nausea_grouping.txt`, reasoning `none`, and maximum output
  2,048 tokens. The default prompt, runtime, and dashboard inputs are unchanged.
- One actual generation request used the same pinned model, reasoning `none`,
  strict JSON output, and an 8,192-output-token cap. Usage was 5,751 input and
  709 output tokens (6,460 total). There were no retries.
- The saved generation request contains only the report ID, fictional context,
  facts, layout, and style. It contains no extraction prompt, older report text,
  previous extraction output, reference labels, or authorization headers.
- All twenty generated reports were retained. Twelve remain verbatim; eight
  were edited before label authoring. `editorial_review.json` records every
  original/final text and reason. No numeric seed value changed. No extraction
  outcome was available for selection or editing.

## Separate authorship and review

The root agent designed facts and reviewed the generation. A separate agent
then authored `expected.jsonl` from the final text and written contract. A different
agent independently reviewed every source/reference pair and all edited passages.
The root agent also inspected the final references. No extractor or normalizer
was called to manufacture or assess the labels. Source/schema checks and the
fixture validator's no-prediction provenance checks are not extraction tests.

The independent review found no blocking issue and requested no label changes.
The final source texts, not the original seeds alone, determine the references.

## Verified labels

| Case group | Verified distinction |
| --- | --- |
| TH001–TH003 | Ordinary counts/ratings; correct symptom attribution and daily context |
| TH004–TH006 | Explicit zero, unknown count, unmentioned symptom, and unstated score |
| TH007–TH009 | Reversed or interleaved facts still form complete compatible candidates |
| TH010 | Two explicit absences; nausea count remains inapplicable |
| TH011–TH012 | Current/morning ratings retained in candidates; not eligible daily severity |
| TH013 | Yesterday's completed total and today's cumulative value have separate dates/scopes |
| TH014 | Exact event clock 08:10 and daily cumulative count remain separate; no summing |
| TH015 | Medication relation belongs only to nausea; no causal inference or invented clock |
| TH016–TH017 | Two contradictory raw values survive; normalized value unresolved with both evidence spans |
| TH018 | Preserve 7/10 in the candidate; normalized severity null with unsupported_scale |
| TH019 | After lunch supplies a window, not a calendar date or clock |
| TH020 | No target symptoms means no candidates/observations, not invented absences |

Seven normalized observations carry issues: TH005 `count_unknown`; TH011 and
TH012 `unsupported_severity_context`; TH016 severity `conflicting_sources`;
TH017 count `conflicting_sources`; TH018 `unsupported_scale`; TH019 `date_unknown`.
TH016/TH017 occurrence remains `present`; uncertainty concerns the value only.

The repeated-symptom candidate checks use distinguishable source excerpts. A
reference quote is a supporting span, not the sole acceptable span. Timing-text
boundaries are diagnostic; semantically equivalent source spans can be valid.
A harmless omission may be separately accepted after source review, under the
frozen policy, while original strict metrics and model output remain visible.

## Offline checks and denominators

- 20 strict source records and 20 reference records with matching unique IDs.
- 20 separate fictional patient IDs; no correction chains and no questionnaire answers.
- 31 candidate checks, each covering 11 semantic fields: 341 expectations.
- 29 normalized observations; nine core fields yield 261 expectations (159 known,
  102 null). Conflicts reduce 31 raw claim groups to 29 normalized records.
- 62 reference evidence entries are exact source substrings; all time-text spans
  occur within their retained evidence. Semantic support was separately reviewed.
- No exact or case/punctuation-normalized whole-text duplicate among the twenty
  cases or against 95 older nonempty source rows in existing data folders.
  Shared phrasing and scenario patterns still exist; this is not statistical independence.
- Source metadata and numeric facts agree with seeds, and all eight editorial
  changes match their recorded before/after texts.
- Freeze timestamps predate generation. Runtime, prompt, source, reference, and
  generation provenance fingerprints were verified.

Recheck source/reference integrity without model requests:

```bash
python run_pipeline.py validate \
  --source data/text_holdout/reports.jsonl \
  --gold data/text_holdout/expected.jsonl
```

No runtime code changed, so no new behavioral tests were added for this data-only
preparation. The command above validates fixtures; it does not measure accuracy.

## Limits and next step

This is a small targeted synthetic validation set, not independent human clinical
annotation. It extends semantic coverage but retains controlled, repetitive
wording and uses the same model family for generation and intended extraction.
Correction chains, multi-day allocation, timezone boundaries, and hypothetical
reports are not covered. There is no training or fine-tuning in this step.

Keep the final source, references, selected prompt, runtime, and scoring policy
frozen for a later one-attempt-per-report run. Report automatic processing,
semantic correctness, and any reviewed evidence acceptance separately. Do not
silently edit references, retry poor outputs, or pool these twenty reports into
old development scores. If outcomes inform tuning, relabel this set as known
regression data.

## Reviewed fingerprints

Reviewed at UTC: 2026-11-16T20:17:00.117506+00:00

`manifest.json` records the machine-readable freeze and all input fingerprints.

| File | SHA-256 |
| --- | --- |
| `data/text_holdout/seeds.jsonl` | `4bb071e11d0cfe0b0fefa14fb563c23c437c3b2add188f9f0d4d9a280bea2003` |
| `data/text_holdout/reports.jsonl` | `196882772250d56dca8b7492146ea1f8ce5a638a5ad366b604f5574624a1bdfa` |
| `data/text_holdout/expected.jsonl` | `2527cde89aa32411332505825c7dcb4b3a5bea687c2b8841099d94b484798cd1` |
| `data/text_holdout/editorial_review.json` | `061ace99b5edf0c55e70465663c0bba95fe2977240f68cd4d18fc1c0e2b901c4` |
| `data/text_holdout/preparation.json` | `b2b1264c2e10176b2ed73b6e7975112ea7ccfd1d9f64851ed9650e450072cbbf` |
| `results/text-holdout-generation/request.json` | `0ef4f29694a358db4ce921f00dcb43f1ac42f7a61291fb9014ff8eb7cfcf0bbf` |
| `results/text-holdout-generation/response.json` | `bb2dc39f9008b9be0440c1898f28d0ecb1d9c8742288dd54311d399d9dda8923` |
| `results/text-holdout-generation/generated_texts.jsonl` | `83ed5ee8d8f02b3e76015b8ae399ad7131a6a00d778cc40ac6294c6efd61f1d4` |
| `results/text-holdout-generation/manifest.json` | `7196ce0d28bd1a7560a0b821d3ce1956cb5964a6d756a07092e589b501b6030c` |
| `prompts/generate_feedback_holdout.txt` | `363baddcfa44bf6b89a0f11bd7aea090e93b9042e507ddd02ef1b7c15f85acbe` |
| `prompts/extraction_nausea_grouping.txt` | `64c6dfe9d09fa225aac6b74045a024350ca09aa13f36889dcab95d935febc33f` |
