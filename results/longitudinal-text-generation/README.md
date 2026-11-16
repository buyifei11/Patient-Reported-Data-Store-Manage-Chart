# Longitudinal text-generation archive

This archive records the **generation of 63 fictional text supplements in three
API requests**. It is a source-authoring stage, not extraction, fine-tuning, or an
accuracy result. Generation ran on November 16, 2026, before the final sources
and reference answers were frozen.

The supplements verbalize 61 questionnaire-only follow-ups plus the
questionnaire portions of R002 and R009 from the existing longitudinal dataset.
The final dataset contains **71 reports**, retaining all ten original text
prefixes and supplying generated text for the other 61. R002 and R009 append
their supplements under a same-interval header; the other eight starter reports
need no generation.

## Configuration and saved evidence

- Model: `gpt-5.4-mini-2026-03-17`.
- API: OpenAI Responses; reasoning effort `none`; strict JSON schema output;
  maximum output 8,192 tokens per batch; `store: false`; `stream: false`.
- Prompt: [generate_feedback_longitudinal.txt](../../prompts/generate_feedback_longitudinal.txt).
- Input: report ID, submission context, original questionnaire facts, and a
  wording-style instruction. The generator does not receive reference answers
  or extraction results.
- Output: `report_id`/`text` pairs, 21 per batch.

Each of `batch-01/`, `batch-02/`, and `batch-03/` retains:

| File | Contents |
|---|---|
| `request.json` | Exact API request payload, including instructions, input facts, and output schema |
| `response.json` | Original API response, model/response identifiers, output, and usage |
| `generated_texts.jsonl` | Parsed raw text pairs, before editorial review |

The [manifest](manifest.json) records timestamps, batch membership, request and
response hashes, completion status, and usage. The earlier
[preparation record](../../data/longitudinal_text/preparation.json) fixes the
generation and extraction scope. The later
[dataset manifest](../../data/longitudinal_text/manifest.json) fingerprints the
reviewed sources, references, and this generation archive.

## Actual usage

| Batch | Supplements | Input tokens | Output tokens | Total tokens |
|---|---:|---:|---:|---:|
| 01 | 21 | 3,860 | 1,091 | 4,951 |
| 02 | 21 | 3,907 | 1,334 | 5,241 |
| 03 | 21 | 3,911 | 1,032 | 4,943 |
| Total | 63 | 11,678 | 3,457 | **15,135** |

All three generation requests completed. No cached input tokens or reasoning
tokens were reported. These totals cover generation only; the later 71-report
extraction has its own saved results and accounting.

## Review, assembly, and limits

The raw outputs contain **37 unique strings across 63 supplements**. They are
controlled and repetitive; generating more rows did not create 63 independently
diverse linguistic examples.

Sixty-two supplements were accepted unchanged. For `TXT-L-P003-14`, the final
source restores an explicit unknown-count statement that generation omitted.
This change occurred before reference authoring and extraction and changed no
numeric fact. Raw output here is preserved. No item was discarded or regenerated.
See the exact before/after text in
[the source review](../../data/longitudinal_text/review.md) and
[editorial_review.json](../../data/longitudinal_text/editorial_review.json).

All final source questionnaire arrays are empty. After source review, reference
answers were authored from the actual final texts and the contract, then frozen.
Extraction receives only final report text and its fixed instructions/schema;
the original questionnaire facts and reference answers never enter extraction
model input or populate the dashboard. The actual extraction archive is
[results/longitudinal-text-extraction](../longitudinal-text-extraction/).

The `extraction_requests: 0` field in this manifest describes this generation
stage, not the subsequent pipeline. This dataset reuses known synthetic facts
and the same model family for generation and extraction. It is longitudinal
integration material, not held-out evidence of real patient-text performance.
