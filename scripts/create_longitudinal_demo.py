"""Create deterministic fictional questionnaire follow-up, not model-test gold."""

from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pipeline import read_jsonl
from src.schema import validate_sources


def generate():
    start = date(2026, 11, 1)
    patients = [{"patient_id": f"P00{i}", "display_name": f"Demo patient {i}",
                 "patient_timezone": "America/Chicago", "followup_start": start.isoformat(),
                 "followup_end": "2026-11-28"} for i in (1, 2, 3)]
    reports = read_jsonl(ROOT / "data/raw/reports.jsonl")
    settings = {
        "P001": (4, {8, 16, 25}, [2, 3, 1, 1], [3, 4, 2, 2]),
        "P002": (5, {7, 12, 20}, [3, 2, 2, 1], [4, 3, 3, 2]),
        "P003": (9, {11, 18, 26}, [1, 2, 2, 1], [2, 3, 3, 2]),
    }
    for patient in patients:
        pid = patient["patient_id"]
        first, missing, counts, severities = settings[pid]
        for day in range(first, 29):
            if day in missing:
                continue
            local_day = start + timedelta(days=day - 1)
            week = (day - 1) // 7
            count = max(0, counts[week] + [-1, 0, 1, 0, -1, 0, 1][(day - 1) % 7])
            severity = max(1, min(5, severities[week] + [0, 0, 1, 0, -1, 0, 0][(day - 1) % 7]))
            if pid == "P001" and day == 10:
                count = 1  # An unexplained decrease from a morning snapshot below.
            if pid == "P003" and day == 14:
                count = None  # Presence via severity, but unknown episode count.
            answers = [
                {"symptom": "vomiting", "event_date": local_day.isoformat(), "count": count,
                 "severity": None if count == 0 else 2},
                {"symptom": "nausea", "event_date": local_day.isoformat(), "count": None,
                 "severity": severity},
            ]
            reports.append({"report_id": f"L-{pid}-{day:02}", "patient_id": pid,
                            "reported_at": datetime(2026, 11, day, 20, 30,
                                                    tzinfo=ZoneInfo(patient["patient_timezone"])).isoformat(),
                            "patient_timezone": patient["patient_timezone"], "text": "",
                            "questionnaire_answers": answers, "supersedes_report_id": None})
    reports.append({"report_id": "L-P001-10-AM", "patient_id": "P001",
                    "reported_at": "2026-11-10T10:00:00-06:00", "patient_timezone": "America/Chicago",
                    "text": "", "questionnaire_answers": [
                        {"symptom": "vomiting", "event_date": "2026-11-10", "count": 4, "severity": 2},
                        {"symptom": "nausea", "event_date": "2026-11-10", "count": None, "severity": 4}],
                    "supersedes_report_id": None})
    changes = [
        {"change_id": "M001", "patient_id": "P001", "medication": "Medication A",
         "changed_at": "2026-11-01T08:00:00-06:00", "change_type": "start"},
        {"change_id": "M002", "patient_id": "P001", "medication": "Medication A",
         "changed_at": "2026-11-15T12:00:00-06:00", "change_type": "dose_change"},
        {"change_id": "M003", "patient_id": "P002", "medication": "Medication B",
         "changed_at": "2026-11-03T13:00:00-06:00", "change_type": "start"},
        {"change_id": "M004", "patient_id": "P002", "medication": "Medication B",
         "changed_at": "2026-11-17T10:00:00-06:00", "change_type": "dose_change"},
        {"change_id": "M005", "patient_id": "P003", "medication": "Medication A",
         "changed_at": "2026-11-08T08:00:00-06:00", "change_type": "start"},
    ]
    return patients, validate_sources(reports), changes


if __name__ == "__main__":
    target = ROOT / "data/longitudinal"
    patients, reports, changes = generate()
    target.mkdir(parents=True, exist_ok=True)
    paths = [target / name for name in ("patients.json", "reports.jsonl", "medication_changes.json")]
    if any(p.exists() for p in paths):
        raise SystemExit("Demo source files already exist; do not overwrite authored sources.")
    paths[0].write_text(json.dumps(patients, indent=2) + "\n")
    paths[1].write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in reports))
    paths[2].write_text(json.dumps(changes, indent=2) + "\n")
    print(f"Created {len(reports)} reports, {len(patients)} patients, and {len(changes)} medication changes.")
