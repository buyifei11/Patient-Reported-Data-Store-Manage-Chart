# Pre-inference held-out reference review

The separate review agent reviewed all 20 held-out sources and their manually authored reference answers against `docs/design.md` and `src/schema.py` before inference. The reviewer did not read `prompts/extraction_v2.txt` or any new inference output and did not use the normalizer to generate expected labels. The reviewer also compared held-out source stories against the 10 original development sources and the 20 additional development sources. This is an independent agent review of synthetic fixtures, not human annotation or clinical validation.

The final review accepts all 20 cases, totaling 25 observations and 17 extraction checks. Schema, report linkage, scenario-group uniqueness, exact source evidence, time-expression substrings, and completed-day ordering were checked separately without calling normalization. All 51 observation-evidence and extraction-check references match their source values. No semantic label correction was needed in the initial version; two source stories were revised to reduce cross-split template similarity, with corresponding manual reference updates described below.

## Individual semantic review

| Report | Reviewed reasoning and result |
| --- | --- |
| H001 | Actual nausea tonight is present. The submission is November 14 at 19:25 in Los Angeles, despite November 15 UTC; the event date is November 14. No exact clock time or severity is claimed. |
| H002 | Two confirmed vomiting bouts during a card game form a limited window on November 14. Evening does not imply a completed-day or cumulative total. |
| H003 | Both symptoms are explicitly absent on the local evening of November 13, because the New York submission is 21:15 on that date. Vomiting zero covers the rehearsal window only; nausea has no episode count. |
| H004 | The concert contingency is hypothetical vomiting tonight, November 13. It supplies no observed count, severity, or clock time. |
| H005 | Tokyo local submission is November 12 at 23:40. Nausea is present tonight with the explicit `after_taking` relation to Tablet Cedar. A separate vomiting event occurred at 21:10 tonight. The medication relation is not transferred to vomiting or treated as causation. |
| H006 | Morning nausea and one vomiting occurrence during the gardening break are separate symptom claims on November 10. The described break makes vomiting a window count, including when that count is one. Neither activity supplies a clock time. |
| H007 | Repeated vomiting yesterday morning resolves to November 10. The repair-shop interval is a window; the exact count is unknown, while occurrence remains present. Only count receives `count_unknown`. |
| H008 | Three vomiting occurrences during a reception meal are a window count. The journal explicitly lacks a recoverable date, so date remains unknown with `date_unknown`; submission context cannot supply a date. |
| H009 | The damaged tally leaves the exact daily count unknown between two possible values. Occurrence and the current-day cumulative scope remain known, so assertion is present and only count receives `count_unknown`. |
| H010 | The revised schedule combines seven vomiting episodes over four listed dates. This is one multiday window with no single event date, no clock time, and `unsupported_time_range`. The count is neither split across dates nor assigned to the submission date. |
| H011 | The log identifies one historical vomiting episode explicitly dated November 9 at 06:45. Both the date and exact clock time come from source text, independently of the November 11 submission. |
| H012 | The finished log explicitly covers all of November 8 and records no vomiting. This is an absent, zero `day_total` for a completed day. Midnight boundaries describe coverage, not an event at midnight. |
| H013 | Nausea is present today, with an explicit daily peak of 8 on a zero-to-ten scale. The extraction check preserves 8, 10, and the daily-maximum context; normalized severity stays null with `unsupported_scale`. |
| H014 | The revised video-call question explicitly asks for a momentary rating rather than the day's worst point. The candidate retains 2/5 with current context. Nausea is present on November 12; normalized severity is null with `unsupported_severity_context`, and no clock time is invented. |
| H015 | The kitchen-pad note establishes today's nausea and a 4/5 rating but explicitly leaves the rating's summary context unclear. Severity remains null with `severity_context_unknown`; the date is November 14. |
| H016 | Tokyo local submission is November 13 at 08:20. Text count five through submission and form count three are compatible current-day cumulative claims. Both confirm presence, so only count becomes null with `conflicting_sources`. Evidence preserves both sources, and the extraction check retains the text value five. |
| H017 | The text provides a worst-so-far-today score of nine on a ten-point scale, which is ineligible for the fixed five-point trend. The form independently provides eligible severity 2. The final severity remains 2 with the rejected text scale retained as an `unsupported_scale` diagnostic, not a severity conflict. |
| H018 | The one vomiting event at 11:32 and the form's submission-time daily count four with severity three have different scopes. They remain separate observations; neither count nor severity is made conflicting merely because the symptom and date match. |
| H019 | Historical nausea on November 13, explicit absence of nausea today on November 14, and today's cumulative vomiting zero are three distinct claims. The previous day's presence is not merged with today's absence. |
| H020 | The administrative message mentions neither target symptom. An empty observation list is correct and does not assert symptom absence. |

## Cross-split similarity review and pre-inference changes

The initial H010 resembled D012's template: a sentence beginning with a date range, six vomiting occurrences, and a three-day span. The held-out author independently replaced it with a recovered community-center schedule combining a tally of seven across four separately listed dates. The source story, numeric count, dates, evidence, time expression, extraction check, and scenario metadata were updated before inference. The single-date representation remains unsupported for the same design reason.

The initial H014 closely resembled D014's short clause combining current nausea, an X-out-of-five rating, an exact clock time, and today. The held-out author replaced it with a video-call question whose explicitly momentary wording determines score eligibility. The revised case has no clock time. Evidence, time expression, extraction check, and scenario metadata were updated manually before inference; the normalized severity remains unsupported because its context is momentary.

The reviewer accepted both revisions and rechecked the changed reference answers. Remaining shared concepts are intended coverage rather than near-identical stories. For example, H018's brief clock-timed episode uses ordinary event language also seen in development, but its structured daily answer tests separation of incompatible scopes. H003 and D004 both mention choir activity, but one concerns two explicitly absent symptoms and a bounded vomiting-zero interval, while the other concerns an actual nausea occurrence. No additional source-story or template near-clone was found in the final comparison. This qualitative review does not establish statistical independence or broader generalization.

## Reviewed file fingerprints

These SHA-256 values identify the files accepted before inference:

| File | SHA-256 |
| --- | --- |
| `data/heldout/reports.jsonl` | `3738b0a8de01bc58bceb069092374782da9d7487246f913f3e311c2025d216c8` |
| `data/heldout/expected.jsonl` | `e4cb15dc5468c5ea8f45611307d1f62ec9394f58d46e13eb83e4c8f013fa6720` |
| `data/heldout/cases.json` | `6cb403bd157af6bdaf4d88c10ea33911c9c867d297e034a0123c5e5116f70d9e` |
| `data/raw/reports.jsonl` | `81e45856bca4ccafec40f7474c3510e230fc03975448eceb221dad297b5710da` |
| `data/dev/reports.jsonl` | `79f74d7c3e38f3c7842634d8d2f258da6e26104db03d00b30de797a9a5269a2b` |
