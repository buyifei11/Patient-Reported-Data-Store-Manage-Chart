# Reference-based evaluation

`src/evaluation.py` compares a pipeline run with the authored reference records.
It is independent of the model client and uses only the Python standard library.
The original 10 reports, 15 observations, and three extraction checks are small
development fixtures. They were used to design the pipeline and are not an
independently annotated, held-out dataset. Results measure agreement with these
references; they do not establish clinical accuracy or generalization.

The prompt experiment adds 20 development reports and 20 separately authored
held-out reports, totaling 50 reports, 61 reference observations, and 41 targeted
checks across all sets. The scorer is unchanged across both prompt versions;
the experiment runner labels the output `reference_role` by split and validates
frozen run metadata. These are small AI-assisted synthetic datasets, not clinical
validation. See [dataset roles](../data/README.md) and [actual comparison](prompt_comparison.md).

## Two separate comparisons

1. **Text extraction:** compare selected source-specific candidate fields against
   `extraction_checks`, before questionnaire reconciliation.
2. **Normalized output:** compare the final observations against `observations`,
   after date resolution, score validation, and source reconciliation.

For R009, the text candidate must retain count **1**. The normalized count is
**null** because the same-day questionnaire reports **0**. These are two correct
results at different stages. Comparing only final output would fail to reveal a
parser that discarded the original text count. R002 similarly checks text
severity **2/5** before the questionnaire conflict makes final severity null.

Gold is read by the evaluator only. It must never enter model prompts or become
the source of pipeline predictions. The controlled reference copies in unit
tests test scoring behavior; their perfect scores are not LLM results.

## Interface and input checks

```python
from src.evaluation import evaluate_predictions

metrics = evaluate_predictions(sources, gold, predictions)
```

All three arguments are lists of dictionaries. Every prediction has this envelope:

```json
{
  "report_id": "R009",
  "status": "ok",
  "candidates": [],
  "observations": [],
  "error": null
}
```

An `ok` envelope means the pipeline completed, including a valid extraction with
no relevant symptoms. An `error` envelope records a failed run; it does not mean
the patient reported no symptoms. Partial normalized observations inside an error
envelope receive no scoring credit. If extraction succeeded but normalization
failed, the pipeline retains schema-validated candidates and sets
`error_code=normalization_error`. Those candidates remain eligible for the
pre-reconciliation extraction checks. Report completion and normalized-output
metrics still record the failure. Candidates in all other error envelopes,
including `invalid_schema`, receive no scoring credit. Missing prediction
envelopes are also failures, with a separate `missing` count.

Source and gold report-ID sets must match exactly. Duplicate source, gold, or
prediction report IDs, unknown prediction report IDs, malformed collection
envelopes, invalid statuses, and stale gold evidence raise `ValueError`. Pipeline
schema validation remains a separate step. The evaluator checks linkage and
metrics rather than replacing the executable schema validator.

## How observations are matched

Matching occurs within a report and symptom. Generated observation IDs and array
order are not accuracy targets. If each side has one observation for a symptom,
they are paired; any incorrect date, count, assertion, or other field then fails
that field's comparison.

For repeated symptoms, matching uses source evidence. Text excerpts must be exact
substrings of the original report; overlap is scored using their character spans
in that report. Compatible questionnaire evidence uses an identical source path
and value. Different overlapping excerpts can therefore support the same match.
The algorithm repeatedly accepts mutually unique best evidence matches. It never
uses count, severity, assertion, normalized date, or reference agreement to select
the highest-scoring answer.

Identical duplicate predictions can supply one match; remaining copies are false
positives. Disagreeing predictions with equally strong evidence are ambiguous.
If provenance does not identify a unique pairing, the unresolved observations
remain unmatched and appear under `matching.ambiguous_groups`. This conservative
policy can lower recall when two legitimate excerpts do not overlap, or when
repeated claims share broad quotes. Inspect those cases manually and improve the
annotation/matching contract before treating the score as reliable. The matcher
does not infer clinical equivalence between differently worded claims.

## Metrics and denominators

There is deliberately no single pooled accuracy percentage: many fields are
usually null, so a model that outputs null everywhere can look deceptively good.

| Output | Meaning and denominator |
| --- | --- |
| `report_completion` | Completed reports / all source reports, with separate error and missing counts. |
| `observation_detection` | A matched observation is a true positive; unmatched prediction is a false positive; unmatched reference is a false negative. Includes present, absent, uncertain, and hypothetical claims. This measures claim detection, not confirmed symptom episodes. |
| `fields.<field>.reference_known` | Exact matches / all non-null reference values for that field, including values in missing or failed reports. |
| `fields.<field>.reference_null` | Explicit nulls on matched predictions / all null reference values. A missing observation or missing key is incorrect, not a successfully preserved null. |
| `fields.<field>.reference_null.overfilled` | Number of matched predictions that supply a non-null value where the reference is null. |
| `unknown_overfill` | Sum of those overfills across fields, with all reference-null fields as denominator. Null includes unknown, unmentioned, and inapplicable values; inspect per-field results and completion alongside this rate. |
| `assertion_accuracy` | Correct assertion / all reference observations. A missing observation is incorrect. |
| `issue_detection` | Precision, recall, and F1 for exact `(field, code)` pairs on matched observations. Missing observations miss their required issues; issues on extra observations are false positives. Duplicate issue entries are treated as one pair. |
| `extraction_checks` | A check passes only when a uniquely supported candidate matches every listed expected field. Denominator is every authored check, including those in failed or missing reports. A normalization failure may still pass this earlier-stage check using its validated candidates. Also reports per-field agreement over checks that actually specify that field. |

