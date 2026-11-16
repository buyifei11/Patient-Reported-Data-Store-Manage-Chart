# Time boundaries and conservative downstream handling

This change fixes deterministic time interpretation and counting boundaries.
It does not modify the default v1 prompt, train a model, or rewrite historical
model outputs or reference labels.

## Current-day ranges

`from midnight today through this submission` and explicit equivalents such as
`Since midnight today up to the time of this report` can identify the same daily
range as a submission-time questionnaire. The normalizer now recognizes bounded
`from`/`since` start-of-day ranges with explicit current endpoints. It masks only
that phrase while checking compatibility; the original quote and time text stay
unchanged. Other earlier-time qualifiers still prevent an unsafe merge.

The source must still have compatible symptom, date, actual assertion, scope,
and context. A model's incorrect `window` scope is not silently promoted to
`day_to_date`. Earlier snapshots such as `by noon` remain separate. The supported
wording is finite; unknown phrasing is not a general natural-language guarantee.

## Episode clocks versus boundaries

A stated clock can be an interval endpoint or a cumulative cutoff. It is not
necessarily the time of an episode. The grounder now rejects clock candidates
supported only by `between`, `from ... to`, `by`, `as of`, `until`, and related
boundary contexts. Both numeric endpoints are checked. An independently stated
actual occurrence at the same numeric time remains usable, even if that time
also appears as a boundary elsewhere in the quote.

The candidate, original text, and raw model response are retained. Invalid
clock interpretation fails normalization visibly; the code does not invent a
replacement clock or silently alter a model candidate to match gold. Exact
episode times, approximate times, timezone resolution, and future-time checks
remain distinct.

## Offline replay evidence

`scripts/replay_time_boundaries.py` replays all **280 saved outputs** from the v3
prompt experiment against the current normalizer without a model call. It
verifies the original manifest, source/reference/prompt/evaluator hashes, saved
prediction/metric hashes, and metadata. Only the old normalization file is
allowed to differ among the frozen runtime files. New downstream modules do not
change the historical model payloads.

Exactly six previously accepted outputs now fail: all four T011 outputs used
the 09:00 cumulative cutoff as an episode time, and both v3 T008 outputs used a
window's 10:00 start as an episode time. The total changes from 255 completed /
25 failed to **249 completed / 31 failed**. These new failures remove unsupported
precision; they are not a claim that model extraction improved. Every candidate
and raw response stays unchanged. Current-range reconciliation is separately
tested with correctly null clock candidates, since the saved T011 candidates
must first be rejected for their clock errors.

The separate [replay summary](../results/time-boundary-v1/summary.json) and
[changed outputs](../results/time-boundary-v1/changes.json) retain the before/after
status, observations, and first rejection reason. Historical scores remain
unchanged. The original v3 runtime is Git revision `66a5560`; frozen experiment
scoring deliberately rejects changed runtime files.

```bash
python scripts/replay_time_boundaries.py --output artifacts/time-boundary-review
```

Choose a new output directory. This command reads no credentials and makes no
network requests. The earlier temporal comparison and midnight replay also
remain available as historical experiments at their documented revisions.

## Aggregation safeguards

The downstream daily aggregator orders supported cumulative cutoffs without
writing them into episode-time fields. Unparsed or future cutoff expressions
remain in review rather than falling back to submission time. Likewise, known
same-day occurrence contradicts a later daily zero even when the earlier exact
quantity is unknown. The daily result is unresolved, not an inferred count of
one and not a fabricated zero. Explicit replacements are resolved first, so a
valid correction can supersede an earlier claim.

Tests cover current-range variants, earlier boundaries, both range endpoints,
independent actual clocks, unsupported/future snapshot cutoffs, actual occurrence
versus zero, unknown latest values, and correction behavior. The integrated demo
keeps unresolved days out of daily totals and retains their source evidence.
