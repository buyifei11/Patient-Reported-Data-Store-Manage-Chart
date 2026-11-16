"""An offline, source-to-SQL-to-chart demonstration using actual saved candidates."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from src.aggregation import aggregate
from src.dashboard import write_dashboard
from src.pipeline import ROOT, _code_digest, _digest, process_report, read_jsonl, validate_predictions
from src.schema import validate_sources
from src import store


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_predictions(reports: list[dict], cache: Path) -> list[dict]:
    """Use validated saved text candidates, or direct questionnaires for empty text.

    No reference labels, model client, or credentials are read. A new uncached
    text report is rejected rather than treated as a symptom-free submission.
    Recorded evidence exceptions are verified and reapplied to working candidates;
    cached normalized values never become the source of a chart value.
    """
    rows = read_jsonl(cache)
    indexed = {r["report_id"]: r for r in rows}
    if len(rows) != len(indexed):
        raise ValueError("Duplicate report IDs in the extraction cache.")
    requested = [indexed[r["report_id"]] for r in reports if r["text"].strip() and r["report_id"] in indexed]
    validate_predictions(reports, requested)
    code_hash, cache_hash = _code_digest(), _sha(cache)
    results = []
    for report in reports:
        if report["text"].strip():
            saved = indexed.get(report["report_id"])
            if saved is None or saved.get("metadata", {}).get("source_sha256") != _digest(report):
                raise ValueError(f"{report['report_id']}: missing or stale cached extraction. Run the extraction CLI first.")
            metadata = {"processing_mode": "saved_candidate_replay", "backend": "saved_candidates",
                        "code_sha256": code_hash, "cache_file_sha256": cache_hash,
                        "original_inference_metadata": saved["metadata"], "model_requests": 0}
            if saved["status"] != "ok" and saved.get("error_code") != "normalization_error":
                results.append({**saved, "observations": [], "metadata": {**metadata, "source_sha256": _digest(report)}})
                continue
            if "evidence_review" in saved:
                envelope = saved["evidence_review"]
                if not isinstance(envelope, dict) or envelope.get("kind") != "review_assisted_evidence_only_replay":
                    raise ValueError(f"{report['report_id']}: invalid evidence review envelope.")
                review = envelope.get("review")
                if not isinstance(review, dict) or envelope.get("review_sha256") != _digest(review):
                    raise ValueError(f"{report['report_id']}: evidence review hash does not match its content.")
                # The helper validates exact source/candidate hashes and restores
                # only the approved source span before running normalization. It
                # preserves the original candidates, response, and review record.
                from scripts.replay_reviewed_evidence import reviewed_replay

                replayed = reviewed_replay(report, saved, review)
                replayed["metadata"] = {**metadata, "source_sha256": _digest(report),
                                        "processing_mode": "reviewed_candidate_replay"}
                results.append(replayed)
                continue
            extracted = {"candidates": saved["candidates"], "raw_response": saved.get("raw_response"), "metadata": {}}
        else:
            metadata = {"processing_mode": "structured_questionnaire", "backend": "questionnaire",
                        "code_sha256": code_hash, "model_requests": 0}
            extracted = {"candidates": [], "raw_response": None, "metadata": {}}
        # process_report always runs the current deterministic normalizer. The
        # extractor here returns recorded source candidates, never gold answers.
        results.append(process_report(report, lambda _text, value=extracted: value, metadata))
    return results


def _csv(path: Path, rows: list[dict]) -> None:
    def cell(value):
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        # Keep raw values in SQLite. Spreadsheet applications must not execute
        # a source label as a formula when someone opens the exported CSV.
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    with path.open("x", newline="", encoding="utf-8") as handle:
        if not rows:
            return
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: cell(v) for k, v in row.items()})


def build(output: Path, dataset: Path = ROOT / "data/longitudinal",
          cache: Path = ROOT / "results/gpt54mini-dev-v1/predictions.jsonl",
          run_id: str = "longitudinal-v1") -> dict:
    if output.exists():
        raise ValueError("Output directory already exists. Choose a new directory to preserve the previous run.")
    patients = json.loads((dataset / "patients.json").read_text())
    reports = validate_sources(read_jsonl(dataset / "reports.jsonl"))
    changes = json.loads((dataset / "medication_changes.json").read_text())
    predictions = prepare_predictions(reports, cache)
    text_reports = sum(bool(r["text"].strip()) for r in reports)
    if text_reports == len(reports) and not any(r["questionnaire_answers"] for r in reports):
        description = "Synthetic follow-up; all reports use saved LLM text extractions"
    elif text_reports == 0:
        description = "Synthetic follow-up; structured questionnaires"
    else:
        description = "Synthetic four-week follow-up; saved LLM candidates plus structured questionnaires"
    metadata = {"description": description,
                "cached_text_reports": text_reports,
                "questionnaire_reports": len(reports) - text_reports,
                "reviewed_evidence_reports": sum("evidence_review" in p for p in predictions),
                "model_requests": 0, "runtime_sha256": _code_digest(), "cache_sha256": _sha(cache),
                "dashboard_template_sha256": _sha(ROOT / "web/dashboard.html"),
                "dataset_files": {name: _sha(dataset / name) for name in ("patients.json", "reports.jsonl", "medication_changes.json")}}
    output.mkdir(parents=True)
    connection = store.connect(output / "patient_reports.sqlite")
    try:
        store.import_run(connection, run_id=run_id, patients=patients, reports=reports,
                         predictions=predictions, medication_changes=changes, metadata=metadata)
        # Statistics and charts are built from the stored records, never from
        # reference fixtures or a separate display-only data array.
        saved = store.load_run(connection, run_id)
        analysis = aggregate(saved["patients"], saved["reports"], saved["predictions"])
        store.save_analysis(connection, run_id, analysis)
        daily = store.daily_records(connection, run_id)
        weekly = store.weekly_counts(connection, run_id)
        after = store.after_medication_change(connection, run_id)
        review = store.review_queue(connection, run_id)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok" or connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Database integrity validation failed.")
        local_changes = [{**change, "local_date": datetime.fromisoformat(change["changed_at"]).astimezone(
            ZoneInfo(next(p["patient_timezone"] for p in patients if p["patient_id"] == change["patient_id"]))
        ).date().isoformat()} for change in saved["medication_changes"]]
        dashboard = {**saved, "run_id": run_id, "daily": daily, "weekly": weekly,
                     "after_medication": after, "review": review, "medication_changes": local_changes,
                     "corrections": analysis["corrections"], "effective_report_ids": analysis["effective_report_ids"]}
        write_dashboard(output / "dashboard.html", dashboard)
        for name, rows in (("daily.csv", daily), ("weekly_counts.csv", weekly),
                           ("after_medication_change.csv", after), ("review_queue.csv", review)):
            _csv(output / name, rows)
        with (output / "predictions.jsonl").open("x") as handle:
            for row in saved["predictions"]:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        summary = {"run_id": run_id, "model_requests": 0, "patients": len(patients),
                   "reports": len(reports), "normalized_observations": sum(len(p["observations"]) for p in predictions),
                   "failed_reports": sum(p["status"] != "ok" for p in predictions),
                   "followup_patient_days": len(daily), "usable_count_days": sum(d["count_status"] == "usable" for d in daily),
                   "count_review_days": sum(d["count_status"] == "review" for d in daily),
                   "missing_count_days": sum(d["count_status"] == "missing" for d in daily),
                   "review_items": len(review), "corrections": analysis["corrections"],
                   "database_integrity": integrity, "metadata": metadata}
        with (output / "summary.json").open("x") as handle:
            json.dump(summary, handle, indent=2); handle.write("\n")
        return summary
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("build", help="Build a local SQLite database, query exports, and offline dashboard")
    create.add_argument("--output", type=Path, default=ROOT / "artifacts/demo")
    create.add_argument("--dataset", type=Path, default=ROOT / "data/longitudinal")
    create.add_argument("--cached-predictions", type=Path, default=ROOT / "results/gpt54mini-dev-v1/predictions.jsonl")
    create.add_argument("--run-id", default="longitudinal-v1")
    query = commands.add_parser("query", help="Run one of the stored-data SQL queries")
    query.add_argument("--db", type=Path, required=True)
    query.add_argument("--run-id", default="longitudinal-v1")
    query.add_argument("--query", choices=("weekly", "medication", "review"), required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            print(json.dumps(build(args.output, args.dataset, args.cached_predictions, args.run_id), indent=2))
            print(f"Open {args.output / 'dashboard.html'} in your browser.")
        else:
            if not args.db.is_file():
                raise ValueError("Database does not exist. Run build first.")
            connection = store.connect(args.db, read_only=True)
            try:
                func = {"weekly": store.weekly_counts, "medication": store.after_medication_change,
                        "review": store.review_queue}[args.query]
                print(json.dumps(func(connection, args.run_id), indent=2, ensure_ascii=False))
            finally:
                connection.close()
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, f"{exc}\n")
    return 0
