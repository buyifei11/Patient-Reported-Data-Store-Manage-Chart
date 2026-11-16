# Evidence-focused prompt comparison

One evidence-completeness instruction block was appended to the original
extraction prompt. The same five reviewed texts were then extracted once each
with the same model and runtime, and compared with the saved original run.

**Observed result: complete supporting quotes increased from 9/10 to 10/10,
and complete reports increased from 4/5 to 5/5. All semantic field values stayed
correct, with no regressions found in these five reports.**

This is a single-run comparison on known development examples. It does not
estimate sampling variability or establish performance on new patient language.

## The only intended change

The candidate [`extraction_evidence.txt`](../../prompts/extraction_evidence.txt)
preserves the entire original [`extraction.txt`](../../prompts/extraction.txt)
and adds a general check requiring:

- The retained quote itself to support every claimed field.
- A quote spanning multiple sentences when a candidate draws facts from those
  sentences, while remaining one exact, contiguous source span.
- No borrowing another symptom's values or reconciling different time contexts.
- No dropping a supported value merely to keep the quote short.

The added block contains no pilot report IDs, numeric answers, or reference
quotes. It is an instruction change, not a fine-tuning operation. The candidate
is saved separately; the default extraction prompt and existing dashboard are
not replaced by this small comparison.

## Controlled setup

- Model: `gpt-5.4-mini-2026-03-17`; reasoning effort `none`; maximum output 2,048
  tokens, matching the original run.
- The source text, reference answers, schemas, normalizer, evaluator, field
  definitions, and evidence-review criteria were unchanged.
- Each stateless model call received only its report text and the candidate
  instructions/schema. It did not receive seeds, questionnaire answers,
  references, or the generation conversation.
- Five new calls, one attempt per report. The baseline was not rerun. Failed
  calls would have remained in the denominator; all five completed this time.
- No response repair, retries to select better outcomes, or label changes.

The [protocol](protocol.json) was frozen before the new calls and records the
unchanged baseline file hashes, input/reference hashes, candidate prompt hash,
and runtime hash.

## Before and after

| Check | Saved original prompt | Evidence-focused prompt |
|---|---:|---:|
| Completed reports | 5/5 | 5/5 |
| Symptom observations matched | 10/10, none extra | 10/10, none extra |
| Candidate semantic field expectations | 110/110 | 110/110 |
| Known normalized core fields | 58/58 | 58/58 |
| Null normalized core fields | 32/32 | 32/32 |
| Quotes that are exact source substrings | 10/10 | 10/10 |
| Quotes supporting every claimed field | 9/10 | 10/10 |
| Complete reports including evidence | 4/5 | 5/5 |
| Exact `time_text` agreement | 9/10 | 10/10 |

Evidence completeness is a source-based review by the main agent and a separate
reviewing agent, not an automatic substring metric or independent human clinical
review. The same criterion was applied to both runs. The null-heavy field totals
and small sample do not establish broad extraction accuracy.

| Report | Expected vomiting count | Original complete? | Candidate complete? |
|---|---:|---|---|
| TP001 | 2 | Yes | Yes |
| TP002 | 0 | Yes | Yes |
| TP003 | Unknown | No: incomplete quote | Yes |
| TP004 | 4 | Yes | Yes |
| TP005 | 1 | Yes | Yes |

All vomiting counts remain 2, 0, null, 4, and 1 respectively. The related morning
and evening reports are not prematurely reconciled by the extractor.

## What changed in TP003

The original retained vomiting quote was:

> I have vomited today so far, but I don't know the number of episodes.

The new model output retains:

> I have vomited today so far, but I don't know the number of episodes. The worst vomiting severity so far today is 2 out of 5

The additional clause now supports the already-correct rating 2/5 and its
worst-so-far-today context. It is a literal continuous span from the source, not
an evaluator edit or a reference quote pasted into the output. Nausea's rating
remains separate and is not transferred into the vomiting candidate.

TP003 nausea's `time_text` also changed from `today` to `so far today`, matching
the reference. This is a separate exact-span observation; the original date and
severity context were already correct.

## Saved artifacts and verification

| File | Role |
|---|---|
| [protocol.json](protocol.json) | Frozen change scope, configuration, review criteria, and provenance |
| [predictions.jsonl](predictions.jsonl) | Actual raw responses, candidates, normalized results, and usage metadata |
| [metrics.json](metrics.json) | Unchanged automatic evaluator output |
| [review.json](review.json) | Per-observation evidence judgments and regression review |
| [summary.json](summary.json) | Candidate-run metrics and explicit review results |
| [comparison.json](comparison.json) | Baseline/candidate metrics, report decisions, and the actual quote comparison |
| [Original baseline](../text-pilot-extraction/README.md) | Preserved original results and failure explanation |

Checks confirm that the five API response IDs are distinct, saved candidates
match their raw responses, every quote is an exact source substring, all ten
quotes support the claimed fields, and automatic metrics reproduce exactly.
Baseline artifacts and source/reference/runtime hashes remain unchanged.

The new calls used 10,488 input tokens and 1,014 output tokens, 11,502 total.
The saved original run used 9,378 input and 996 output tokens, 10,374 total.
The longer instructions therefore have a measurable token overhead.

The candidate addresses the observed omission on this pilot. Broader, differently
worded examples and cases not used to design the prompt are still needed before
claiming a reliable general improvement. No such expansion is part of this run.
