"""Immutable source/run storage and reproducible SQLite query materializations.

No model, reference answer, or credential is read here. The chosen run is always
explicit; importing a later extraction does not silently replace an earlier run.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.pipeline import _digest, validate_predictions
from src.schema import validate_sources


SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string.")
    return value


def _date(value: object) -> date:
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("Dates must use YYYY-MM-DD.")
    return date.fromisoformat(value)


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("A medication-change timestamp must contain an explicit UTC offset.")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("A medication-change timestamp must contain an explicit UTC offset.")
    return parsed


def connect(path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    """Open a local database; read-only query connections never initialize schema."""
    if read_only:
        if str(path) == ":memory:":
            raise ValueError("Read-only connections require an existing database file.")
        # as_uri escapes spaces and literal '?'/'#' characters in local paths;
        # mode=ro refuses missing databases and blocks writes at SQLite's layer.
        connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    else:
        connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if not read_only:
        connection.executescript((SQL_ROOT / "schema.sql").read_text())
    return connection


def _indexed(rows: list[dict], key: str) -> dict:
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{key} records must be a list of objects.")
    result = {}
    for row in rows:
        identifier = _text(row.get(key), key)
        if identifier in result:
            raise ValueError(f"Duplicate {key}: {identifier}")
        result[identifier] = row
    return result


def _validate_patients(patients: list[dict]) -> dict:
    indexed = _indexed(patients, "patient_id")
    fields = {"patient_id", "display_name", "patient_timezone", "followup_start", "followup_end"}
    for patient in patients:
        if set(patient) != fields:
            raise ValueError("Patient records require the documented follow-up fields only.")
        _text(patient["display_name"], "display_name")
        try:
            ZoneInfo(_text(patient["patient_timezone"], "patient_timezone"))
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Patient timezone must be an available IANA timezone.") from exc
        if _date(patient["followup_end"]) < _date(patient["followup_start"]):
            raise ValueError("Follow-up end cannot precede its start.")
    return indexed


def _evidence_matches(source: dict, evidence: dict) -> bool:
    actual = source
    try:
        for part in evidence["path"].split("."):
            actual = actual[int(part)] if isinstance(actual, list) else actual[part]
    except (KeyError, IndexError, ValueError, TypeError):
        return False
    value = evidence["value"]
    if evidence["path"] == "text":
        return isinstance(value, str) and bool(value) and value in actual
    return type(actual) is type(value) and actual == value


def _bounds(observation: dict, patient_timezone: str) -> tuple[str | None, str | None, str]:
    """Represent all possible instants without inventing a date-only event time."""
    if observation["event_date"] is None:
        return None, None, "unknown_date"
    day = _date(observation["event_date"])
    zone = ZoneInfo(patient_timezone)
    if observation["event_time"] is not None:
        naive = datetime.combine(day, time.fromisoformat(observation["event_time"]))
        # A repeated clock during fall-back has two possible instants. A skipped
        # spring-forward clock has none; neither may be silently treated as exact.
        instants = set()
        for fold in (0, 1):
            local = naive.replace(tzinfo=zone, fold=fold)
            if local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == naive:
                instants.add(local.astimezone(timezone.utc))
        if instants:
            return _utc(min(instants)), _utc(max(instants)), "exact" if len(instants) == 1 else "ambiguous_local_time"
    start = datetime.combine(day, time.min, zone)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(timezone.utc) - timedelta(microseconds=1)
    return _utc(start), _utc(end), "date_only" if observation["event_time"] is None else "invalid_local_time"


def _immutable(connection, table: str, key: str, identifier: str, value: dict, columns: dict) -> None:
    # Table/column identifiers are private constants, never caller-supplied SQL.
    existing = connection.execute(f"SELECT source_json FROM {table} WHERE {key} = ?", (identifier,)).fetchone()
    serialized = _json(value)
    if existing is not None:
        if existing["source_json"] != serialized:
            raise ValueError(f"Changed content under existing {key}: {identifier}. Use an explicit new version.")
        return
    values = {**columns, "source_json": serialized}
    connection.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))


def import_run(connection: sqlite3.Connection, *, run_id: str, patients: list[dict],
               reports: list[dict], predictions: list[dict], medication_changes: list[dict],
               metadata: dict | None = None) -> bool:
    """Atomically import an immutable run; return False for an identical reimport."""
    _text(run_id, "run_id")
    by_patient = _validate_patients(patients)
    reports = validate_sources(reports)
    by_report = _indexed(reports, "report_id")
    by_prediction = _indexed(predictions, "report_id")
    if set(by_report) != set(by_prediction):
        raise ValueError("Every imported report needs exactly one result, including failed results.")
    validate_predictions(reports, predictions)
    for report in reports:
        if report["patient_id"] not in by_patient:
            raise ValueError("Every report must belong to a registered run patient.")
        result = by_prediction[report["report_id"]]
        if result.get("metadata", {}).get("source_sha256") != _digest(report):
            raise ValueError("A saved result requires its exact source_sha256.")
        if result["status"] == "error" and result["observations"]:
            raise ValueError("A failed report cannot contain usable normalized observations.")
        if result["status"] == "ok" and (result.get("error") is not None or result.get("error_code") is not None):
            raise ValueError("Successful results cannot carry an extraction/normalization failure.")
        if result["status"] == "error" and not result.get("error_code"):
            raise ValueError("Failed results must identify their error code.")
        _indexed(result["observations"], "observation_id")
        for observation in result["observations"]:
            if not all(_evidence_matches(report, item) for item in observation["evidence"]):
                raise ValueError("Normalized evidence must match its original source.")
    _indexed(medication_changes, "change_id")
    for change in medication_changes:
        if set(change) != {"change_id", "patient_id", "medication", "changed_at", "change_type"}:
            raise ValueError("Medication changes require the documented fields only.")
        if change["patient_id"] not in by_patient:
            raise ValueError("A medication change must belong to a registered run patient.")
        _text(change["medication"], "medication")
        _timestamp(change["changed_at"])
        if change["change_type"] not in {"start", "stop", "dose_change"}:
            raise ValueError("Unknown medication change type.")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValueError("Run metadata must be an object.")
    payload = {"patients": sorted(patients, key=lambda r: r["patient_id"]),
               "reports": sorted(reports, key=lambda r: r["report_id"]),
               "predictions": sorted(predictions, key=lambda r: r["report_id"]),
               "medication_changes": sorted(medication_changes, key=lambda r: r["change_id"]), "metadata": metadata}
    digest = _hash(payload)
    with connection:
        existing = connection.execute("SELECT payload_sha256 FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if existing:
            if existing["payload_sha256"] != digest:
                raise ValueError("Changed content under an existing run_id; choose a new run_id.")
            return False
        for patient in patients:
            _immutable(connection, "patients", "patient_id", patient["patient_id"], patient, patient)
        for report in reports:
            _immutable(connection, "reports", "report_id", report["report_id"], report, {
                "report_id": report["report_id"], "patient_id": report["patient_id"],
                "reported_at": report["reported_at"], "patient_timezone": report["patient_timezone"],
                "source_text": report["text"], "questionnaire_json": _json(report["questionnaire_answers"]),
                "supersedes_report_id": report["supersedes_report_id"], "source_sha256": _digest(report)})
        for change in medication_changes:
            _immutable(connection, "medication_changes", "change_id", change["change_id"], change, {
                **change, "changed_utc": _utc(_timestamp(change["changed_at"]))})
        connection.execute("INSERT INTO runs VALUES (?,?,?,?)", (run_id, _utc(datetime.now(timezone.utc)), digest, _json(metadata)))
        connection.executemany("INSERT INTO run_patients VALUES (?,?,?)", [(run_id, p["patient_id"], i) for i, p in enumerate(patients)])
        connection.executemany("INSERT INTO run_medication_changes VALUES (?,?,?)", [(run_id, c["change_id"], i) for i, c in enumerate(medication_changes)])
        for index, report in enumerate(reports):
            result = by_prediction[report["report_id"]]
            connection.execute("INSERT INTO report_results VALUES (?,?,?,?,?,?,?,?,?,?)", (
                run_id, report["report_id"], index, result["status"], result.get("error_code"), result.get("error"),
                _json(result["candidates"]), result.get("raw_response"), _json(result.get("metadata", {})), _json(result)))
            for ordinal, observation in enumerate(result["observations"]):
                lower, upper, precision = _bounds(observation, report["patient_timezone"])
                connection.execute("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    run_id, report["report_id"], observation["observation_id"], ordinal, observation["symptom"],
                    observation["assertion"], observation["count"], observation["count_scope"], observation["severity"],
                    observation["event_date"], observation["event_time"], lower, upper, precision,
                    _json(observation["evidence"]), _json(observation["issues"]), _json(observation)))
    return True


def _require_run(connection, run_id: str, *, analysis: bool = False) -> None:
    table = "analyses" if analysis else "runs"
    if connection.execute(f"SELECT 1 FROM {table} WHERE run_id = ?", (run_id,)).fetchone() is None:
        raise ValueError("Run analysis is not available." if analysis else "Unknown run_id.")


def load_run(connection: sqlite3.Connection, run_id: str) -> dict:
    _require_run(connection, run_id)
    def values(query, column):
        return [json.loads(row[column]) for row in connection.execute(query, (run_id,))]
    patients = values("SELECT p.source_json FROM patients p JOIN run_patients r USING(patient_id) WHERE r.run_id=? ORDER BY r.ordinal", "source_json")
    reports = values("SELECT p.source_json FROM reports p JOIN report_results r USING(report_id) WHERE r.run_id=? ORDER BY r.ordinal", "source_json")
    predictions = values("SELECT result_json FROM report_results WHERE run_id=? ORDER BY ordinal", "result_json")
    changes = values("SELECT p.source_json FROM medication_changes p JOIN run_medication_changes r USING(change_id) WHERE r.run_id=? ORDER BY r.ordinal", "source_json")
    metadata = json.loads(connection.execute("SELECT metadata_json FROM runs WHERE run_id=?", (run_id,)).fetchone()[0])
    return {"patients": patients, "reports": reports, "predictions": predictions, "medication_changes": changes, "metadata": metadata}


def save_analysis(connection: sqlite3.Connection, run_id: str, analysis: dict) -> bool:
    """Replace only derived query materializations, atomically; raw records remain immutable."""
    source = load_run(connection, run_id)
    if not isinstance(analysis, dict) or set(analysis) != {"daily", "review", "corrections", "effective_report_ids"}:
        raise ValueError("Analysis must contain daily, review, corrections and effective_report_ids.")
    by_report = {r["report_id"]: r for r in source["reports"]}
    observation_ids = {r["report_id"]: {o["observation_id"] for o in r["observations"]} for r in source["predictions"]}
    expected_days = set()
    for patient in source["patients"]:
        cursor, end = _date(patient["followup_start"]), _date(patient["followup_end"])
        while cursor <= end:
            expected_days.add((patient["patient_id"], cursor.isoformat()))
            cursor += timedelta(days=1)
    actual_days = [(r["patient_id"], r["event_date"]) for r in analysis["daily"]]
    if len(actual_days) != len(set(actual_days)) or set(actual_days) != expected_days:
        raise ValueError("Daily analysis must cover every registered follow-up day exactly once.")
    effective = analysis["effective_report_ids"]
    if not isinstance(effective, list) or len(effective) != len(set(effective)) or not set(effective) <= by_report.keys():
        raise ValueError("Effective report IDs must be unique members of the selected run.")
    for row in analysis["daily"]:
        for field, status_field, maximum in (("vomiting_count", "count_status", None),
                                               ("nausea_severity", "nausea_status", 5),
                                               ("vomiting_severity", "vomiting_severity_status", 5)):
            value, status = row[field], row[status_field]
            if status not in {"usable", "review", "missing"}:
                raise ValueError("Unknown daily field status.")
            if (status == "usable") != (value is not None):
                raise ValueError("Only usable daily fields may contain a numeric value.")
            if value is not None and (type(value) is not int or value < (1 if maximum else 0)
                                      or maximum is not None and value > maximum):
                raise ValueError("Invalid daily count or severity value.")
        if type(row["report_count"]) is not int or row["report_count"] < 0:
            raise ValueError("Daily report_count must be a nonnegative integer.")
        day = _date(row["event_date"])
        if row["week_start"] != (day - timedelta(days=day.weekday())).isoformat():
            raise ValueError("week_start must be the Monday containing event_date.")
        if any(identifier not in by_report or by_report[identifier]["patient_id"] != row["patient_id"] for identifier in row["source_report_ids"]):
            raise ValueError("Daily provenance must refer to this patient's run reports.")
    for row in analysis["review"]:
        if row["report_id"] not in by_report or row["patient_id"] != by_report[row["report_id"]]["patient_id"]:
            raise ValueError("Review items must reference this run's patient and report.")
        if row["observation_id"] is not None and row["observation_id"] not in observation_ids[row["report_id"]]:
            raise ValueError("Review observation must belong to its selected run report.")
        if row["event_date"] is not None:
            _date(row["event_date"])
        _text(row["field"], "review field")
        _text(row["reason"], "review reason")
    for row in analysis["corrections"]:
        if row["report_id"] not in by_report or by_report[row["report_id"]]["supersedes_report_id"] != row["target_report_id"]:
            raise ValueError("Correction decisions must use the source's explicit replacement link.")
    digest = _hash(analysis)
    with connection:
        old = connection.execute("SELECT payload_sha256 FROM analyses WHERE run_id=?", (run_id,)).fetchone()
        if old and old[0] == digest:
            return False
        for table in ("daily_summary", "review_items", "correction_decisions", "effective_reports", "analyses"):
            connection.execute(f"DELETE FROM {table} WHERE run_id=?", (run_id,))
        connection.execute("INSERT INTO analyses VALUES (?,?,?,?)", (run_id, _utc(datetime.now(timezone.utc)), digest, _json(analysis)))
        connection.executemany("INSERT INTO effective_reports VALUES (?,?)", [(run_id, r) for r in effective])
        for row in analysis["daily"]:
            connection.execute("INSERT INTO daily_summary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                run_id, row["patient_id"], row["event_date"], row["week_start"], row["vomiting_count"],
                row["count_basis"], row["count_status"], row["nausea_severity"], row["nausea_status"],
                row["vomiting_severity"], row["vomiting_severity_status"], row["report_count"],
                _json(row["source_report_ids"]), _json(row["review_reasons"]), _json(row)))
        for index, row in enumerate(analysis["review"]):
            connection.execute("INSERT INTO review_items VALUES (?,?,?,?,?,?,?,?,?)", (
                run_id, index, row["patient_id"], row["report_id"], row["observation_id"], row["event_date"], row["field"], row["reason"], _json(row)))
        for row in analysis["corrections"]:
            connection.execute("INSERT INTO correction_decisions VALUES (?,?,?,?,?,?)", (
                run_id, row["report_id"], row["target_report_id"], row["status"], row["reason"], _json(row)))
    return True


def daily_records(connection: sqlite3.Connection, run_id: str) -> list[dict]:
    _require_run(connection, run_id, analysis=True)
    return [json.loads(r[0]) for r in connection.execute("SELECT row_json FROM daily_summary WHERE run_id=? ORDER BY patient_id,event_date", (run_id,))]


def weekly_counts(connection: sqlite3.Connection, run_id: str) -> list[dict]:
    _require_run(connection, run_id, analysis=True)
    return [dict(r) for r in connection.execute((SQL_ROOT / "weekly_counts.sql").read_text(), {"run_id": run_id})]


def after_medication_change(connection: sqlite3.Connection, run_id: str) -> list[dict]:
    _require_run(connection, run_id, analysis=True)
    rows = []
    for row in connection.execute((SQL_ROOT / "after_medication_change.sql").read_text(), {"run_id": run_id}):
        value = dict(row)
        value["evidence"] = json.loads(value.pop("evidence_json"))
        value["issues"] = json.loads(value.pop("issues_json"))
        value["has_review_items"] = bool(value["has_review_items"])
        rows.append(value)
    return rows


def review_queue(connection: sqlite3.Connection, run_id: str) -> list[dict]:
    _require_run(connection, run_id, analysis=True)
    return [json.loads(row[0]) for row in connection.execute("SELECT row_json FROM review_items WHERE run_id=? ORDER BY ordinal", (run_id,))]
