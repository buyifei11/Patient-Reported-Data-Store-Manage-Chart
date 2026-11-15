# Patient-Reported Data: Store, Manage & Chart

Track B prototype for structuring synthetic patient reports, storing them over time, and showing symptom trends.

## Current stage

The first milestone contains a data design and starter examples. The parser, database, SQL queries, and dashboard are not implemented yet.

- [Design and field explanations (中文)](docs/design.md)
- [10 synthetic source reports](data/raw/reports.jsonl)
- [Expected structured results: 13 observations](data/gold/expected.jsonl)

Each JSONL file contains one JSON object per line. Match input and expected results by `report_id`.

The examples cover nausea and vomiting, explicit absence, uncertain timing and counts, cumulative reports, a correction, questionnaire conflicts, and a patient-reported medication relationship. All patients and medication labels are fictional.

Expected results were drafted with AI assistance and checked against the documented rules. They are development fixtures, not an independently labeled test set or evidence of clinical accuracy. Expected results must not be supplied to the parser as input.

## Current validation

The starter files have been checked for JSON validity, unique IDs, field values, timezones and dates, source evidence, and correction references. No parser evaluation has been run yet.

## Next steps

1. Review the design and starter examples.
2. Implement extraction and deterministic validation.
3. Store reports and observations in SQLite.
4. Add multi-week data, independent evaluation cases, two SQL queries, and a patient trend view.

## Local development

Open this repository folder in VS Code. No API key or dependency installation is needed to inspect the current files. Runnable commands will be documented when the implementation is added.

Keep real API keys in a local `.env` file. The repository ignores local secrets, environments, caches, and generated artifacts, while keeping the synthetic source and expected datasets under version control.
