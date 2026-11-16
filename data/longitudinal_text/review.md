# Source and reference review

This is the preparation record for the 71-report all-text longitudinal dataset.
Sources and references were frozen at **2026-11-16 20:42:26 UTC**, before the
first extraction request. The immutable [manifest](manifest.json) records that
snapshot and its file hashes. Later extraction outputs are stored separately in
[results/longitudinal-text-extraction](../../results/longitudinal-text-extraction/).

## Authorship and source checks

The source conversion used three real generation API requests to
`gpt-5.4-mini-2026-03-17`, with reasoning effort `none`. Each request generated
21 supplements, for 63 in total. Exact requests, responses, usage, and raw texts
remain in [the generation archive](../../results/longitudinal-text-generation/README.md).
No text was discarded or regenerated after examining extraction performance.

A reference-author agent inspected the final texts against the written data
contract, and a separate reviewer checked all 71 source/reference pairings.
Neither the extractor nor the normalizer was invoked to manufacture reference
answers. This is AI-assisted authoring and separate agent review, not independent
human annotation or clinical expert validation.

The review checked that:

- All 71 final sources have text and zero questionnaire entries. All ten original
  text prefixes, original patient IDs, submission times, timezones, and follow-up
  bounds are preserved; report IDs and correction links are explicitly mapped.
- All 63 supplements preserve their seeded symptom values, absence, uncertainty,
  and daily scope after the single disclosed edit below.
- Every generated severity identifies its own symptom, worst-so-far-today
  context, and out-of-five scale. A count does not determine a severity.
- Submission clocks do not become symptom occurrence clocks. Nausea has no
  episode count; its null count does not create a `count_unknown` issue.
- All 279 retained reference evidence entries are literal source substrings
  with `path: "text"`. Each normalized time phrase is supported by retained
  evidence. No questionnaire path appears in the references.

## The sole pre-inference edit

Report: **TXT-L-P003-14**. The raw generated output was:

> My nausea is worst at 3/5 today so far. I've had vomiting today so far, and my vomiting is worst at 2/5 today so far.

The reviewed source is:

> My nausea is worst at 3/5 today so far. I've had vomiting today so far, but I don't know how many times. My vomiting is worst at 2/5 today so far.

The original seed explicitly represented an unknown vomiting count. Generation
omitted that statement, so the final source restores it. Occurrence, daily scope,
and numeric ratings are unchanged. The edit preceded both reference authoring
and extraction. It was a source-fidelity correction, not a response to an
extractor error. The raw API output is unchanged, and the other 62 generated
supplements remain verbatim. See [editorial_review.json](editorial_review.json)
for the machine-readable record.

## Reference decisions that affect interpretation

| Case | Preserved meaning and expected handling |
|---|---|
| TXT-R001 | Yesterday's two vomits are a completed-day total; today's morning nausea is a separate observation. |
| TXT-R002 | The original nausea rating 2/5 conflicts with the form-derived 3/5 for the same interval. Keep both raw claims; normalized severity is null with `conflicting_sources`. The two agreeing zero-vomiting statements support one distinct claim. |
| TXT-R003 | The explicitly stated 14:20 vomiting event remains an event count with a clock, not a daily total. |
| TXT-R004, TXT-R005, TXT-R006 | Preserve each reported cumulative count. The explicit TXT-R006 replacement of TXT-R005 is applied downstream; the report references do not sum updates or delete the replaced source. |
| TXT-R007 | “After dinner” defines a window but no resolvable date. Count remains one; date stays null with `date_unknown`. |
| TXT-R008 | A vague positive vomiting count stays unknown, with `count_unknown`; it is not zero. |
| TXT-R009 | The original count one and appended denial are conflicting same-interval claims. Keep both raw claims; normalized assertion is uncertain and count null, with assertion/count conflict issues. The append is not a correction. |
| TXT-R010 | Morning nausea has an explicit relation to taking Medication A. Concern about vomiting tonight is hypothetical. Neither establishes a treatment effect or an observed vomiting count. |
| TXT-L-P003-14 | Vomiting occurred with an explicitly unknown count; its 2/5 worst-daily rating and nausea's 3/5 rating remain known. |
| TXT-L-P001-10-AM and TXT-L-P001-10 | Morning count four and evening count one remain separate per-report claims. The unexplained decrease is a daily aggregation issue; it is not inserted as a per-report extraction conflict. |

Raw claims and normalized observations are different evaluation layers. R002
and R009 each have two conflicting claims that become one uncertain normalized
observation. Consequently, the original ten reports contribute **17 candidate
checks and 15 normalized observations**; the 61 follow-ups contribute **122 of
each**. Totals are **139 checks and 137 observations**.

Each candidate check covers 11 semantic fields: symptom, assertion, count,
count scope, severity value, severity scale, severity context, day reference,
explicit date, clock, and medication relation. The 137 observations have 1,233
core-field expectations: **803 known and 430 null**. Reference issues comprise
one severity conflict, one unknown date, two unknown counts, one assertion
conflict, and one count conflict. These are reference contents, not extraction
accuracy scores.

## Evaluation boundary and limitations

The frozen extraction protocol keeps all reports and failures, uses one attempt
per report, and does not retune the prompt or repair labels based on predictions.
Reference answers are available to the evaluator only; model inputs and dashboard
construction do not consume them. Any permitted source-verified quotation review
must remain a separate recorded replay with original outputs and strict scores
preserved. It cannot waive wrong values, negation, timing, or attribution.

These sources are known synthetic integration material, not fresh held-out
examples. Among 63 raw supplements there are 37 unique strings and 26 repeated
occurrences beyond the first copies. Repeated patterns, reused facts, artificial
longitudinal trajectories, and the shared model family limit what any score on
this dataset can establish. The original ten and converted 61 should be reported
separately when discussing results.
