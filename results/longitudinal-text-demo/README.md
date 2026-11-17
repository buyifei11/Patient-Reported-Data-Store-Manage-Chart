# All-text source → LLM → SQLite → dashboard

This snapshot uses **71 actual saved text extractions and zero direct
questionnaire submissions**. It contains three fictional patients across 84
follow-up patient-days, 137 stored symptom observations, and five medication
changes. The original mixed-input exports are preserved in
[Git history](https://github.com/buyifei11/Patient-Reported-Data-Store-Manage-Chart/tree/d839974ede58b65df6e2ef4aafab85185e610c0c/results/longitudinal-demo).
Only the current all-text dashboard snapshot is kept in the working repository.

Open [dashboard.html](dashboard.html) locally. GitHub's file viewer does not
execute HTML; download the file or build the demo with the command below.

## Rebuild without API calls

```bash
python run_demo.py build --dataset data/longitudinal_text \
  --cached-predictions results/longitudinal-text-extraction/predictions.jsonl \
  --run-id longitudinal-text-v1 --output artifacts/longitudinal-text-demo
```

Choose a new output directory if that one exists. The generated SQLite database
is local and excluded from Git; the text exports and standalone HTML here are
byte-for-byte copies of the actual build. No chart values are hand-entered.

The 71 API calls occurred during [extraction](../longitudinal-text-extraction/README.md).
`model_requests: 0` in this build's [summary](summary.json) means **zero additional
calls during offline rebuilding**, not zero LLM usage. The build revalidates
raw saved candidates and recomputes normalization; cached normalized values do
not override that process. No manual evidence exceptions were required here.

## What the stored data show

| Patient | Reported episodes | Usable count days | Days with reports | Count review days |
|---|---:|---:|---:|---:|
| P001 | 37 | 23/28 | 25/28 | 1 |
| P002 | 39 | 22/28 | 23/28 | 1 |
| P003 | 27 | 16/28 | 21/28 | 3 |

Across all patients there are 61 usable count days, five count review days, and
18 missing count days. These 84 daily statuses are mutually exclusive. The
12 review items are field/source diagnostics, so they are not a count of unique
days. Reported episode sums include eligible partial cumulative values; they
are not complete estimates of every actual episode.

- TXT-R006 replaces TXT-R005 while preserving the original. P002 November 4
  uses count 2 and nausea severity 4, never the summed count 7.
- P001 November 3 retains conflicting nausea 2/5 versus 3/5 while vomiting zero
  remains eligible. November 10's unexplained count decrease 4 → 1 stays in review.
- P003 retains unknown dates, unknown counts, contradictory claims, and
  hypothetical vomiting without filling missing counts with zeros.
- Medication legends identify starts and dose changes; they do not establish
  symptoms after each daily dose or causal effects.

## Verification and files

[validation.json](validation.json) records **54/54 passing checks** of SQLite integrity and
foreign-key checks, exact source/candidate preservation, CSV/query/dashboard
data equality, weekly reconciliation, and the correction/conflict/gap scenarios.
[build_input_audit.json](build_input_audit.json) records the actual guarded build:
reads of `expected.jsonl` and `seeds.jsonl` were prohibited, and none occurred.
Only source reports, patient/change metadata, actual saved predictions, and
runtime/SQL/template files entered the build.

[browser_check.json](browser_check.json) records a browser smoke check of all
three patient selections, source expansion, labels, chart gaps, review details,
and the 71-text/0-questionnaire footer. No console errors were observed.
The complete offline unit/integration suite also passed: 245 tests via
`python -m unittest discover -s tests -q`. Frozen inputs, source bindings, model
response IDs, and prompt/runtime fingerprints were verified unchanged.

`predictions.jsonl` contains the build's replayed results and original inference
metadata. `daily.csv`, `weekly_counts.csv`, `after_medication_change.csv`, and
`review_queue.csv` are actual SQLite query exports. Reference-based accuracy
belongs to the separate extraction evaluation; a successful build is not an
independent accuracy test.

See the [walkthrough](../../docs/demo_walkthrough.md) for commands and a short
presentation sequence. This is a local synthetic-data prototype, not a clinical
deployment.
