# Run and explain the all-text prototype

## Offline setup

Use Python 3.11 or newer; this project was tested with Python 3.14.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -q
python run_demo.py build --dataset data/longitudinal_text \
  --cached-predictions results/longitudinal-text-extraction/predictions.jsonl \
  --run-id longitudinal-text-v1 --output artifacts/longitudinal-text-demo
```

Open `artifacts/longitudinal-text-demo/dashboard.html` in a browser. It is
self-contained; no server, internet connection, or API key is needed after
dependency installation. Choose a new output directory for another build.

- `patient_reports.sqlite`: original text, actual candidates, normalized results,
  correction history, daily summaries, and review items.
- `predictions.jsonl`: current normalization of the 71 saved model outputs.
- `daily.csv`, `weekly_counts.csv`: eligible daily values and weekly coverage.
- `after_medication_change.csv`: temporal contexts without a causal claim.
- `review_queue.csv`: unresolved values and exclusions with source identifiers.
- `summary.json`: input/runtime hashes, processing provenance, and counts.

All 71 reports contain text and empty questionnaire arrays. The 61 original
questionnaire-only reports were verbalized; R002 and R009 also received their
form facts as text supplements. Original text and conflicting claims were
retained. References were reviewed and frozen before the 71 extraction calls.
The dashboard reads model output, never references. `saved_candidate_replay`
means Python revalidates recorded model candidates; it is not a new API call.

## A concise demonstration

1. Open **Demo patient 2**. Show four weeks of daily counts, gaps, coverage, and
   medication legends. The M1/M2 labels name the medication, change type, and date.
2. Expand **TXT-R005** and **TXT-R006**. The original count 3 remains stored;
   November 4 uses the corrected count 2 and nausea severity 4. The cumulative
   values 2, 3, and 2 are never summed into 7. **Current record** describes the
   selected version; **Processing completed** describes processing success.
3. Select **Demo patient 1**. November 3 has a supported vomiting zero but
   conflicting nausea ratings 2/5 and 3/5. Both claims are now visible in text.
   November 10's morning count 4 falls to evening count 1 without a correction,
   so the daily count is excluded and the two reports are linked in review.
4. Select **Demo patient 3**. Inspect the unknown date, unknown count, and
   contradictory vomiting claims. November 14 has an explicitly unknown count
   but usable nausea severity. November 8's feared vomiting is hypothetical,
   so it does not become an observed count. Missing days remain gaps.
5. Explain the path: source text → LLM candidates → Python validation and
   normalization → SQLite → daily eligibility rules → SQL and charts. Gold is
   used separately to score extraction, never to fill chart values.
6. Explain the result honestly: all 137 reference observations and 1,233 core
   fields matched in this synthetic integration run. One repeated zero claim
   was merged, and two time phrases differed only in wording. The separate
   20-case validation still has two documented extraction limitations.

```bash
python run_demo.py query --db artifacts/longitudinal-text-demo/patient_reports.sqlite --run-id longitudinal-text-v1 --query weekly
python run_demo.py query --db artifacts/longitudinal-text-demo/patient_reports.sqlite --run-id longitudinal-text-v1 --query medication
python run_demo.py query --db artifacts/longitudinal-text-demo/patient_reports.sqlite --run-id longitudinal-text-v1 --query review
```

The medication query compares symptoms with recorded medication changes, not
every daily dose. TXT-R003's 14:20 episode follows the recorded 13:00 change;
date-only reports on the change day cannot establish precise order. This does
not establish a medication reaction. The query remains in SQL/CLI/CSV; the main
dashboard uses labeled medication markers.

## Optional fresh extraction

Configure `.env` locally before this command. It makes 71 paid API requests.
The saved extraction already supplies the offline demo, so this is optional.

```bash
python run_pipeline.py extract --source data/longitudinal_text/reports.jsonl \
  --provider openai --model gpt-5.4-mini-2026-03-17 \
  --prompt-file prompts/extraction_nausea_grouping.txt \
  --output data/processed/new-longitudinal-text.jsonl
python run_pipeline.py evaluate --source data/longitudinal_text/reports.jsonl \
  --gold data/longitudinal_text/expected.jsonl \
  --predictions data/processed/new-longitudinal-text.jsonl \
  --output artifacts/new-longitudinal-text-metrics.json
```

Use a new cache, output directory, and run ID for a new build. Missing or stale
text results stop the build explicitly. Do not overwrite historical runs or
replace predictions with references.

## Boundaries and historical comparison

The current dataset is derived from known synthetic scenarios. Its 63 generated
supplements have 37 unique raw strings, and generation/extraction use the same
model family. High scores here demonstrate this integration path; they do not
measure broad real-world accuracy. No fine-tuning was performed.

The original mixed-input demo remains available:
`python run_demo.py build --output artifacts/original-mixed-demo`. That default
uses ten original v1 text outputs and 61 direct questionnaire submissions.
Use the explicit all-text command above for the current deliverable.

See [extraction evidence](../results/longitudinal-text-extraction/README.md),
[storage decisions](storage_and_trends.md), and
[integration verification](../results/longitudinal-text-demo/README.md).
