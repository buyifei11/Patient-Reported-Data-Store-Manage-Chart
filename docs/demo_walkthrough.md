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

## Interview plan: 30 minutes

The brief allocates **5 minutes to the candidate introduction, 15 minutes to the
prototype and design decisions, and 10 minutes to technical questions,
trade-offs, and AI usage**. Use the introduction for your actual background,
relevant experience, and why you chose this problem, then transition to the
prototype. Do not spend that entire section presenting the project.

Slides are optional; the brief requires a live prototype, not a slide deck.
Four short slides are enough: the provider's problem; the pipeline and schema;
validation results; and decisions and limitations. Switch to the actual terminal,
dashboard, and source records for the demonstration.

Use the [16:9 pipeline image](presentation/pipeline-overview.png) directly in
slides; the [SVG version](presentation/pipeline-overview.svg) remains editable.
An optional separate introduction slide can summarize your own background.
The repository already supplies written design and evaluation documentation;
a long additional report is unnecessary for this presentation.

| Time within the 15-minute walkthrough | What to show and explain |
| --- | --- |
| 0:00–1:30 | The provider's 30-second need, the oncology nausea/vomiting scope, and the pipeline. References feed evaluation, not chart values. |
| 1:30–3:00 | Open the prepared dashboard and database. Explain their real saved LLM provenance. Rebuilding is optional and belongs to rehearsal, not the required live sequence. |
| 3:00–8:00 | Use the prepared dashboard. Use patient 2 and TXT-R006 to follow source text, candidates, normalized values, and the corrected count 2. Then show patient 1's TXT-R002: conflicting nausea ratings are reviewed while the supported vomiting zero remains usable. |
| 8:00–11:00 | Run the two main queries: weekly counts with coverage, then peak nausea dates. Keep the medication-change query as a backup. Explain the result and open its source report. |
| 11:00–13:00 | Contrast 18/20 strict whole-report matches on the separate frozen validation set with 71/71 normalized core-and-issue matches on known synthetic integration cases. The latter has 69/71 literal matches and does not establish general 100% accuracy. |
| 13:00–14:30 | Explain AI-assisted coding, synthetic text generation, and extraction; Python owns validation, date arithmetic, correction and counting rules. Discuss missing data, narrow symptom scope, and temporal association versus causation. |
| 14:30–15:00 | State what the prototype demonstrates and hand over to questions. |

## Prepared SQL demonstration: no rebuild required

Complete the offline setup before the interview. The three commands below read
`artifacts/longitudinal-text-demo/patient_reports.sqlite` with run
`longitudinal-text-v1`; this is the current all-text dataset. No API key, network,
model call, database write, or new database is involved. Run from the repository
root in the VS Code terminal. The helper uses only Python's standard library.

### Main query 1: weekly vomiting counts and coverage

```bash
.venv/bin/python run_queries.py weekly
```

The default patient is P001. This executes [weekly_counts.sql](../sql/weekly_counts.sql)
with a bound patient filter and prints five weekly rows. Focus on the week of
**2026-11-09**: **15 reported episodes, 6/7 usable count days, one review day**.
Explain that incomplete reporting prevents treating this as a complete weekly
frequency. Daily cumulative updates were already reconciled before SQL sums the
daily rows; they are not added as separate submissions.

| Display column | Meaning |
| --- | --- |
| `Week of` | Monday starting the calendar week. Follow-up is clipped to November 1-28, so the October 26 bucket contains only November 1. |
| `Count` | Sum of eligible daily reported values; `NULL` if none are usable. |
| `Coverage` | Days with usable counts / registered follow-up days in that week. |
| `Review days` | Daily counts excluded because an unresolved issue affects counting. |
| `Missing days` | No usable daily count and no count-review classification; this can include a report that omits the count. |
| `Partial days` | Usable cumulative reports covering today so far. |
| `Full days` | Usable explicit completed-day reports. |

`Coverage` numerator + `Review days` + `Missing days` equals the follow-up
denominator. This is count coverage, not the number of submissions.

