-- Highest usable daily-worst nausea rating within one patient's stored follow-up.
-- Keep all tied dates. Unknown/review ratings are excluded, never replaced by 0.
-- Vomiting eligibility is independent of nausea eligibility.
WITH eligible AS (
    SELECT patient_id, event_date, nausea_severity, vomiting_count, count_status,
           source_report_ids_json
    FROM daily_summary
    WHERE run_id = :run_id AND patient_id = :patient_id
      AND nausea_status = 'usable' AND nausea_severity IS NOT NULL
)
SELECT * FROM eligible
WHERE nausea_severity = (SELECT MAX(nausea_severity) FROM eligible)
ORDER BY event_date;
