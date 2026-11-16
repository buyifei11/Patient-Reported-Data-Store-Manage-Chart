"""Replay the frozen compact-prompt candidates under the daily nausea fix, offline."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.replay_normalization import payload, replay_row
from src.evaluation import evaluate_predictions
from src.pipeline import _code_digest, read_jsonl, validate_fixtures, validate_predictions
from src.schema import validate_sources


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def replay(output):
    directory = ROOT / "results/text-validation-nausea"
    protocol = json.loads((directory / "protocol.json").read_text())
    for relative, expected in protocol["frozen_files"].items():
        if relative != "src/normalization.py" and sha(ROOT / relative) != expected:
            raise ValueError(f"Frozen comparator, data, or runtime changed: {relative}")
    sources = validate_sources(read_jsonl(ROOT / protocol["source_file"]))
    gold = validate_fixtures(sources, read_jsonl(ROOT / protocol["gold_file"]))
    saved = validate_predictions(sources, read_jsonl(ROOT / protocol["stage_1"]["input"]))
    if [r["report_id"] for r in saved] != protocol["report_ids"]:
        raise ValueError("Saved report order does not match the frozen protocol.")
    before = evaluate_predictions(sources, gold, saved)
    original_metrics = json.loads((ROOT / "results/text-validation-compact/metrics.json").read_text())
    if before != {k: v for k, v in original_metrics.items() if k != "provenance"}:
        raise ValueError("Original evaluation did not reproduce.")
    provenance = {
        "kind": "offline_normalization_replay", "model_requests": 0,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "original_predictions": protocol["stage_1"]["input"],
        "original_predictions_sha256": sha(ROOT / protocol["stage_1"]["input"]),
        "original_runtime_sha256": protocol["base_runtime_sha256"],
        "normalization_runtime_sha256": _code_digest(),
        "replay_script_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(directory / "protocol.json"),
        "metadata_policy": "metadata describes the original extraction; normalization_replay describes this offline replay. Original token usage is not new usage.",
    }
    by_id = {r["report_id"]: r for r in sources}
    rows, changes = [], []
    for old in saved:
        row = replay_row(by_id[old["report_id"]], old)
        for key in ("candidates", "raw_response", "metadata"):
            if row[key] != old[key]:
                raise ValueError(f"Replay altered original {key}.")
        row["normalization_replay"] = provenance
        rows.append(row)
        if payload(old) != payload(row):
            changes.append({"report_id": row["report_id"], "before": payload(old), "after": payload(row)})
    validate_predictions(sources, rows)
    after = evaluate_predictions(sources, gold, rows)
    if before["extraction_checks"] != after["extraction_checks"]:
        raise ValueError("Raw candidate metrics changed in a normalization-only replay.")
    summary = {
        **provenance, "changed_reports": [c["report_id"] for c in changes],
        "original_candidates_raw_responses_metadata_unchanged": True,
        "raw_extraction_metrics_unchanged": True,
        "original_whole_report_rule_still_fails": ["TV007", "TV009"],
        "interpretation": "Only normalized structure improves. Duplicate raw candidates still fail the frozen end-to-end rule.",
        "arms": {},
    }
    for label, predictions, metrics in (("saved", saved, before), ("python_replay", rows, after)):
        per_report = []
        for source, reference, row in zip(sources, gold, predictions):
            per = evaluate_predictions([source], [reference], [row])
            errors = [m for m in per["mismatches"] if m["kind"] != "extraction_check"
                      and not (m["kind"] == "field" and m["field"] == "time_text")]
            per_report.append({"report_id": row["report_id"],
                               "normalized_values_and_structure_pass": row["status"] == "ok" and not errors and not per["matching"]["ambiguous_groups"]})
        summary["arms"][label] = {
            "emitted_candidates": sum(len(r["candidates"]) for r in predictions),
            "normalized_observations": sum(len(r["observations"]) for r in predictions),
            "normalized_core_fields": {
                kind: {metric: sum(metrics["fields"][f]["reference_" + kind][metric]
                                   for f in protocol["normalized_core_fields"])
                       for metric in ("correct", "total")} for kind in ("known", "null")},
            "automatic_candidate_fields": {
                "correct": sum(v["correct"] for v in metrics["extraction_checks"]["fields"].values()), "total": 165},
            "observation_detection": metrics["observation_detection"],
            "reports": per_report,
        }
    output.mkdir(parents=True, exist_ok=False)
    with (output / "predictions.jsonl").open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    after["provenance"] = {**provenance, "predictions_sha256": sha(output / "predictions.jsonl")}
    write_json(output / "metrics.json", after)
    write_json(output / "changes.json", changes)
    write_json(output / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.output)
    print(json.dumps({"model_requests": 0, "changed_reports": result["changed_reports"],
                      "arms": {k: {f: v for f, v in arm.items() if f != "reports"} for k, arm in result["arms"].items()}}, indent=2))
