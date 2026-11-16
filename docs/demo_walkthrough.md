# Run and explain the prototype

## Offline setup

Use Python 3.11 or newer; this project was tested with Python 3.14.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -q
python run_demo.py build --output artifacts/demo
```

Open `artifacts/demo/dashboard.html` in a browser. The file is self-contained;
no server, internet connection, or API key is needed after dependency installation.
Choose a new output directory for another build. Existing output is never
overwritten. The database and CSV files are generated alongside the page:

- `patient_reports.sqlite`: original sources, processing results, and derived tables.
- `predictions.jsonl`: current normalization of actual cached candidates plus forms.
- `daily.csv`, `weekly_counts.csv`: eligible daily values and weekly coverage.
- `after_medication_change.csv`: temporal contexts without a causal claim.
- `review_queue.csv`: unresolved values and exclusions with source identifiers.
- `summary.json`: dataset/runtime hashes, processing provenance, counts, and corrections.

The extra questionnaires are source data, not gold. The ten free-text reports
reuse the first real v1 model run, including its limitations. A displayed
`saved_candidate_replay` means the code revalidated earlier model output; it is
not a new model call. No model output is selectively replaced by a reference.

## A concise demonstration

1. Open **Demo patient 2**. The chart shows supported daily counts over four
   weeks, gaps, medication markers, and the coverage denominator.
2. Open **R005** and **R006** under source records. The original count 3 is
   retained, but the corrected November 4 value is 2. Explain why cumulative
   reports are not summed.
3. Select **Demo patient 1**. November 3 has a supported vomiting zero but an
   unresolved nausea score. November 10's cumulative decrease is excluded from
   the count trend and visible in the review queue. These are different issues.
4. Select **Demo patient 3**. Inspect the unknown date, unknown count, and text/form
   conflict. Missing follow-up days remain gaps. The questionnaire-only
   November 14 has an unknown count but a usable severity.
5. Return to **Demo patient 2** and inspect medication timing. R003's 14:20
   episode is definitely after the 13:00 change. For patient 3, the same-day
   morning nausea cannot be ordered precisely against the recorded change.
6. Show the SQL files and one terminal query. Explain that the chart reads
   database-derived results and preserves source evidence, not hardcoded chart data.

```bash
python run_demo.py query --db artifacts/demo/patient_reports.sqlite --query weekly
python run_demo.py query --db artifacts/demo/patient_reports.sqlite --query medication
python run_demo.py query --db artifacts/demo/patient_reports.sqlite --query review
```

## Optional fresh text extraction

The default offline demo is reproducible without paid services. To demonstrate
the existing cloud extractor separately, configure `.env` locally and run:

```bash
python run_pipeline.py extract --provider openai \
  --model gpt-5.4-mini-2026-03-17 --limit 1 \
  --output data/processed/live-one-report.jsonl
```

This optional command makes a real API request. Never present the resulting
single-case output as broad validation, and do not overwrite historical runs.
The cloud adapter and optional Ollama adapter are separate from the offline demo.

For a new full longitudinal text extraction cache, use `run_pipeline.py extract`
with the matching source dataset, then pass its output to
`run_demo.py build --cached-predictions PATH --output NEW_DIRECTORY`. Empty-text
questionnaires are still processed directly by the demo. A cache must contain
every nonempty-text report with the exact source hash; stale or missing text
results stop the build instead of disappearing.

## Trade-offs to explain

- AI identifies source claims; deterministic code owns dates, validation,
  reconciliation, correction state, counting, and SQL.
- V1 remains the baseline. V2/v3 experiments found useful gains and material
  regressions; the higher completion rate alone did not justify promotion.
- The daily-count policy is deliberately conservative about events/windows with
  unclear overlap. Excluded observations remain available for inspection.
- Four-week questionnaire coverage demonstrates storage and charting, not
  generalizable LLM extraction accuracy or clinical validity.
- The [storage design](storage_and_trends.md) and [time-boundary fix](time_boundaries.md)
  describe rules, regression checks, and known limitations.
