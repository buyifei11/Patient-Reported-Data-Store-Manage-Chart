# Independent synthetic validation set v3

This set contains 20 fictional English source reports (T001–T020), 20 unique fictional patients (TP001–TP020), and manually authored expected observations and targeted extraction checks. Medication Willowglass is a fictional label. All reports are independent submissions and have no replacement links.

## Authoring and independence

The author read only the extraction contract in `docs/design.md`, the executable schema in `src/schema.py`, and the fixture-validation API in `src/pipeline.py`. No extraction prompts, historical model outputs, development fixtures, earlier held-out fixtures, or starter raw/gold fixtures were read. The set was authored separately while the candidate prompt was being developed and was not disclosed to the prompt author before the candidate freeze.

Source narratives, reference values, scopes, dates, issues, and rationales were authored manually from the contract. Small serialization helpers only assembled explicit field values; they did not derive labels. **No extraction-model inference or normalization execution was used to generate the gold.** No network calls were made, no model outputs were inspected, and no normalizer output was used as a reference. This is AI-authored synthetic diagnostic material, not independently human-annotated clinical ground truth.

## Contract review

Every normalized observation specifies all contract fields. Evidence is a contiguous, exact source-text substring or an exact questionnaire field value. Calendar anchors in preceding sentences are included in the relevant contiguous evidence. Case and punctuation are retained. Unknown dates, counts, and score contexts stay unknown with the corresponding field issues; absence and hypothetical claims remain distinct.

Counts distinguish particular episodes, bounded intervals, current-day cumulative totals, and completed-day totals. A multi-day count remains a single undated window. Interval boundaries and cumulative snapshot cutoffs are not promoted to exact episode times. An earlier cumulative snapshot stays separate from a submission-time form, while compatible positive daily totals that disagree create a count-only conflict. A valid questionnaire rating may coexist with a rejected text-score diagnostic.

All submission timestamps have explicit UTC offsets and valid IANA timezones. The offsets correspond to the named zones on the submission date. Every questionnaire answer targets its patient-local submission date. Reference identifiers follow known date, known clock time, then symptom ordering where relevant; semantic correctness does not depend on these labels.

`cases.json` records the purpose and contract rationale of each case. The empty-symptom case deliberately has no observations or targeted extraction checks.

## Validation

Schema and provenance validation passed through `src.pipeline.validate_fixtures` under the project virtual environment: 20 reports, 22 observations, and 22 targeted extraction checks. The normalizer entry point was replaced by an assertion-raising guard during validation, and no extraction model was invoked. A separate timestamp-offset check identified Vancouver's November offset as UTC−07:00 under the installed IANA timezone data; T016 was corrected before independent review without changing its local date or labels. Validation checks structural consistency and source linkage, not independent semantic accuracy. The source and gold will be frozen before evaluation, and no later reference change may be justified solely by a model prediction.

## Author response to independent pre-inference review

The independent reviewer identified that T011's 09:00 cumulative cutoff is not an episode occurrence time. The earlier snapshot now has null normalized `event_time` and null targeted candidate `clock_time`; its exact cutoff wording remains in `time_text`. Its distinct current-endpoint daily claim retains the contract-required count conflict against the questionnaire, without adjustment for any normalizer limitation.

Before any inference, T002, T003, T005, and T019 were rewritten with different sentence structures and narrative contexts in response to the independent reviewer's cross-split similarity check. Their intended semantic phenomena and values were retained, with exact evidence and time expressions updated to match. The T019 fictional label is now Medication Willowglass. The author did not inspect any prior fixture, prompt, or model output during this revision.

Post-revision validation again passed: 20 reports, 22 observations, and 22 extraction checks, with normalization guarded off and all submission offsets matching their patient zones.

## Independent pre-inference signoff

The reviewer inspected all 20 sources, all 22 expected observations and targeted checks, and all 50 prior source narratives. This inspection occurred after candidate prompt v3 was locked at SHA256 `6c0af35b5a22c10aeb020010830b7145b5dfd0063e058b81e52f805a2f4c096d`. The prompt was not changed in response to these cases. No v3 experiment model outputs existed during this review, and normalization output was not used to author or approve labels.

The reviewer requested the T011 cutoff-time correction and the four narrative revisions documented above, then rechecked their exact source spans and intended scopes. Interval endpoints in T001 and T008 and the cumulative cutoff in T011 correctly remain null episode times. T011's current daily count must conflict with its questionnaire even if the bounded normalizer does not recognize the new start-to-current wording; that potential shared implementation limitation is deliberately not hidden by changing the expected answer. T020 correctly retains the rejected text-scale issue while accepting the independent eligible questionnaire severity. No further semantic label correction was identified before inference.

The revised narratives are distinct from the prior scenarios; shared contract phenomena and ordinary symptom vocabulary remain unavoidable in this small diagnostic set. Exact report IDs, patient IDs, and source text have no cross-split overlap. Independent schema/provenance validation passed for all 20 reports, 22 observations, and 22 checks with both normalizer entry points guarded against invocation. This signoff establishes a reviewed, frozen synthetic reference set, not clinical validity or statistical independence from the shared contract.

Before freezing, the case inventory was standardized to the existing array format (`report_id`, `scenario_group`, `focus`, `reason`). Only inventory presentation changed; source text and reference labels were unaffected.
