# Prototype validation record

This milestone completes the local source-to-store-to-chart flow while keeping
the v1 extraction baseline fixed. All data are synthetic. No new model requests
were made during implementation, offline replay, or demo generation.

## Automated verification

The full offline suite passes **221 tests** with:

```bash
python -m unittest discover -s tests -q
```

Coverage includes strict schemas, mocked API failure paths, evidence/time rules,
metric denominators, frozen-experiment controls, cumulative counts, corrections,
independent severity eligibility, database transactions/idempotency, UTC
medication ordering, read-only queries, source-hash validation, HTML escaping,
CSV formula neutralization, and the complete offline build.

Specific behavioral assertions include:

- R005 stays stored with count 3, while the effective R006/R004 daily count is 2.
- P001's November 3 vomiting zero remains numeric zero; its conflicting nausea
  severity remains unknown.
- Missing P003 days remain null; P003's November 7 conflict is not counted.
- P001's November 10 decrease from morning 4 to evening 1 requires review.
- Unknown latest daily values do not fall back to earlier known counts.
- Known occurrence with unknown quantity conflicts with a later daily zero.
- Failed/incomplete/branching replacements do not deactivate a valid original.
- R003 at 14:20 is after its medication change at 13:00; same-day unknown-time
  R010 nausea is indeterminate. Superseded R005 is absent from effective queries.
- A stale or uncached text report stops the offline build; gold is never read.
- Reimporting exactly saved sources/results creates no duplicate; changed IDs
  fail atomically. Query commands do not create schema or modify the database.

All 70 diagnostic source/reference records and 71 longitudinal source records
pass structural/provenance validation. These sets overlap on ten starter reports;
they are not 141 independent model-validation cases.

## Generated demonstration

The final build contains 71 reports, 137 normalized observations, zero failed
reports, and 84 follow-up patient-days. There are 61 usable count days, five count
review days, and 18 missing-count days. Fourteen review items retain field-level
diagnostics. SQLite integrity and foreign-key checks pass.

The two SQL exports contain 15 patient/calendar-week rows and 164 medication
context rows. An observation may be related in time to multiple changes, so the
second count is not a symptom-episode total. Snapshot files are preserved in
[`results/longitudinal-demo/`](../results/longitudinal-demo/); local databases and
routine build artifacts remain ignored under `artifacts/`.

Browser checks used an isolated headless Chrome profile with external requests
blocked. All three patient selections were exercised; every displayed count and
nausea point matched the SQLite-derived daily rows. Source expansion retained
R005's original count, medication filtering worked, and desktop (1440 pixels)
and mobile (390 pixels) layouts had no page overflow or script errors. The page
made no remote requests. Desktop/mobile images were visually inspected. The
selected [browser record](../results/longitudinal-demo/browser-check.json) and
[preview](dashboard-preview.png) document the check.

## Extraction guardrail replay

All 280 frozen v3-experiment outputs were replayed without changing candidates
or reference labels. Six previously accepted unsupported clock interpretations
are now rejected. This is a validation improvement, not a higher LLM accuracy
claim. See [time_boundaries.md](time_boundaries.md) and its separate saved replay.

All 64 previously versioned source/reference/prompt/result files selected for
preservation were checked byte-for-byte against Git revision `66a5560`. Old
experiments are historical evidence and retain their original scores. Their
frozen-runtime scoring should be reproduced at the documented Git revision.

## Practical limit

These checks establish bounded software behavior on synthetic cases. They do not
prove general language understanding, clinical accuracy, or complete capture of
patient episodes. Conservative exclusions, missing coverage, and model semantic
errors remain visible; a clinician review/write-back workflow is future work.
