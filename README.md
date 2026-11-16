# Patient-Reported Data: Store, Manage & Chart

A Track B prototype for fictional nausea/vomiting reports: extract source claims,
validate them, preserve history in SQLite, apply counting/correction rules, and
show patient trends with coverage and unresolved values. All deliverables are in
English. No real patient information is used.

The current [all-text longitudinal demo](results/longitudinal-text-demo/README.md)
uses **71 actual LLM text extractions, with zero directly processed questionnaires**.
The former questionnaire facts were verbalized and reviewed before extraction;
all ten original text reports were retained, including their conflicts and
correction history. The frozen run recovered all 137 reference observations and
all 1,233 normalized core fields. One repeated source claim produced an extra raw
candidate that Python merged, and two time phrases differ only in wording.
This is a synthetic integration result, not evidence of general 100% accuracy.
See the [extraction results](results/longitudinal-text-extraction/README.md).

A separate [five-report text pilot](data/text_pilot/README.md) now contains actual
LLM-generated feedback, reviewed references, and generation provenance. Its
[first extraction baseline](results/text-pilot-extraction/README.md) and a bounded
[evidence-prompt comparison](results/text-pilot-evidence/README.md) are recorded
separately. The original mixed-input dashboard is preserved as a historical
baseline alongside the new all-text demo.

A separate [ten-report text set](data/text_validation/README.md) has recorded
[original/evidence](results/text-validation-comparison/README.md),
[broad grouping](results/text-validation-grouping/README.md), and
[compact grouping](results/text-validation-compact/README.md) experiments.
Whole-report passes were 2/10, 8/10, 7/10, and 8/10, respectively. A subsequent
[two-stage nausea follow-up](results/text-validation-nausea/README.md) repairs the
daily-context Python gap first: replaying the saved compact output yields correct
normalized values and structure for 10/10 reports, while preserving raw duplicate
candidates. A separate one-rule prompt trial removes those duplicates but creates
one invalid quote, leaving 9/10 usable reports. At that stage the Python fix was
retained and the new prompt remained experimental. The user subsequently accepted the verified TV007
quotation omission as an evidence-only exception: a separate
[reviewed replay](results/text-validation-nausea/reviewed-evidence/README.md)
contains 10/10 accepted reports with unchanged semantic values, and no new model
calls. The original strict score remains 9/10. Sources, references, and the default prompt remain
unchanged. These cases are known development/regression material, not a fresh
evaluation set; normalized correctness and strict whole-report correctness are
reported separately.

The [twenty-report validation set](data/text_holdout/README.md) now has a
[first frozen extraction result](results/text-holdout-extraction/README.md):
20/20 reports processed, 18/20 fully correct, 339/341 candidate fields correct,
and 260/261 normalized core fields correct. An unknown-count scope omission and
a morning/current context error remain. All 29 observations and seven issue
flags are present; no quote waiver, retry, or post-result tuning was used.

## Run the complete offline demo

Use Python 3.11 or newer; tested with Python 3.14.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -q
python run_demo.py build --dataset data/longitudinal_text \
  --cached-predictions results/longitudinal-text-extraction/predictions.jsonl \
  --run-id longitudinal-text-v1 --output artifacts/longitudinal-text-demo
