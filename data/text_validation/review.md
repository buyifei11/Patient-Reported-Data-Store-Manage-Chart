# Preparation and review record

Status: ten reviewed source/reference pairs, with **no extraction run** on this
set. Fixture validation is not an extraction accuracy result.

## Authorship and generation

- The main agent designed ten new fictional fact seeds and writing layouts.
  They are not copied questionnaires or independently sampled real patients.
- Both existing extraction prompt fingerprints and the runtime fingerprint were
  frozen in `preparation.json` before the generation request. Neither prompt nor
  runtime was changed during preparation.
- One actual Responses API request used `gpt-5.4-mini-2026-03-17`, reasoning effort
  `none`, strict JSON output, and a 4,096-output-token cap. It consumed 2,617 input
  tokens and 482 output tokens, 3,099 total. There were no retries.
- The generator saw only report IDs, fictional context, facts, and writing
  instructions. Its saved request contains no extraction prompts, older source
  texts, previous extractor outputs, or authorization headers.
- All ten raw generated texts were accepted unchanged. No examples were rejected,
  regenerated, or selected based on extraction performance.
- The main agent authored reference values and exact supporting quotes by reading
  the texts against the contract. A separate agent reviewed the case matrix,
  every generated text, all 165 candidate-field expectations, and all 15 normalized
  observations. It requested no corrections.
- No extraction/normalization function was run to manufacture or judge these
  answers. No extraction, training, or fine-tuning API calls were made. Existing
  strict fixture validation uses the evaluator's provenance checks with an empty
  output list; those internal missing-output scores are not a model result.

## Semantic review

| Case | Verified result | Evidence requirement |
|---|---|---|
| TV001 | Vomiting count 3; severity 1/5; no nausea observation | One sentence suffices |
| TV002 | Nausea severity 4/5; no vomiting observation | One sentence suffices |
| TV003 | Vomiting count 1; severity 3/5; cumulative daily scope | Both adjacent sentences retain count and score |
| TV004 | Vomiting count 2; severity 4/5 | Both sentences, despite reversed fact order |
| TV005 | Nausea severity 2/5 | Final sentence alone is sufficient |
| TV006 | Vomiting count 4, severity 3/5; nausea severity 1/5 | Vomiting spans the intervening nausea sentence |
| TV007 | Vomiting count 2, severity 2/5; nausea severity 5/5 | Middle sentence for vomiting; final sentence for nausea |
| TV008 | Vomiting count 5, severity 1/5; nausea severity 3/5 | Vomiting retains the intervening parenthetical clause |
| TV009 | Vomiting absent, count 0, no rating; nausea severity 3/5 | Explicit denial supports zero |
| TV010 | Vomiting present, unknown count, severity 4/5; nausea severity 2/5 | First two sentences retain occurrence, unknown count, and score |

All 14 stated ratings explicitly describe that symptom's worst severity so far
today, out of 5. All eight vomiting observations have `day_to_date` scope. Seven
have known counts, including zero; TV010 has the sole unknown vomiting count and
the sole `count_unknown` issue. All seven nausea counts are null/inapplicable.
No extra symptom, clock time, medication, correction, or conflicting value was
added. Dates follow "today" in the provided patient-local context.

Each reference quote is one exact contiguous substring. Broad vomiting evidence
in TV006/TV008 includes other-symptom text without borrowing its rating. The
smaller TV005/TV007 nausea quotes are already complete. Alternative sufficient
exact spans remain valid; the reference boundary is not the only correct answer.

## Offline checks completed

- Strict source and reference schemas, identifier linkage, and provenance pass:
  10 reports, 15 observations, and 15 extraction checks / 165 field expectations.
- All 30 evidence entries (15 candidate checks plus 15 normalized records) are
  exact source substrings; semantic support was also reviewed separately.
- Source texts equal raw generation; context and fields agree with seeds.
- Every questionnaire array is empty. Seeds and gold remain outside extraction
  input, and generation request contents match the documented allowed projection.
- IDs and case groups are unique. No text exactly duplicates another report in
  the existing data folders. This does not demonstrate linguistic or statistical
  independence; templates and vocabulary still overlap.
- Frozen seed, generation prompt, extraction prompts, runtime, and raw generation
  fingerprints match. The freeze predates the actual request.
- Historical datasets, outputs, extraction prompts, and dashboard inputs were
  not changed. No runtime tests were added for this data-only preparation.

## Limits and future handling

These are small, deliberately targeted, AI-assisted synthetic validation cases
with separate agent review, not independent human clinical annotations. Wording
is controlled and repetitive; TV010's "cumulative count" is less conversational.
The generator and planned extractor use the same model family. The ten fictional
patient IDs do not imply ten independently sampled patients. There is no coverage
of medications, occurrence clocks, corrections, ambiguous dates, or general
clinical language.

Sources and labels must remain frozen for a later comparison. Quote support must
be checked separately from scalar-field correctness and exact-substring validity.
Using these outcomes for further tuning changes their role to development data;
a final generalization claim needs another untouched set. Related paraphrases
must stay within the same case group and future split.

## Reviewed file fingerprints

Reviewed at UTC: 2026-11-16T05:15:38.015461+00:00

| File | SHA-256 |
|---|---|
| `data/text_validation/seeds.jsonl` | `d54494512b4f7c250627937f35a5d3ce0756b00a0a0f62ed2202eb2951263534` |
| `data/text_validation/reports.jsonl` | `907d09c1292d7ed1d42c8fa8b731585c358e6ca6bafc082fda4088ff1ac10cd6` |
| `data/text_validation/expected.jsonl` | `0c975a58177f44ef2822d09fae299672daaf0dabd97c467b8efdb53276a65ea6` |
| `data/text_validation/preparation.json` | `9fef70b797d13b430c773c0a0ac10b7a7b4ae3485b945c1b6578d96292be96e2` |
| `prompts/generate_feedback_validation.txt` | `693898e634eaaf2968cfe7c16883c13d56de8d0ed83b5dae21363527e83972b7` |
| `results/text-validation-generation/request.json` | `685234084e7b85347f0f61ec17b5021b7c602fe64ec44331376f9ee016311382` |
| `results/text-validation-generation/response.json` | `4abfbb0604a5eb782783b4c1192826b51d248667e1c0e53c07130b0cc6adcca4` |
| `results/text-validation-generation/generated_texts.jsonl` | `7d762e21bed778b4584a775f7a2070c9fd53a97d40e6fcc3efa1995812af5b3e` |
