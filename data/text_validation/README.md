# Ten text cases: preparation and regression experiments

**Preparation, the [two-prompt comparison](../../results/text-validation-comparison/README.md), [grouping follow-up](../../results/text-validation-grouping/README.md), and [compact follow-up](../../results/text-validation-compact/README.md) are complete. These cases are known development/regression material.**
They are new, fictional cases authored after the two existing extraction prompts
were frozen. One LLM generation request produced the texts; references were then
authored from those texts and the data contract and checked by a separate agent.
All ten generated texts were accepted without editorial changes.

These began as targeted synthetic validation cases, not a final independent test set.
They extend the [five development examples](../text_pilot/README.md) with different
sentence layouts. They are newly authored facts, not ten more conversions of the
61 original questionnaires. No model training was performed. The preparation
protocol and review remain historical snapshots from before extraction; actual
outputs and metrics are recorded in the separate comparison, without changing
these source texts or reference answers.

The grouping follow-up used the observed errors to adjust a prompt, so it is a
development experiment. It removed fragmented candidates but reduced whole-report
passes from 8/10 to 7/10, due to two invalid quotes and one nausea scope error.
That candidate was not promoted. Historical seed `split=validation` labels record
the preparation role; the follow-up protocol explicitly records the current role.

The compact follow-up returns to 8/10 whole-report passes. Vomiting grouping,
continuous quotes, and nausea count-scope constraints pass this run, but TV007
and TV009 emit duplicate nausea candidates. A separate offline diagnosis explains
why the unchanged normalizer retains those duplicates; no program fix or output
repair was included in the prompt comparison.

## What the ten cases cover

Every count means **today up to submission**, not a complete-day total. Every
stated severity means **that symptom's worst severity so far today, out of 5**.

| Report | Text structure | Vomiting count | Vomiting severity | Nausea severity |
|---|---|---:|---:|---:|
| TV001 | Single sentence | 3 | 1/5 | Not mentioned |
| TV002 | Single sentence | Not mentioned | Not mentioned | 4/5 |
| TV003 | Count, then rating in next sentence | 1 | 3/5 | Not mentioned |
| TV004 | Rating, then count in next sentence | 2 | 4/5 | Not mentioned |
| TV005 | Nausea occurrence, then rating | Not mentioned | Not mentioned | 2/5 |
| TV006 | Vomiting count → nausea → vomiting rating | 4 | 3/5 | 1/5 |
| TV007 | Nausea → vomiting → nausea rating | 2 | 2/5 | 5/5 |
| TV008 | Nausea aside between vomiting count and rating | 5 | 1/5 | 3/5 |
| TV009 | Explicit absence of vomiting, plus nausea | 0 | Not applicable | 3/5 |
| TV010 | Vomiting present but count unknown, plus nausea | Unknown | 4/5 | 2/5 |

There are **10 reports and 15 symptom observations**, not 15 reports. TV001–TV005
each have one observation; TV006–TV010 each have two. A symptom that is not
mentioned does not get a fabricated absent observation.

## Read each text with its answer

### TV001: an ordinary single-sentence control

> I’ve vomited three times so far today, and the worst vomiting severity today up to now is 1 out of 5.

One vomiting observation: present, count **3**, severity **1**. The whole sentence
supports the count and rating. Severity 1 still describes a present symptom.
There is no nausea observation.

### TV002: do not invent the unmentioned symptom

> I’m nauseous today up to now, and my nausea is 4 out of 5 at its worst so far today.

One nausea observation: present, severity **4**, count null because this contract
does not count nausea episodes. There is no vomiting observation; silence about
vomiting does not mean zero.

### TV003: the count and rating need both sentences

> I’ve vomited once so far today. The worst vomiting severity today up to now is 3 out of 5.

Vomiting: count **1**, severity **3**. Quoting only the first sentence would omit
the score. Quoting only the second would omit the count. A complete candidate
quote must cover both. "Once so far today" is a daily cumulative count even
though the number happens to be one.

### TV004: the same task with reversed sentence order

> The worst vomiting severity so far today is 4 out of 5. I’ve thrown up 2 times today up to now.

Vomiting: count **2**, severity **4**. Both sentences are needed for these fields.
"Thrown up" denotes vomiting; placing the score before the count changes neither.

### TV005: a shorter quote can still be complete

> I’ve had nausea today up to now. My worst nausea severity so far today is 2 out of 5.

Nausea: present, severity **2**. The final sentence alone supports presence, score,
scale, date reference, and severity context, so it is the reference evidence.
The full two-sentence quote would also be valid. Completeness does not mean always
quoting the entire report.

### TV006: keep evidence across an intervening symptom

> I’ve vomited 4 times so far today. I’ve had nausea today up to now, and my worst nausea severity today up to now is 1 out of 5. The worst vomiting severity so far today is 3 out of 5.

Vomiting: count **4**, severity **3**. Nausea: severity **1**. The vomiting quote
must span the first and third sentences, retaining the intervening sentence as
part of one exact contiguous quote. That sentence does not transfer nausea's
score of 1 to vomiting. Nausea needs only the middle sentence.

### TV007: interleaving does not always require a long quote

> I’ve had nausea today up to now. I’ve vomited 2 times so far today, and the worst vomiting severity today up to now is 2 out of 5. My nausea is 5 out of 5 at its worst so far today.

