# Text extraction pilot: the first five examples

This is the first data-preparation step for an English text-extraction experiment.
Five existing fictional questionnaires supply fact seeds. One actual LLM request
turns those seeds into patient feedback. The text is then reviewed, and reference
answers are authored from the reviewed text and the existing data contract.

Preparation is complete. The [first extraction baseline](../../results/text-pilot-extraction/README.md)
and a bounded [evidence-prompt comparison](../../results/text-pilot-evidence/README.md)
are recorded separately. No model training or dashboard replacement has been
performed for this pilot. These are development examples, not an independent
test set or real patient data.

## Start with these five cases

All counts describe **today up to the submission**, not a completed day. All
provided severity ratings describe the **worst severity so far today**, out of 5.

| Report | Patient / date | Vomiting count | Vomiting severity | Nausea severity | Purpose |
|---|---|---:|---:|---:|---|
| TP001 | P001 / 2026-11-04 | 2 | 2/5 | 3/5 | Ordinary positive report |
| TP002 | P002 / 2026-11-22 | 0 | Not applicable | 2/5 | Explicit absence of vomiting |
| TP003 | P003 / 2026-11-14 | Unknown | 2/5 | 3/5 | Vomiting happened, but the number is unknown |
| TP004 | P001 / 2026-11-10, submitted 10:00 | 4 | 2/5 | 4/5 | Earlier cumulative update |
| TP005 | P001 / 2026-11-10, submitted 20:30 | 1 | 2/5 | 5/5 | Later update conflicts with the earlier count |

Submission times are in each patient's timezone, `America/Chicago`. They are not
times at which a vomiting episode occurred. There are five reports and ten
symptom observations: one nausea and one vomiting observation per report.

### TP001: a known number

> So far today I have vomited 2 times, and the worst vomiting severity so far today is 2 out of 5. I also have nausea, and the worst nausea severity so far today is 3 out of 5.

The vomiting count is 2, its scope is `day_to_date`, and both severity values are
explicit. The date is resolved from "today" and the submission metadata.

### TP002: zero is a known value

> I have had no vomiting today so far. I also have nausea, and the worst nausea severity so far today is 2 out of 5.

Vomiting has `assertion=absent` and `count=0`. Its severity is null because no
vomiting occurred. Nausea remains present with severity 2/5.

### TP003: unknown is different from zero

> I have vomited today so far, but I don't know the number of episodes. The worst vomiting severity so far today is 2 out of 5, and I also have nausea with a worst severity so far today of 3 out of 5.

Vomiting has `assertion=present` and `count=null`: occurrence is known, number is
not. Its severity is still known. The normalized reference includes `count_unknown`.
The nausea count is also null, but for a different reason: episode counts are not
defined for nausea in this contract.

This reviewed text has one disclosed editorial clarification. The raw generation
omitted "so far today" from the nausea clause. That phrase was inserted before
any extraction run to make the intended severity context explicit. See the
[review record](review.md); the unedited model output is preserved.

### TP004 and TP005: preserve each report's claim

TP004, submitted at 10:00:

> Today up to now I have vomited 4 times, and the worst vomiting severity so far today is 2 out of 5. I also have nausea, and the worst nausea severity so far today is 4 out of 5.

TP005, submitted at 20:30:

> Today up to now I have vomited 1 time, and the worst vomiting severity so far today is 2 out of 5. I also have nausea, and the worst nausea severity so far today is 5 out of 5.

The correct per-report extraction counts are **4 and 1**, respectively. Neither
report declares a correction. Their disagreement is a later daily-aggregation
question; it must not turn either extraction reference count into null. The pair
shares one `group_id` and must stay together in any future dataset split.

## Files and their roles

| File | Role | May the extraction process read it as input? |
|---|---|---|
| [seeds.jsonl](seeds.jsonl) | Facts and provenance used to generate the five texts | No |
| [reports.jsonl](reports.jsonl) | Reviewed English text and submission metadata | Yes; the existing LLM adapter receives only `text` |
| [expected.jsonl](expected.jsonl) | Expected extraction fields and normalized observations | No; evaluation only |
| [review.md](review.md) | Review findings, editorial change, limitations, and file fingerprints | No |
| [Generation prompt](../../prompts/generate_feedback_pilot.txt) | Instructions used for text generation | No |
| [Generation record](../../results/text-pilot-generation/) | Actual API request, response, raw texts, and usage/provenance manifest | No |