```

Open **`artifacts/longitudinal-text-demo/dashboard.html`** in a browser. No server, API key, or
internet connection is needed after dependency installation. Use a new output
directory for another build; existing runs are never overwritten.

The demo has **71 reports, three patients, and 28 follow-up days per patient**.
It replays all 71 saved model candidate batches through the current normalizer,
then builds SQLite, daily summaries, SQL exports, and the dashboard. It never
reads reference answers or fact seeds. Extraction made 71 API requests; this
offline rebuild makes zero additional requests. See the
[demo walkthrough](docs/demo_walkthrough.md) for a presentation sequence.

A selected [generated example](results/longitudinal-text-demo/dashboard.html), query
exports, and [validation record](results/longitudinal-text-demo/validation.json) are saved
for review. Download the HTML file to open that snapshot locally; GitHub's file
viewer does not execute the dashboard.

Generated files include `patient_reports.sqlite`, `predictions.jsonl`,
`daily.csv`, `weekly_counts.csv`, `after_medication_change.csv`,
`review_queue.csv`, `summary.json`, and the standalone dashboard.

```bash
python run_demo.py query --db artifacts/longitudinal-text-demo/patient_reports.sqlite --run-id longitudinal-text-v1 --query weekly
python run_demo.py query --db artifacts/longitudinal-text-demo/patient_reports.sqlite --run-id longitudinal-text-v1 --query medication
python run_demo.py query --db artifacts/longitudinal-text-demo/patient_reports.sqlite --run-id longitudinal-text-v1 --query review
```

Queries open the database read-only. Weekly counts include reporting coverage;
missing values do not become zeros. The medication query compares symptoms with
recorded starts, stops, or dose changes, not each day's actual medication intake.
It remains available through SQL, the CLI, and CSV exports; the dashboard uses
labeled medication markers rather than a separate timing-comparison table.

The [original mixed-input snapshot](results/longitudinal-demo/dashboard.html)
and its [validation record](docs/prototype_validation.md) remain unchanged.
`python run_demo.py build --output artifacts/original-mixed-demo` still builds
that historical default: ten saved text extractions plus 61 direct questionnaires.
Use the explicit dataset, cache, and run ID above for the current all-text demo.

## What is implemented

| Component | Behavior |
| --- | --- |
| Data contract | Strict v0.2 schemas for source reports, candidates, normalized observations, and references. |
| Text extraction | OpenAI Responses API and optional Ollama adapter, with source-only model input and explicit provenance. |
| Normalization | Relative dates, literal evidence checks, clock-boundary checks, severity eligibility, and compatible text/form reconciliation. |
| SQLite | Immutable source IDs and extraction runs; failed results, evidence, and correction history retained. |
| Daily statistics | Complete replacements, cumulative no-sum rules, explicit zeros, missing days, field-specific eligibility, and review reasons. |
| SQL | Weekly reported counts with coverage; symptoms relative to recorded medication changes. |
| Dashboard | Patient selection, count/severity trends, labeled medication changes, weekly coverage, concrete review explanations, and expandable source records. |
| Validation | Offline tests for schemas, clients, time boundaries, corrections, aggregation, database integrity, queries, and integration. |

R006 corrects R005's vomiting count from 3 to 2 while retaining nausea severity 4.
The original remains in the database, and the trend uses 2. The three cumulative
records are not summed into 7. Unknown/conflicting counts and unresolved event
overlap stay out of daily totals and remain reviewable.

## Extraction experiments and model configuration

The cloud model used here is `gpt-5.4-mini-2026-03-17`. The current all-text run
explicitly selects `prompts/extraction_nausea_grouping.txt`, evaluated on the
separate 20-case set before this integration run. The CLI default remains the
original v1 prompt for backward compatibility; v2/v3 experiments and their
regressions are retained. No fine-tuning was performed. Historical experimental
outputs are preserved unchanged; their frozen runtime is available in Git.

| Evidence | Purpose |
| --- | --- |
| [First development run](docs/development_run.md) | Ten original reports and the first actual model outputs. |
| [Temporal comparison](docs/prompt_comparison.md) | 140 paired calls comparing v1/v2. |
| [Scope/evidence comparison](docs/prompt_v3_comparison.md) | 280 paired calls on 50 known and 20 fresh cases, v1/v3. |
| [First normalization fix](docs/normalization_fix.md) | Offline replay of the midnight-to-submission reconciliation correction. |
| [Time-boundary fixes](docs/time_boundaries.md) | Current range variants and rejection of cutoff/interval clocks as episode times. |

For optional fresh cloud extraction, configure `.env` locally with
`OPENAI_API_KEY` and `OPENAI_MODEL`; `.env.example` has the accepted keys. Never
commit a key. Environment values take precedence over `.env`. No shell code or
variable expansion is executed by the loader.

```bash
python run_pipeline.py extract --source data/longitudinal_text/reports.jsonl \
  --provider openai --prompt-file prompts/extraction_nausea_grouping.txt \
  --model gpt-5.4-mini-2026-03-17 \
  --output data/processed/new-text-run.jsonl

python run_pipeline.py evaluate \
  --source data/longitudinal_text/reports.jsonl \
  --gold data/longitudinal_text/expected.jsonl \
  --predictions data/processed/new-text-run.jsonl \
  --output artifacts/new-text-run.metrics.json
```

Extraction makes API requests; evaluation does not. It sends only source text,
not questionnaires, metadata, or gold. Requests use strict output, reasoning
effort `none`, a 2,048 output-token cap, and `store=false`; this flag alone is not
a zero-retention guarantee. Errors remain explicit and there are no automatic
retries. Choose a new output path each time. If using `--limit`, evaluation still
includes all supplied reference reports, so unrequested reports count as missing.

The optional local adapter requires an explicitly selected installed model:

```bash
python run_pipeline.py extract --provider ollama --model YOUR_INSTALLED_MODEL \
  --output data/processed/local-run.jsonl
```

See [model selection](docs/model_selection.md) for the selection rationale and
limitations. Installation alone is not evidence of task suitability.

## Files to read

| Location | Purpose |
| --- | --- |
| `docs/design.md`, `docs/storage_and_trends.md` | Field meanings, schema, responsibilities, and counting rules. |
| `docs/demo_walkthrough.md` | Setup, live walkthrough, query commands, and trade-offs. |
| `data/longitudinal/` | Four-week sources, patients, medication changes, and generation notes. |
| `data/raw/`, `data/gold/`, `data/dev/`, `data/heldout/`, `data/heldout_v3/` | Separate extraction-development and validation sources/references. |
| `src/normalization.py`, `src/aggregation.py` | Code-owned time, reconciliation, correction, and eligibility rules. |
| `src/store.py`, `sql/` | SQLite storage and executable queries. |
| `src/demo.py`, `src/dashboard.py`, `web/dashboard.html` | Stored-data demo build and offline chart renderer. |
| `docs/evaluation.md`, `results/` | Metric definitions and selected immutable experimental artifacts. |
| `tests/` | Offline behavioral tests with mocked clients and temporary databases. |

The [dataset guide](data/README.md) distinguishes longitudinal sources from the
70 diagnostic reports and explains overlap. Routine databases/exports are ignored
under `artifacts/`; selected review artifacts are versioned under `results/`.

## Practical limits

This is a local synthetic-data prototype, without authentication, clinical
validation, or a manual review/write-back workflow. Event/window overlap is not
automatically resolved, and unsupported interpretations stay visible for review.
The model can still make semantic errors that pass structural checks. A passing
code test or a completed extraction is not a claim of correct clinical data.
Further prompt work should isolate changes and use new independent cases when
making generalization claims, rather than silently retuning on reviewed outputs.
