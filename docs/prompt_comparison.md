# Temporal prompt comparison: results and decision

Experiment date: 2026-11-15. Model: `gpt-5.4-mini-2026-03-17`. **Decision: retain v1 as the default; keep v2 as an experimental candidate.** Date interpretation improved, but the new prompt did not meet the predeclared requirement to avoid material per-report regressions.

## What changed and what was controlled

Added 20 development reports and 20 held-out reports with separately authored reference answers. Together with the original 10, the repository now has 50 reports and 61 reference observations. The new examples are diagnostic cases, not the future four-week longitudinal dataset. See [dataset roles](../data/README.md).

Only the prompt's `day_reference` instruction changed. It explains current-report `tonight` and other same-day expressions, separates a known day from whether a symptom occurred, and warns against assuming dates for unanchored or historical statements. The model, schema, normalizer, evaluator, and request settings were identical for both prompt versions. The experiment added no training or few-shot examples.

The candidate prompt was frozen before the primary implementer viewed the held-out cases. Authors and a separate reviewer checked labels and cross-split narrative overlap before inference; two near-template narratives were rewritten at that stage. All inputs and runtime files were hashed before the first call. Prompts, labels, and scoring rules were not revised after viewing outputs. The original 10 sources, references, and first-run snapshot remain unchanged.

We ran one paired round over 30 development reports and two paired rounds over the same 20 held-out reports: **140 requests**, with alternating prompt order and no retries. The repeated test set still contains only 20 independent cases. [Frozen protocol](prompt_experiment.md) and [input manifest](../results/temporal-prompt-v2/manifest.json).

## Measured results

All fractions below include failed/missing observations in their reference denominators. "Completed" means extraction and normalization succeeded, not merely that the API returned text.

| Measure | Development v1 | Development v2 |
| --- | ---: | ---: |
| Completed reports | 29/30 | 30/30 |
| Matched observations | 35/36 | 36/36 |
| Known dates | 31/33 | 33/33 |
| Known counts | 16/17 | 17/17 |
| Candidate day-reference checks | 11/13 | 13/13 |
| All targeted extraction checks | 19/24 | 23/24 |

| Measure | Held-out r1 v1 | Held-out r1 v2 | Held-out r2 v1 | Held-out r2 v2 |
| --- | ---: | ---: | ---: | ---: |
| Completed reports | 18/20 | 18/20 | 17/20 | 17/20 |
| Known dates | 19/23 | 21/23 | 16/23 | 19/23 |
| Candidate day-reference checks | 8/10 | 9/10 | 8/10 | 9/10 |
| Known counts | 8/11 | 8/11 | 7/11 | 8/11 |
| Known count scopes | 9/14 | 9/14 | 7/14 | 9/14 |
| Assertion agreement | 22/25 | 23/25 | 19/25 | 21/25 |
| Observation F1 | 0.880 | 0.920 | 0.809 | 0.857 |
| All targeted extraction checks | 14/17 | 13/17 | 14/17 | 14/17 |
| Matched reference-null fields overfilled | 0/97 | 1/97 | 0/97 | 0/97 |

The date scores are end-to-end pipeline measures, not pure model metrics. The H016 matching limitation below affects round 1's date, assertion, detection, and overfill scores. No single pooled accuracy or claim of statistical superiority is appropriate.

## Improvements and remaining errors

**The clean temporal gain is reproducible on H004.** Its conditional statement, `Should vomiting interrupt the concert tonight, I plan to leave at intermission.`, has an unknown date under v1 and the correct submission-local date under v2 in both held-out rounds. Both retain `hypothetical` and a null count. D001 and D002 also improve from unknown to today on the development set, covering hypothetical and actual "tonight" statements.

**R010 does not demonstrate a paired gain in this experiment.** Both prompts now get it right. The original v1 failure did not recur, illustrating why a single before/after example is weak evidence. That historical failure and its original output have been preserved.

**Material regressions prevent default replacement.** In held-out round 1, H003's absence during a rehearsal changes from a bounded `window` to `day_to_date`, potentially broadening a zero count to an unsupported interval. H006 changes a break-window count to an event, and H016 changes a current daily total to a window. In round 2, v2 changes H015's straight apostrophe to a curly apostrophe in its evidence quote; exact provenance validation rejects the report. These are actual recorded regressions, even though several aggregate scores rise. The sample does not establish that every such difference is a stable causal effect of the prompt revision.