`reports.jsonl` deliberately contains `questionnaire_answers: []` in every row.
The source questionnaire facts are retained only in the seed/provenance path.
Otherwise the deterministic merger could fill values from the original answers
and hide an extraction error. Original datasets and the existing dashboard remain
unchanged.

## Reading the fields

Each JSONL line is one report. `report_id` joins its seed, reviewed source, and
reference record; it does not represent an individual symptom.

### Seed fields

| Field | Meaning and reason for keeping it |
|---|---|
| `report_id` | New pilot ID, TP001–TP005; avoids silently replacing original reports |
| `origin_report_id` | Existing questionnaire record from which the seed facts came |
| `origin_source_sha256` | Fingerprint of that original record; detects source changes |
| `group_id` | Groups related reports; TP004/TP005 share a patient/day group |
| `split` | `development` for every pilot example; no unseen-test claim |
| `focus` | The semantic situation this example checks |
| `style` | A writing instruction to the text generator, not a clinical fact |
| `context` | Original patient ID, submission timestamp, timezone, and correction link |
| `facts` | Symptom facts that the generated text must preserve |

### Source report fields

| Field | Meaning |
|---|---|
| `report_id` | Identifier linking this text to its reference |
| `patient_id` | Fictional patient identifier |
| `reported_at` | When the report was submitted, including the UTC offset |
| `patient_timezone` | Timezone used to resolve "today" and other relative dates |
| `text` | The reviewed patient feedback; this is what the extraction LLM reads |
| `questionnaire_answers` | Always empty here, so the old answers cannot supplement extraction |
| `supersedes_report_id` | Explicit correction target; null in all five examples |

### Symptom and reference fields

| Field | Meaning |
|---|---|
| `symptom` | `nausea` or `vomiting` |
| `assertion` | Whether the symptom is present or explicitly absent in these examples |
| `count` | Vomiting episodes; 0 means known absence, null means unknown or not applicable |
| `count_scope` | `day_to_date` means cumulative up to submission; null for nausea |
| `severity` | Worst symptom severity so far today on the 1–5 scale; null when no applicable score is given |
| `severity_scale_max` | The scale's upper bound, 5 when a rating is stated; null otherwise |
| `severity_context` | `worst_today_so_far` for these ratings; preserves what the score measures |
| `event_date` | Calendar date described by the text, resolved using context |
| `event_time` | A known symptom occurrence clock time; null in all five reports |
| `observation_id` | Stable reference ID for one symptom observation; not a field the LLM must invent |
| `time_text` | A supporting time phrase copied from the text |
| `date_basis` | `relative_text` here because dates are established from "today" |
| `medication_relation` | Null: none of these texts states a medication relationship |
| `evidence` | Exact supporting text; `path: text` names its source and `value` contains the quote |
| `issues` | Field-specific missing/conflicting information; not a model confidence score |

The reference file has two complementary parts:

- `extraction_checks`: ten checks covering the semantic fields the LLM should
  extract before normalization. `source` identifies the supporting quote, and
  `expected_fields` gives the expected values. At this layer, `severity_value`
  is the stated score, `day_reference=today` is the relative day, `explicit_date`
  is null, and `clock_time` is null. These are not final date calculations.
- `observations`: ten expected final normalized symptom records. These labels
  were authored from the reviewed text and contract, without using the normalizer
  to manufacture its own reference answers. Observations use alphabetical symptom
  order for stable reference IDs; identity/order is not a language-understanding
  target.

In an issue such as `{"field":"count","code":"count_unknown"}`, `field` names
the affected value and `code` states why it remains unresolved. Reference quote
and time-phrase boundaries are examples of valid evidence; later scoring must
separate semantic field accuracy from harmless differences in span boundaries.

## Checks performed in this step

Existing strict source/reference schemas, ID linkage, and evidence provenance were
validated. Original questionnaire facts, report context, group membership, empty
questionnaire inputs, and the raw-to-reviewed text change were checked separately.
These are fixture checks, not extraction accuracy scores.

The references are AI-assisted, agent-authored and independently agent-reviewed.
They are not independently human-annotated or clinically validated gold. The
wording is deliberately controlled and highly repetitive, so the five cases only
establish a small, inspectable starting point. They do not test broad language
variation or generalization.

The original extraction model has now been run with a frozen prompt. Its saved
outputs and evaluation are in the separate baseline record linked above. All key
values matched; one report retained incomplete supporting evidence. The separate
evidence-prompt comparison has now been completed: the candidate preserved all
field values and supplied complete quotes for all ten observations in that run.
Sources and references were not edited. Broader evaluation is still needed; these
five known development examples do not demonstrate generalization.
