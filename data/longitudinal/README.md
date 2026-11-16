# Four-week demonstration sources

This dataset contains **71 fictional reports for three patients**, covering
November 1-28, 2026. It includes the original ten free-text reports unchanged and
61 additional questionnaire-only submissions. `patients.json` defines 28
inclusive follow-up days per patient; `medication_changes.json` contains five
fictional start/dose-change records. These are source inputs, not model outputs
or reference answers.

The extra questionnaires have empty `text` and are normalized directly by code.
They do not require or demonstrate new LLM extraction. The offline demo reuses
the original ten actual model candidate batches from
`results/gpt54mini-dev-v1/predictions.jsonl`, checks each source hash, and runs the
current normalizer. It never copies gold observations into its output. The
historical R010 time interpretation remains visible rather than being repaired
from its reference answer.

`scripts/create_longitudinal_demo.py` documents the deterministic generation
recipe. Counts and ratings follow artificial patterns to exercise a chart, not
an empirical treatment response. Source files are checked in and the generator
refuses to overwrite them. No real patients, drugs, or treatment effects are
represented; medication names are placeholders.

The dataset deliberately includes missing dates, explicit zero counts, an
unknown count with a supplied severity, a text/form conflict, and a morning
count of four followed by an unexplained evening count of one on P001's
November 10. That decrease requires review. R006 remains the explicit complete
replacement of R005, preserving its nausea rating while correcting vomiting.

The four-week follow-up intersects five Monday-based calendar-week buckets.
The weekly query clips coverage denominators at the enrollment boundaries
rather than inventing observations outside follow-up. A day without a report is
not zero. Evening questionnaire totals remain partial `day_to_date` reports.

This is a longitudinal integration demo, not an additional independent model
evaluation set. Ten source IDs intentionally overlap the starter fixtures.
