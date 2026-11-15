# Patient-Reported Data: Store, Manage & Chart

Track B prototype for structuring synthetic patient reports, storing them over time, and showing symptom trends.

## Current stage

The first milestone contains the v0.2 data design and starter examples. The repository does not yet contain executable application code. All submission artifacts are written in English.

| Component | Status |
| --- | --- |
| Data fields and processing rules | Documented; not implemented as executable schemas or validators. |
| Starter source data | 10 reports from 3 fictional patients. |
| Expected structured results | 15 observations and 3 targeted extraction checks, authored as development references; not parser-generated output. |
| Parser and model integration | Not implemented. |
| Database and SQL queries | Not implemented. |
| Charts or dashboard | Not implemented. |
| Reusable validation scripts and automated tests | Not implemented. |
| Full multi-week dataset and held-out evaluation cases | Not yet prepared. |

- [Design and field explanations](docs/design.md)
- [10 synthetic source reports](data/raw/reports.jsonl)
- [Expected structured results: 15 observations](data/gold/expected.jsonl)

Each JSONL file contains one JSON object per line. Match input and expected results by `report_id`.

The examples cover nausea and vomiting, a completed-day total, explicit absence, uncertain timing and counts, cumulative reports, a complete multi-symptom correction, field-specific questionnaire conflicts, and a patient-reported medication relationship. All patients and medication labels are fictional.

Expected results were drafted with AI assistance and checked against the documented rules. They are development fixtures, not an independently labeled test set or evidence of clinical accuracy. Expected results must not be supplied to the parser as input.

## v0.2 data contract

- Text extraction, deterministic normalization, and cross-report aggregation have separate responsibilities.
- `questionnaire_answers` is a list, allowing multiple symptoms in one submission.
- `day_total` distinguishes a completed-day total from `day_to_date`.
- Issues use `{field, code}` objects; a severity conflict does not discard a valid count.
- Severity means the worst severity so far today on the documented 1-5 scale.
- Corrections submit a complete replacement, including unchanged symptoms.
- Gold includes small `extraction_checks` before reconciliation, and final `observations` after normalization. Generated IDs are not semantic accuracy targets.

The same 10 fixture IDs are retained, but several source examples and reference answers were revised for v0.2. They now contain 15 observations rather than 13. Earlier fixtures remain in Git history.

## Current validation

One-off integrity checks are used during preparation for JSON validity, unique IDs, field values, timezones and dates, indexed evidence paths, correction references, and consistency between the examples and design. These checks have not yet been added as reusable scripts or an automated test suite. No parser evaluation has been run.

## Next steps

1. Review the design and starter examples.
2. Implement extraction and deterministic validation.
3. Store reports and observations in SQLite.
4. Add multi-week data, independent evaluation cases, two SQL queries, and a patient trend view.

## Local development

Open this repository folder in VS Code. No API key or dependency installation is needed to inspect the current files. Runnable commands will be documented when the implementation is added.

Keep real API keys in a local `.env` file. The repository ignores local secrets, environments, caches, and generated artifacts, while keeping the synthetic source and expected datasets under version control.