**Shared extraction failures remain.** H010 is a total across four dates, but all four held-out outputs use `day_total` and provide a quote that omits the time expression. H012 has a correct candidate date and completed-day zero, but its quote omits the explicit calendar anchor, so grounding rejects it. H002 is incorrectly split into two observations in both prompt versions; its combined window count is not preserved. D016's unspecified severity context is interpreted as current in both development runs, although normalized severity correctly remains null.

**A deterministic normalization defect was discovered in H016.** The source says `from midnight today through this submission`, which is compatible with the current-day questionnaire. The normalizer's conservative earlier-window check rejects any quote containing `midnight`, so it retains text count 5 and form count 3 separately in all four runs instead of flagging their conflict. The baseline has this defect too; it is not a newly invented count or an error that model training alone would solve. This shared code defect is recorded without changing the frozen experiment. It should be fixed and regression-tested in a separately versioned follow-up.

**H016 also exposes an evaluation limitation.** With a full text quote, both separate observations have equally strong evidence overlap with the one merged reference, and the matcher leaves it ambiguous. In v2 round 1 the shorter text quote gives the form observation the unique best match. That creates both one extra matched date/assertion and the recorded overfill of 3 against a null reference. The number 3 is from the form, not fabricated. The round-1 overfill difference alone is therefore not a sound reason to reject v2; the concrete scope regressions and H015 failure are.

Round 1's known-date gain of two consists of H004's temporal improvement plus that H016 alignment effect. Round 2's gain of three consists of H004 (+1), recovery of H019's three observations from a baseline time-phrase casing failure (+3), and v2's new H015 failure (-1). This accounting avoids attributing every higher date score to better temporal reasoning.

Exact `time_text` boundary differences remain visible in full metrics. They were neither repaired nor used to retune the prompt. A wider valid excerpt is not automatically a semantic error, while changing source punctuation or casing can violate the current exact-evidence contract.

## Usage, artifacts, and reproduction

All 140 calls returned usage: 264,408 input tokens (207,616 cached), 16,360 output tokens, and zero reasoning tokens. At the listed prices recorded in [model selection](model_selection.md), this implies approximately **$0.13179**. It is a calculated token-cost estimate, not an invoice. Summed per-request elapsed time was 198.68 seconds; median was 1.39 seconds. These are one small run's timings, not a performance benchmark.

The [machine-readable summary](../results/temporal-prompt-v2/summary.json) contains all six runs. Each run has its own `*.predictions.jsonl` and `*.metrics.json` in [the experiment directory](../results/temporal-prompt-v2/), including failures, exact model text, token usage, prompt identity, and input/code hashes. Provider request IDs are omitted; credentials are never included.

To rescore the frozen outputs without API calls, use a new ignored directory so the saved metric files remain intact:

```bash
mkdir -p work/temporal-review
cp results/temporal-prompt-v2/manifest.json results/temporal-prompt-v2/*.predictions.jsonl work/temporal-review/
python run_experiment.py score --directory work/temporal-review --split development
python run_experiment.py score --directory work/temporal-review --split heldout
```

This verifies frozen data, prompts, runtime code, and recorded model/prompt metadata. It deliberately refuses rescoring after those files change; use the experiment's Git revision for exact reproduction. Existing outputs are never overwritten. No score command reads credentials or makes a model request.

The general extraction CLI now supports `--prompt-file`. Default `prompts/extraction.txt` remains identical to v1. To explicitly investigate v2 on additional development data, select `--prompt-file prompts/extraction_v2.txt` and choose a new output path. Do not silently promote that run to a held-out evaluation.

## Decision and next work

The narrow temporal rule is useful, but v2 does not meet the frozen adoption criterion. Keep v1 as the default and preserve v2 for further development. This does not certify v1 as reliable; both versions show substantive extraction and normalization limitations on the harder cases.

The next bounded improvement should first fix H016's deterministic reconciliation defect, then address count-scope preservation and exact evidence grounding with separately versioned tests and prompts. These observed held-out cases become known regression examples if used for that work; a later independent claim needs a new frozen test set. Fine-tuning is not justified by this experiment, and no training was performed.
