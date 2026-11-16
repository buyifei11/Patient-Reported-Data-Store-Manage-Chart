PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    patient_timezone TEXT NOT NULL,
    followup_start TEXT NOT NULL,
    followup_end TEXT NOT NULL,
    source_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    reported_at TEXT NOT NULL,
    patient_timezone TEXT NOT NULL,
    source_text TEXT NOT NULL,
    questionnaire_json TEXT NOT NULL,
    supersedes_report_id TEXT REFERENCES reports(report_id) DEFERRABLE INITIALLY DEFERRED,
    source_sha256 TEXT NOT NULL,
    source_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS medication_changes (
    change_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    medication TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    changed_utc TEXT NOT NULL,
    change_type TEXT NOT NULL CHECK(change_type IN ('start','stop','dose_change')),
    source_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    imported_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_patients (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    ordinal INTEGER NOT NULL,
    PRIMARY KEY(run_id, patient_id)
);
CREATE TABLE IF NOT EXISTS run_medication_changes (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    change_id TEXT NOT NULL REFERENCES medication_changes(change_id),
    ordinal INTEGER NOT NULL,
    PRIMARY KEY(run_id, change_id)
);
CREATE TABLE IF NOT EXISTS report_results (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    report_id TEXT NOT NULL REFERENCES reports(report_id),
    ordinal INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ok','error')),
    error_code TEXT,
    error_message TEXT,
    candidates_json TEXT NOT NULL,
    raw_response TEXT,
    metadata_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    PRIMARY KEY(run_id, report_id)
);
CREATE TABLE IF NOT EXISTS observations (
    run_id TEXT NOT NULL,
    report_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    symptom TEXT NOT NULL CHECK(symptom IN ('nausea','vomiting')),
    assertion TEXT NOT NULL,
    count INTEGER,
    count_scope TEXT,
    severity INTEGER,
    event_date TEXT,
    event_time TEXT,
    earliest_utc TEXT,
    latest_utc TEXT,
    time_precision TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    issues_json TEXT NOT NULL,
    observation_json TEXT NOT NULL,
    PRIMARY KEY(run_id, report_id, observation_id),
    FOREIGN KEY(run_id, report_id) REFERENCES report_results(run_id, report_id)
);
CREATE INDEX IF NOT EXISTS observation_time ON observations(run_id, event_date, symptom);
CREATE TABLE IF NOT EXISTS analyses (
    run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
    computed_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    analysis_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS effective_reports (
    run_id TEXT NOT NULL,
    report_id TEXT NOT NULL,
    PRIMARY KEY(run_id, report_id),
    FOREIGN KEY(run_id, report_id) REFERENCES report_results(run_id, report_id)
);
CREATE TABLE IF NOT EXISTS daily_summary (
    run_id TEXT NOT NULL REFERENCES analyses(run_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    event_date TEXT NOT NULL,
    week_start TEXT NOT NULL,
    vomiting_count INTEGER,
    count_basis TEXT CHECK(count_basis IN ('day_to_date','day_total')),
    count_status TEXT NOT NULL CHECK(count_status IN ('usable','review','missing')),
    nausea_severity INTEGER,
    nausea_status TEXT NOT NULL CHECK(nausea_status IN ('usable','review','missing')),
    vomiting_severity INTEGER,
    vomiting_severity_status TEXT NOT NULL CHECK(vomiting_severity_status IN ('usable','review','missing')),
    report_count INTEGER NOT NULL,
    source_report_ids_json TEXT NOT NULL,
    review_reasons_json TEXT NOT NULL,
    row_json TEXT NOT NULL,
    PRIMARY KEY(run_id, patient_id, event_date),
    CHECK((count_status = 'usable' AND vomiting_count IS NOT NULL AND count_basis IS NOT NULL)
          OR (count_status != 'usable' AND vomiting_count IS NULL)),
    CHECK(vomiting_count IS NULL OR vomiting_count >= 0)
);
CREATE TABLE IF NOT EXISTS review_items (
    run_id TEXT NOT NULL REFERENCES analyses(run_id),
    ordinal INTEGER NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    report_id TEXT NOT NULL REFERENCES reports(report_id),
    observation_id TEXT,
    event_date TEXT,
    field TEXT NOT NULL,
    reason TEXT NOT NULL,
    row_json TEXT NOT NULL,
    PRIMARY KEY(run_id, ordinal)
);
CREATE TABLE IF NOT EXISTS correction_decisions (
    run_id TEXT NOT NULL REFERENCES analyses(run_id),
    report_id TEXT NOT NULL REFERENCES reports(report_id),
    target_report_id TEXT NOT NULL REFERENCES reports(report_id),
    status TEXT NOT NULL CHECK(status IN ('applied','rejected')),
    reason TEXT,
    row_json TEXT NOT NULL,
    PRIMARY KEY(run_id, report_id)
);
