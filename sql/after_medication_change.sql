-- Temporal context, not causation. All effective present observations are compared
-- with each registered change for that patient. Exact instants and possible local
-- day/DST bounds have already been converted to UTC by the store's adapter.
WITH comparisons AS (
    SELECT m.change_id, m.patient_id, p.display_name, m.medication, m.change_type,
           m.changed_at, m.changed_utc, r.report_id, o.observation_id,
           o.symptom, o.count, o.count_scope, o.severity,
           o.event_date, o.event_time, o.time_precision,
           o.evidence_json, o.issues_json,
           CASE WHEN o.earliest_utc IS NULL THEN 'unknown_date'
                WHEN o.earliest_utc > m.changed_utc THEN 'after'
                WHEN o.latest_utc < m.changed_utc THEN 'before'
                WHEN o.earliest_utc = o.latest_utc AND o.earliest_utc = m.changed_utc THEN 'at_change_time'
                ELSE 'indeterminate' END AS timing_status,
           EXISTS(SELECT 1 FROM review_items q
                  WHERE q.run_id = o.run_id AND q.report_id = o.report_id
                    AND (q.observation_id IS NULL OR q.observation_id = o.observation_id)) AS has_review_items
    FROM observations AS o
    JOIN effective_reports AS e ON e.run_id = o.run_id AND e.report_id = o.report_id
    JOIN reports AS r ON r.report_id = o.report_id
    JOIN run_medication_changes AS rm ON rm.run_id = o.run_id
    JOIN medication_changes AS m ON m.change_id = rm.change_id AND m.patient_id = r.patient_id
    JOIN patients AS p ON p.patient_id = r.patient_id
    WHERE o.run_id = :run_id AND o.assertion = 'present'
)
SELECT * FROM comparisons
WHERE timing_status != 'before'
ORDER BY patient_id, changed_utc, event_date IS NULL, event_date, event_time, report_id, observation_id;
