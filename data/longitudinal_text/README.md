# All-text longitudinal integration dataset

This dataset contains **71 fictional text reports for three patients** across
November 1–28, 2026. All 71 have nonempty `text` and empty
`questionnaire_answers` arrays. Symptom information therefore has to pass through
LLM extraction before normalization, storage, and visualization. Patient,
submission, correction, and medication-change metadata remain structured.

This is a text conversion of the existing [longitudinal dataset](../longitudinal/README.md),
not a new held-out benchmark. It provides 84 follow-up patient-days and retains
the same five medication-change records. It exercises the complete pipeline on
known synthetic cases; it does not establish clinical accuracy or generalization.

## How the reports were assembled

| Original source group | Reports | New text source |
|---|---:|---|
| Text only among the original ten | 8 | Original text retained verbatim |
| Text and questionnaire: R002 and R009 | 2 | Original text retained verbatim, followed by generated questionnaire statements |
| Questionnaire-only follow-ups | 61 | Generated patient feedback based on the original questionnaire facts |
| Total | 71 | All text, zero questionnaire answers in the final sources |

The generator produced **63 supplements**, covering the 61 follow-ups and the
two mixed reports. This is not 63 additional reports. All ten original text
prefixes remain unchanged. R002 and R009 use a same-reporting-interval header to
retain both original claims and form-derived claims without choosing a winner.
Sixty-two generated supplements were accepted unchanged; one omitted
unknown-count statement was restored before reference authoring and extraction.
The exact change is recorded in [review.md](review.md) and
[editorial_review.json](editorial_review.json).

New report IDs prepend `TXT-` to the original IDs. The explicit correction link
is correspondingly mapped from `TXT-R006` to `TXT-R005`. Original source files
are preserved. Correction links and medication changes are supplied metadata;
the LLM does not infer them.

## Files and their roles

| File | Purpose | Runtime use |
|---|---|---|
| [reports.jsonl](reports.jsonl) | Final patient text, submission metadata, and correction links; one report per line | Extraction and subsequent processing |
| [patients.json](patients.json) | Three patients, timezones, and inclusive follow-up bounds | Storage, filtering, and coverage denominators |
| [medication_changes.json](medication_changes.json) | Five fictional start/dose-change events | Timeline context |
| [seeds.jsonl](seeds.jsonl) | Original source IDs/fingerprints, original text, questionnaire facts, and generation instructions for all 71 reports | Authoring provenance only |
| [expected.jsonl](expected.jsonl) | Independently authored raw-claim checks and normalized reference observations | Evaluation only |
| [preparation.json](preparation.json) | Configuration and scope frozen before generation | Audit only |
| [editorial_review.json](editorial_review.json) | Source assembly decisions and the sole pre-inference edit | Audit only |
| [manifest.json](manifest.json) | Final source/reference counts and frozen file fingerprints | Reproducibility checks |
| [review.md](review.md) | Source/reference review and interpretation decisions | Documentation |

`expected.jsonl` contains **139 distinct candidate checks** and **137 normalized
observations**. A candidate check describes what a raw text claim says; a
normalized observation describes the result after compatible claims are grouped
and conflicting claims are retained as uncertainty. There are 1,529 candidate
field expectations and 1,233 normalized core-field expectations, including
430 intentional nulls. All reference evidence points to literal text spans.

## Extraction, evaluation, and dashboard boundary

The intended data flow is:

```text
Original facts → generated text → reviewed final reports → LLM candidates
                                                           ↓
                                                     normalization
                                                           ↓
                                                     SQLite → charts

Reviewed final reports + written contract → reference answers → evaluation
```

The extraction model receives final report text and the frozen instructions and
schema. It does **not** receive seed facts, questionnaire answers, reference
answers, or submission metadata. Python uses submission metadata afterward to
resolve supported relative dates. Reference answers are used to score saved
predictions, never to populate the database or dashboard.

The actual 71-report extraction is stored in
[results/longitudinal-text-extraction](../../results/longitudinal-text-extraction/).
Its [protocol](../../results/longitudinal-text-extraction/protocol.json) records
the selected prompt, model, one-attempt policy, and frozen source/reference
hashes. Offline dashboard construction subsequently reuses actual saved
candidates and makes zero additional model requests. Generation, extraction,
and offline rebuilding are separate stages.

The `extraction_requests_so_far: 0` values in preparation artifacts describe the
pre-inference snapshot. They do not imply that the later extraction never ran.

## Interpretation limits

- These are known integration fixtures. The original ten reports and some seed
  facts had already been used during development. Do not present this set as an
  independent test split or use its score as the held-out result.
- The 63 raw generated supplements contain only **37 unique text strings**.
  Repeated wording, controlled symptom vocabulary, and a shared generation and
  extraction model family limit linguistic diversity.
- Follow-up counts and ratings follow artificial patterns. Medication markers
  establish timeline context, not treatment effects or individual dose timing.
- Unknown counts, missing days, conflicts, hypothetical symptoms, and superseded
  reports remain visible under the [data contract](../../docs/design.md).
  Missing data is not zero, and cumulative updates must not be added together.