Suggested explanation: “This week has 15 reported episodes across six usable
days. The remaining day needs review, so I show coverage beside the total.”

### Main query 2: highest reported nausea severity

```bash
.venv/bin/python run_queries.py peak
```

[peak_nausea.sql](../sql/peak_nausea.sql) selects only usable daily-worst nausea
ratings, calculates the maximum for the selected patient and run, and returns
**all tied dates**. It does not compare vomiting counts with severity ratings.

For P001 the current result is **2026-11-10, nausea 5/5**. `Vomiting count` is
`NULL` and `Count status` is `review`: the nausea rating is usable even though
that day's vomiting counts conflict. `NULL` is not zero. The source IDs are
`TXT-L-P001-10` and `TXT-L-P001-10-AM`.

In the dashboard select **Demo patient 1**, inspect November 10, and expand
these two source records. Their vomiting counts decrease from 4 at 10:00 to 1
at 20:30 without a correction. Explain field-specific eligibility: a count
conflict does not invalidate an independently supported nausea score.

Suggested explanation: “November 10 has the highest usable nausea rating, 5/5.
The conflicting vomiting count stays unresolved; the source reports remain
available for review.”

### Backup query 3: symptoms relative to medication changes

```bash
.venv/bin/python run_queries.py medication --patient P002 --report TXT-R003
```

This executes [after_medication_change.sql](../sql/after_medication_change.sql)
with patient and report filters. The actual result shows Medication B change
`M003` at **2026-11-03 13:00 -06:00**, and a vomiting event at **14:20** on the
same date. `Order=after` establishes time order relative to that recorded change.
It does not prove a medication reaction or identify each day's dose.

`Review=yes` is expected here: a single event is not an established daily total,
so count aggregation needs review even though the exact event time is usable.
Other rows can be `indeterminate`, `unknown_date`, or `at_change_time`; definite
before-change rows are excluded. Each result is an observation/change pair, not
necessarily a unique symptom event. One observation can relate to several changes.

Suggested explanation: “This event was reported after the medication change.
I preserve that timing relationship without claiming the medication caused it.”

### Useful controls and rehearsal

```bash
# Show the exact SQL and bound inputs, then execute it.
.venv/bin/python run_queries.py peak --show-sql
# Switch patient explicitly.
.venv/bin/python run_queries.py weekly --patient P002
# Get complete machine-readable rows, including evidence for medication timing.
.venv/bin/python run_queries.py medication --patient P002 --report TXT-R003 --format json
```

The table view hides lengthy JSON evidence, but does not change query values.
Missing databases, unknown run/patient/report selections, and invalid argument
combinations produce explicit errors. If there are no eligible rows, the output
says so; this is not interpreted as zero symptoms. `--report` applies only to the
medication query. All three prepared queries are parameterized.

Keep SQL files open in VS Code beside the terminal. Run the first two queries
live, read one informative row each, then open its source in the prepared
dashboard. Reserve the third query for questions. Budget 2-3 minutes for this
sequence; rehearse beforehand rather than installing dependencies live.

If building a different database during rehearsal, supply its matching path and
run ID with `--db PATH --run-id RUN`. Never point at the historical mixed-input
`artifacts/demo` accidentally. The original `run_demo.py query` commands remain
available unchanged.

A rebuild is optional: use the setup command with a new output directory because
existing outputs are protected. The brief does not require rebuilding a database
or writing SQL from scratch during the interview. If fresh inference is requested,
one report can be extracted separately; disclose whether a response is saved or
new, and do not rerun all 71 requests as part of the main demonstration.

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
This full rerun is for development, outside the interview sequence. The saved
extraction already supplies the offline demo, so no rerun is required. For an
explicitly requested one-report demonstration, add `--limit 1` to the extraction
command and use a fresh output path. It selects TXT-R001 from the full source
file. Do not evaluate that single output against all 71 references and describe
the resulting missing reports as extraction failures.

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
