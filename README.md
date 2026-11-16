# Patient-Reported Data: Store, Manage & Chart

Track B prototype for structuring synthetic patient reports, storing them over time, and showing symptom trends. All submission artifacts are in English.

## Current milestone

The extraction and evaluation milestone is implemented: source validation, LLM text extraction, deterministic normalization, and comparison with authored reference answers. The first real cloud run is documented in [the development-run report](docs/development_run.md).

| Component | Status |
| --- | --- |
| Data contract | v0.2 design and executable strict schemas. |
| Starter data | 10 reports, 3 fictional patients, 15 reference observations, 3 targeted extraction checks. |
| Model integration | OpenAI Responses API and optional local Ollama adapter; no automatic model fallback. |
| Normalization | Relative dates, evidence checks, severity rules, and compatible source reconciliation. |
| Evaluation | Detection, per-field known/null accuracy, assertions, issue detection, and pre-reconciliation checks. |
| Offline tests | Schema, client failure paths, normalization, metrics, and CLI boundaries. No API charges for tests. |
| Database, cross-report aggregation, SQL, charts | Not implemented yet. Correction links are validated, but effective versions and cumulative totals are not computed. |
| Four-week data and held-out evaluation | Not prepared yet. |

The original reports and reference answers are unchanged. They were drafted with AI assistance and reviewed against the documented rules; they are development fixtures, not independently annotated clinical ground truth. Model outputs and code-test success do not establish clinical validity.

## Quick start

Use Python 3.11 or newer. This milestone was tested with Python 3.14.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_pipeline.py validate
python -m unittest discover -s tests -q
```

Validation and tests work without credentials. Each JSONL file contains one object per line; records are linked by `report_id`.

## Configure the cloud pilot

The provisional model is `gpt-5.4-mini-2026-03-17`. See [model selection](docs/model_selection.md) for task fit, alternatives, cost assumptions, and the evidence required before final adoption. The installed `llama3:8b` is an optional baseline, not the default selection.

If `.env` does not already exist, copy `.env.example` to `.env`. Open it in VS Code and set `OPENAI_API_KEY` locally. Create a key through the [OpenAI API dashboard](https://platform.openai.com/api-keys). Do not paste a key into chat, commit it, or include it in screenshots. `.env` is ignored by Git; `.env.example` contains no key.

The loader accepts `KEY=VALUE` entries, optional surrounding quotes, and comments on separate lines. It does not execute shell expressions or expand variables. Environment variables take precedence. Only `OPENAI_API_KEY` and `OPENAI_MODEL` are supported in this file.

## Run extraction, then evaluation

```bash
python run_pipeline.py extract \
  --provider openai \
  --model gpt-5.4-mini-2026-03-17 \
  --limit 10 \
  --output data/processed/my-dev-run.jsonl

python run_pipeline.py evaluate \
  --predictions data/processed/my-dev-run.jsonl \
  --output artifacts/my-dev-run.metrics.json
```

Use a new output filename for each run. Existing files are never overwritten. Extraction reads only source reports, sends only their text to the model, and saves actual candidates before normalization. It never reads gold. Evaluation is a separate command that reads saved output and references. `--limit` truncates extraction; evaluation still includes all reference reports, so unrequested reports count as missing unless you explicitly supply matching source and gold subsets.

Each result records `status`, candidates, observations, exact model output, an error code when needed, model/prompt/source/code metadata, and elapsed time. A failed report differs from a successful empty extraction. Valid candidates survive a normalization failure so the extraction stage can still be inspected. API/configuration failures stop the run; semantic failures are recorded per report. There are no automatic retries.

OpenAI requests use strict structured output, reasoning effort `none`, a 2,048 output-token cap, and `store=false`. This is a synthetic-data prototype; that storage flag alone is not a guarantee of zero provider retention.

The optional local adapter requires an explicitly selected model already installed in Ollama:

```bash
python run_pipeline.py extract --provider ollama --model YOUR_INSTALLED_MODEL \
  --output data/processed/local-dev-run.jsonl
```

## Files to read

| File | Purpose |
| --- | --- |
| `docs/design.md` | Field meanings, responsibilities, and counting rules. |
| `docs/model_selection.md` | Why a model is a candidate, and how adoption will be justified. |
| `docs/evaluation.md` | Metric definitions, matching, and limitations. |
| `docs/development_run.md` | Actual first-run results and error interpretation. |
| `data/raw/reports.jsonl` | Original synthetic reports. |
| `data/gold/expected.jsonl` | Authored answers; never model input. |
| `prompts/extraction.txt` | Generic text-extraction instructions. |
| `src/schema.py` | Required fields, types, and input contracts. |
| `src/openai_client.py`, `src/llm.py` | Cloud and local inference adapters. |
| `src/normalization.py` | Code-owned dates, evidence, scopes, and reconciliation. |
| `src/evaluation.py` | Comparison with reference answers. |
| `src/pipeline.py`, `run_pipeline.py` | Configuration, JSONL I/O, and command orchestration. |
| `tests/` | Offline behavioral tests using controlled inputs and mocked HTTP. |

Routine outputs in `data/processed/` and `artifacts/` are ignored. A selected synthetic run is preserved in `results/gpt54mini-dev-v1/` for review without an API key. Re-score it with:

```bash
python run_pipeline.py evaluate \
  --predictions results/gpt54mini-dev-v1/predictions.jsonl \
  --output artifacts/review-dev-v1.metrics.json
```

## Limits and next step

The first run found a real temporal extraction error: R010's `tonight` was retained as text but not recognized as today's date. Three other mismatches are wider time-phrase excerpts with the same temporal meaning. Keep these distinctions visible; do not relabel a detection F1 of 1.0 as perfect extraction.

Normalization supports a bounded set of English temporal expressions, ISO or English month/day/year dates, and explicit clock times. Unsupported or contradictory candidates fail visibly. Passing schema/evidence checks cannot prove that every semantic interpretation is correct. A single-day observation representation cannot allocate multi-day totals.

Next, address the temporal extraction gap and evaluate separately authored cases with a frozen prompt. Then add SQLite, correction-aware aggregation, two SQL queries, and patient trends. Full follow-up coverage and medication-change records remain future inputs.
