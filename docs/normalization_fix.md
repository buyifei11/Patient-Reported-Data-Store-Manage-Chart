# Daily-range reconciliation fix

The normalizer now reconciles a vomiting count covering `from midnight today
through this submission` with the current-day questionnaire when the candidate
has `day_to_date` scope. Previously, the word `midnight` caused the conservative
earlier-snapshot filter to reject that match.

For H016, text count **5** and questionnaire count **3** cover the same interval.
The corrected result is one observation with `assertion: present`, `count: null`,
`count_scope: day_to_date`, and the issue `count / conflicting_sources`. Its
original text quote and questionnaire evidence are retained. The local date is
still `2026-11-13` in Asia/Tokyo, despite the submission timestamp's UTC date.

## Scope and boundaries

The change masks a recognized `from midnight today` range ending in
`through`, `until`, or `to` plus `this submission` or `now`, solely in a temporary
string used by the earlier-snapshot filter. The original quote and `time_text`
are never edited. All other compatibility checks still apply, including symptom,
date, assertion, count scope, event time, medication relation, and remaining
earlier-time qualifiers in the quote.

`By noon today`, `as of 10 today`, and `from midnight today through noon` remain
separate from a later questionnaire total. An extracted `window` is not silently
changed to `day_to_date`. The same compatibility rule also applies to comparable
daily text claims when no questionnaire is present.

This is a bounded English-pattern fix, not a general temporal-language parser.
Other wording or broad quotes containing unrelated earlier-time qualifiers may
still require future work. No prompt, model, extraction candidate, source report,
reference label, or evaluator changed in this follow-up.

## Offline replay results

All **140 saved outputs** from the six runs in `results/temporal-prompt-v2/` were
replayed through the updated normalizer. They still represent **50 distinct
reports**, not 140 independent cases. There were **zero model requests** and no
API charges for the replay.

| Saved run | Changed reports | H016 after replay |
| --- | --- | --- |
| Development v1, round 1 | None | Not in this split. |
| Development v2, round 1 | None | Not in this split. |
| Held-out v1, round 1 | H016 only | One observation; count null with conflict; all evidence retained. |
| Held-out v2, round 1 | None | Still two observations because the extracted scope is `window`. |
| Held-out v1, round 2 | H016 only | One observation; count null with conflict; all evidence retained. |
| Held-out v2, round 2 | H016 only | One observation; count null with conflict; all evidence retained. |

Every other observation and status is unchanged. Completion counts and targeted
extraction scores are unchanged in all six runs. The three corrected H016 results
now match the authored reference and recover its conflict issue. In those runs,
observation F1 changes respectively from 0.880 to 0.939, 0.809 to 0.870, and 0.857
to 0.917. Those gains come from correct reconciliation and unambiguous matching;
they are not evidence of improved LLM extraction. The remaining v2 round-1 scope
error and evidence-matching limitation are still visible.

Full results are in the [summary](../results/normalization-midnight-v1/summary.json),
[changed-record comparison](../results/normalization-midnight-v1/changes.json),
and six separate metric files in that directory. The original experiment
artifacts and scores are unchanged; its frozen runtime is Git revision
`be6114310772db621475420e285ede57fa623a17`.

## Verification and reproduction

Seven normalization regression tests cover conflicting and equal positive
counts, zero-versus-positive conflicts, earlier endpoints, other snapshot
qualifiers, incorrect window scope, timezone handling, text-only reconciliation,
and evidence/input preservation. New failing cases were exercised before the
fix. Seven replay tests check failure preservation, provenance, overwrite
protection, unchanged historical artifacts, and no settings/network access.
The full offline suite passes **156 tests**; all 50 source/reference fixtures
also validate.

From the project root with the Python environment activated:

```bash
python -m unittest discover -s tests -q
python scripts/replay_normalization.py --output artifacts/normalization-replay
```

Choose a new output directory for each replay. The script verifies the original
manifest, saved model/prompt/source/code metadata, and original scores before
replaying. Frozen inputs other than `src/normalization.py` must remain unchanged;
the evaluator and reference labels cannot drift. Each new result records hashes
of the original artifacts, current runtime, and replay script. Only metrics and
changed-record comparisons are written, avoiding duplicate model responses with
misleading new inference metadata.

The historical `run_experiment.py score` command deliberately rejects the
changed runtime; use the original Git revision to reproduce that experiment,
or the replay command above to inspect this follow-up.

## Next step

Improve count-scope extraction and exact evidence preservation in a separately
versioned prompt experiment. The default prompt remains v1; no training or new
model inference was performed here. H016 and the previously inspected held-out
outputs now inform development, so these files are known regression data for
follow-up work. A new independent evaluation requires new frozen cases.