Vomiting: count **2**, severity **2**. Nausea: severity **5**. The middle sentence
supports all vomiting fields; the final sentence supports all nausea fields.
This checks correct symptom assignment amid interleaving. Unlike TV006, neither
observation needs the entire report as evidence.

### TV008: evidence separated by a parenthetical aside

> I’ve vomited 5 times so far today (I’ve had nausea today up to now, and my worst nausea severity so far today is 3 out of 5), and the worst vomiting severity today up to now is 1 out of 5.

Vomiting: count **5**, severity **1**. Nausea: severity **3**. The vomiting quote
spans the aside to retain both its count and score. Nausea's own clause suffices
for its reference. This uses a different grammatical layout from TV006.

### TV009: zero is an answer

> I haven’t vomited so far today. I’ve had nausea today up to now, and my worst nausea severity so far today is 3 out of 5.

Vomiting: **absent**, count **0**, severity **null**. Nausea: present, severity
**3**. The explicit denial supports a zero; it is not missing data. No vomiting
severity should be invented when vomiting is absent.

### TV010: unknown is not zero

> I’ve vomited today up to now, but the cumulative count is unknown. The worst vomiting severity so far today is 4 out of 5. I’ve had nausea today up to now, and my worst nausea severity so far today is 2 out of 5.

Vomiting: **present**, count **null**, severity **4**; its normalized observation
has the issue `{"field": "count", "code": "count_unknown"}`. Both first sentences
support those facts. Nausea: present, severity **2**, with no count issue. A missing
vomiting number must not erase the known score or imply uncertain occurrence.

## Files and evaluation boundaries

| File | Purpose | Future extraction input? |
|---|---|---|
| [reports.jsonl](reports.jsonl) | The ten reviewed texts and submission metadata | Yes; the LLM receives only `text` |
| [expected.jsonl](expected.jsonl) | Reference fields, normalized answers, and evidence | No; scoring/review only |
| [seeds.jsonl](seeds.jsonl) | New fictional facts, writing layout, and case groups | No; generation only |
| [preparation.json](preparation.json) | Scope and extraction prompt fingerprints frozen before generation | No |
| [review.md](review.md) | Authorship, review findings, limitations, and data fingerprints | No |
| [Generation prompt](../../prompts/generate_feedback_validation.txt) | Instructions used to turn facts into texts | No |
| [Generation record](../../results/text-validation-generation/) | Actual request, response, raw texts, and manifest | No |

All `questionnaire_answers` arrays are empty. Otherwise questionnaire values could
fill gaps in the model's extraction and hide errors. The generator received facts,
context, and writing instructions, but no extraction prompts, previous texts, or
previous extraction outputs. Sources and reference answers remain separate.

The **165 candidate field expectations** are 15 observations × 11 semantic fields.
They are checks, not 165 successful extractions or independent examples.
The reference also contains 15 normalized observations to check the later code
stage. These answers were not produced by running the normalizer on itself.

## How to read the fields

The format is unchanged from the [pilot field guide](../text_pilot/README.md#reading-the-fields).
The key distinctions are:

- `report_id` identifies one text; `observation_id` identifies one symptom in it.
- `assertion` distinguishes present from explicitly absent symptoms.
- `count=0` means known absence of vomiting. `count=null` means unknown vomiting
  count or an inapplicable nausea count; the symptom and assertion disambiguate it.
- `count_scope=day_to_date` means cumulative up to submission, including zero and
  unknown counts with that scope. Nausea has null scope.
- `severity_value` is the extracted number; `severity_scale_max=5` and
  `severity_context=worst_today_so_far` explain its meaning. The normalized value
  is called `severity`. Absent vomiting has no score, scale, or score context.
- `day_reference=today` comes from the text; code later resolves `event_date`
  using `reported_at` and `patient_timezone`. These examples use November 12–15,
  2026 in America/Chicago. No submission time becomes an occurrence time:
  `clock_time` and `event_time` are null.
- `source` in each `extraction_checks` entry points to an exact supporting quote;
  `expected_fields` states what it should support. Normalized `evidence` retains
  the same provenance. Quotes may overlap across symptoms.
- `issues` records an unresolved field. TV010 vomiting alone has `count_unknown`.
  It is not a low-confidence label for the entire report.

New seed metadata uses `origin=new_synthetic_case` rather than claiming an
original questionnaire ID. `group_id` keeps future paraphrases of a seed in one
split; `split=validation` records the initial intended role. Fictional patient IDs are
VAL-P001–VAL-P010, not ten independently sampled real patients. `focus`, `layout`,
and `style` describe case construction and never enter the extraction input.

## Scope of the comparison

The two frozen prompts were compared on these same reviewed texts, with the same
extraction model and runtime. Semantic fields and evidence completeness were
checked separately, including extra and missing observations. Whole reports
passed 2/10 with the original prompt and 8/10 with the evidence-focused prompt;
TV003 and TV006 still split counts and scores in the latter run. See the linked
comparison for the full results and the observed TV006 structure regression.
An exact substring check alone does not prove that a quote supports every field;
literal differences in valid quote boundaries should not count as errors.

This small set targets evidence retention and symptom assignment. Its wording is
still controlled and repetitive; TV010's "cumulative count" is less conversational
than ordinary feedback. It does not test broad clinical language, medication
relations, occurrence clocks, corrections, or ambiguous dates. The texts and labels
are AI-assisted, not independent human clinical annotations. Generation uses the
same model family as the planned extractor, which further limits independence.
These results have now been used to tune prompts, making the cases development
examples. A generalization claim needs another untouched evaluation set.
