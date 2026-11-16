-- One row per patient and Monday-based calendar week within registered follow-up.
-- Daily cumulative snapshots were reconciled before materialization, never summed
-- together here. NULL means no usable daily count; missing days are never zero.
SELECT d.patient_id, p.display_name, d.week_start,
       COUNT(*) AS followup_days,
       SUM(CASE WHEN d.report_count > 0 THEN 1 ELSE 0 END) AS reported_days,
       SUM(CASE WHEN d.count_status = 'usable' THEN 1 ELSE 0 END) AS count_covered_days,
       SUM(CASE WHEN d.count_status = 'review' THEN 1 ELSE 0 END) AS review_days,
       SUM(CASE WHEN d.count_status = 'missing' THEN 1 ELSE 0 END) AS missing_count_days,
       SUM(CASE WHEN d.count_status = 'usable' AND d.count_basis = 'day_to_date' THEN 1 ELSE 0 END) AS partial_count_days,
       SUM(CASE WHEN d.count_status = 'usable' AND d.count_basis = 'day_total' THEN 1 ELSE 0 END) AS completed_count_days,
       SUM(CASE WHEN d.count_status = 'usable' THEN d.vomiting_count END) AS reported_vomiting_count,
       ROUND(1.0 * SUM(CASE WHEN d.count_status = 'usable' THEN 1 ELSE 0 END) / COUNT(*), 4) AS count_coverage,
       CASE WHEN SUM(CASE WHEN d.count_status = 'usable' AND d.count_basis = 'day_total' THEN 1 ELSE 0 END) = COUNT(*)
            THEN 'complete_reported_days' ELSE 'partial_reporting' END AS interpretation
FROM daily_summary AS d
JOIN patients AS p ON p.patient_id = d.patient_id
WHERE d.run_id = :run_id
GROUP BY d.patient_id, p.display_name, d.week_start
ORDER BY d.patient_id, d.week_start;
