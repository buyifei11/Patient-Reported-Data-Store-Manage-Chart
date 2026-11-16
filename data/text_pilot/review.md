# Pilot preparation and review record

Preparation-stage status: reviewed development fixtures; extraction had not been
run when this review was recorded. The later
[first extraction baseline](../../results/text-pilot-extraction/README.md) is
documented separately; it did not change these source/reference labels.

## Authorship and generation

- Seed facts were taken from five existing fictional questionnaires. Their
  original record IDs and fingerprints are stored in `seeds.jsonl`.
- Text generation used one real OpenAI Responses API request with
  `gpt-5.4-mini-2026-03-17`, reasoning effort `none`, and strict JSON output.
- The generator received seed facts and submission context. The request, exact
  API response, raw text output, model identifier, token usage, and hashes are
  retained in `results/text-pilot-generation/`.
- Generation used 1,624 input tokens and 285 output tokens (1,909 total).
- The main agent authored references from the reviewed text and data contract.
  A separate agent first checked the raw text against the seeds, then checked
  every reference field against the reviewed text and facts.
- This is AI-assisted synthetic authoring and independent agent review, not
  independent human annotation, expert clinical review, or measured extraction
  performance. No extraction or training requests were made.

## Raw-text review

| Report | Initial decision | Finding | Reviewed decision |
|---|---|---|---|
| TP001 | Pass | Count 2; vomiting severity 2/5; nausea severity 3/5; compatible daily contexts | Accepted |
| TP002 | Pass | Explicit zero vomiting, no invented vomiting rating, nausea severity 2/5 | Accepted |
| TP003 | Clarify | Nausea score 3/5 is present, but its own worst-so-far-today context is only implicit across a conjunction | Accepted after the documented clarification below |
| TP004 | Pass | Cumulative count 4, vomiting severity 2/5, nausea severity 4/5 | Accepted |
| TP005 | Pass | Cumulative count 1, vomiting severity 2/5, nausea severity 5/5; no invented correction | Accepted |

## The sole editorial change

Report: **TP003**. The raw API output remains unchanged.

Original clause:

> I also have nausea with a worst severity of 3 out of 5.

Reviewed clause:

> I also have nausea with a worst severity so far today of 3 out of 5.

The words **so far today** were inserted to make this symptom's severity context
explicit. The raw wording was plausibly compatible with the preceding clause,
but was not as explicit as the seed's `worst_today_so_far` definition. No value,
count, date, symptom, or medication fact was changed. The edit was made before
any extraction result existed; it is a disclosed data-authoring clarification,
not selection or repair based on extractor performance. The other four reviewed
texts are identical to their raw generation.

## Reference and provenance review

All five sources, ten extraction checks, and ten normalized references passed
schema and provenance checks. A separate agent reviewed all 110 semantic field
expectations in the extraction checks and all normalized observations.

- The pilot source files contain empty questionnaire arrays; original answers
  remain outside the future extraction input.
- Every seed matches the original questionnaire values and source fingerprint.
- Original patient IDs, dates, submission timestamps, timezones, and null
  correction links are preserved.
- All vomiting counts have `day_to_date` scope. No submission timestamp becomes
  a symptom occurrence time.
- TP002's zero means known absence. TP003's unknown number does not become zero;
  vomiting remains present and its known severity remains 2/5.
- Nausea counts are null because counts are not defined for that symptom; they
  do not receive a `count_unknown` issue.
- TP004/TP005 retain counts 4 and 1 as per-report extraction references. The
  later daily-aggregation conflict is deliberately not inserted into these labels.
- Exact supporting text is retained. Time-phrase and quotation boundaries are
  not treated as proof that only one textual span can be correct.
- Sources and references were checked directly; the normalizer was not executed
  to create or judge its own reference labels. No extraction accuracy was computed.

## Scope and next step

All five examples are `development`. Related cumulative reports share a group;
any paraphrases of a seed must remain in the same future split. This small pilot
contains highly repetitive, controlled wording and is not evidence of robustness
or generalization. Earlier datasets and the existing dashboard are unchanged.

The next separate step is to freeze an extraction configuration, run the actual
text extractor without the seed/reference data, and compare its saved extraction
results with these reviewed references. No such run is included here.

## Reviewed file fingerprints

Reviewed at UTC: 2026-11-16T04:40:05.182302+00:00

| File | SHA-256 |
|---|---|
| `data/text_pilot/seeds.jsonl` | `051efa04837c2b1bb451f6ad31314e5712b3fe1d3377e4037cfd3e47eb3574d4` |
| `data/text_pilot/reports.jsonl` | `d9a13eab768fccddbb74512cfad4ef691d39e247d79c324e4a87f41327809b49` |
| `data/text_pilot/expected.jsonl` | `900b90be5c206a49e7b1c3070e1ba2bfb6a5c951f733df19d927f9699e93374d` |
| `prompts/generate_feedback_pilot.txt` | `42eb001b291c2d65717ca5ebc05651044661437fc13217b63989cae7e7251e4a` |
| `results/text-pilot-generation/request.json` | `0dbac7156f55a718a59798620ad7e9965bf2612b7a28a5af3a46a6877af07707` |
| `results/text-pilot-generation/response.json` | `77f15143cce4f22799237fffe2175e32e8513e8cd04a335e4de8b64cc1527ede` |
| `results/text-pilot-generation/generated_texts.jsonl` | `4ba5a0290095f1536f7c6430b77ea957d0fc573af2be9222cbd39c70f4929fd4` |