Precision is `TP / (TP + FP)`, recall is `TP / (TP + FN)`, and F1 is
`2*TP / (2*TP + FP + FN)`. A zero denominator produces JSON `null`, not an invented
perfect score. An entirely missed nonempty reference set has recall and F1 zero;
precision is undefined if there were no predictions.

Per-field comparisons cover `symptom`, `assertion`, `count`, `count_scope`,
`severity`, `event_date`, `event_time`, `time_text`, `date_basis`, and
`medication_relation`. Missing fields fail even if the reference is null. Booleans
do not equal numeric zero or one. Extra observations lower detection precision;
they do not expand the reference-based field denominator. Read field accuracy
together with detection precision and recall.

`time_text` is a literal diagnostic: two valid excerpts can differ and lower this
field's exact-match score despite an equivalent normalized date. `date_basis`
also measures agreement with the chosen provenance convention. Neither is pooled
into an overall semantic accuracy score. Evidence text itself is used for
alignment and validation rather than exact-string accuracy. Medication objects
are compared as complete objects, so their labels and relationship must agree.

Extraction checks choose a candidate by symptom, when specified, and source-quote
overlap, never by its expected count or severity. Equally supported disagreeing
candidates fail as ambiguous. Each check is independent: multiple checks may
inspect different fields of the same candidate. Untargeted candidate fields are
not scored by the selected checks; three checks belong to the original fixtures,
21 to the additional development set, and 17 to the held-out set.

## Inspecting mistakes and running tests

`mismatches` identifies the report, reference label/index, prediction index, field,
expected value, and actual value where applicable. It also lists missing/extra
observations, missing/extra issues, report failures, and failed extraction checks.
`prediction_missing` distinguishes an absent value from an explicit null.
IDs and indexes in these diagnostics are navigation aids, not match criteria.

Run the offline scorer tests from the repository root:

```sh
python -m unittest discover -s tests -p 'test_evaluation.py' -v
```

Tests deliberately inject wrong counts, all-null numeric outputs, failed and
missing reports, duplicates and extra claims, reordered arrays and changed IDs,
wrong issue fields, overfilled unknowns, and R009 candidate/reconciliation errors.
Repeated-symptom examples ensure evidence drives alignment rather than matching
the answer that produces the best grade. These tests require no model or API key.

The temporal experiment followed that pre-inference freeze/review process for
its held-out cases. Once their outputs guide further changes, those cases become
known regression data; a new independent claim needs new cases. Targeted checks
are not complete coverage of all candidate fields or language patterns.

## Observed alignment limitation

H016 in the temporal experiment contains a daily text/form conflict that the
normalizer incorrectly leaves as two observations. Full text and form evidence
tie against the merged reference in three runs, leaving it unmatched. A shorter
text excerpt in v2 round 1 makes the form observation the unique match, producing
both an additional correct-date score and a count overfill. The number comes
from the form; the metric alone does not mean it was fabricated. Inspect this
case with the missing/extra observations and conflict flags. The frozen scores
were not changed after this limitation was discovered.

A subsequent [normalization fix and offline replay](normalization_fix.md) resolve
the three saved H016 candidates with `day_to_date` scope into one conflict-marked
observation. The fourth candidate has `window` scope and remains separate; its
alignment limitation still applies. The evaluator and historical scores are
unchanged. Follow-up replay scores measure a code change on known cases, not new
model inference or independent generalization.

## Follow-up scope and evidence experiment

For the later ten-report nausea experiment, one verified harmless skipped-sentence
quote is accepted through an explicit [source-reviewed evidence exception](../results/text-validation-nausea/reviewed-evidence/README.md).
The original strict score remains 9/10; the separately labeled reviewed output
accepts 10/10 reports. Its original candidates remain unchanged and the restored
continuous source span is used only for normalization. This does not change the
automatic evaluator or waive unreviewed evidence failures.

The [v3 comparison](prompt_v3_comparison.md) uses the same evaluator and corrected
normalizer for both prompts: 50 known regression reports and 20 newly authored
validation reports, two rounds per arm. `scripts/run_prompt_v3.py` preserves full
metrics and adds paired report diagnostics. It excludes `time_text` and
`date_basis` from automated material-mismatch summaries, not from the full scores.
Manual review must still distinguish a valid alternative excerpt from a wrong
semantic phrase; H010's location-valued `time_text` is a genuine remaining error.

V3 demonstrates why candidate checks, completion, and normalized-field accuracy
must be read together. Fresh round 2 completes 20/20 reports but has only 11/16
correct known normalized scopes and 12/16 targeted candidate scope checks. D012
passes the fields selected in its targeted check while failing an uncovered
cross-field date rule. Literal evidence checks also do not prove that every
numeric claim is supported or that an interval endpoint is an episode time.
