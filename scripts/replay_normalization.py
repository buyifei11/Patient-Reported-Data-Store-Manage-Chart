"""Replay the frozen temporal experiment's candidates without model requests."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from src.evaluation import evaluate_predictions
from src.normalization import NormalizationError, normalize_report
from src.pipeline import _code_digest, _digest, read_jsonl, validate_fixtures, validate_predictions
from src.schema import validate_sources


BASE_REVISION = "be6114310772db621475420e285ede57fa623a17"
BASE_CODE_SHA256 = "de076b5cf30df5e2e99dbf9f0cbf373273c4b066dc93ff350bde89cceac1eee1"
NORMALIZATION_ERROR = "Candidates failed provenance or normalization checks; inspect the saved candidates."


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("experiment") != "temporal-prompt-v2":
        raise ValueError("This replay is scoped to the frozen temporal-prompt-v2 experiment.")
    # Only normalization may change. In particular, changing labels or scoring
    # would prevent attributing differences to the normalization fix.
    for relative, expected in manifest["files"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError(f"Invalid frozen path: {relative}")
        if relative != "src/normalization.py" and file_hash(path) != expected:
            raise ValueError(f"Replay input changed: {relative}")
    return manifest


def verify_predictions(directory: Path, manifest: dict, sources: list[dict],
                       rows: list[dict], split: str, repeat: int, label: str) -> None:
    validate_predictions(sources, rows)
    by_id = {source["report_id"]: source for source in sources}
    ids = [row["report_id"] for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(by_id):
        raise ValueError("Replay requires exactly one saved prediction per source report.")
    expected = {
        "backend": "openai", "requested_model": manifest["model"],
        "experiment": manifest["experiment"], "split": split, "repeat": repeat,
        "prompt_label": label,
        "prompt_file_sha256": manifest["files"][manifest["prompts"][label]],
        "manifest_sha256": file_hash(directory / "manifest.json"),
        "source_dataset_sha256": _digest(sources), "code_sha256": BASE_CODE_SHA256,
    }
    for row in rows:
        metadata = row["metadata"]
        for field, value in {**expected, "source_sha256": _digest(by_id[row["report_id"]])}.items():
            if type(metadata.get(field)) is not type(value) or metadata[field] != value:
                raise ValueError(f"{row['report_id']}: saved metadata mismatch for {field}")
        if row["status"] == "ok" or row.get("error_code") == "normalization_error":
            if metadata.get("returned_model") != manifest["model"]:
                raise ValueError(f"{row['report_id']}: unexpected returned model")


def replay_row(source: dict, saved: dict) -> dict:
    """Retry normalization only; never reinterpret an extraction failure."""
    row = copy.deepcopy(saved)
    if row["status"] != "ok" and row.get("error_code") != "normalization_error":
        return row
    try:
        row["observations"] = normalize_report(source, row["candidates"])
        row.update(status="ok", error=None, error_code=None)
    except (NormalizationError, ValidationError, ValueError):
        row.update(status="error", observations=[], error=NORMALIZATION_ERROR,
                   error_code="normalization_error")
    return row


def payload(row: dict) -> dict:
    return {key: row.get(key) for key in ("status", "error_code", "error", "observations")}


def compact(metrics: dict) -> dict:
    return {
        "report_completion": metrics["report_completion"],
        "observation_detection": metrics["observation_detection"],
        "date_known": metrics["fields"]["event_date"]["reference_known"],
        "count_known": metrics["fields"]["count"]["reference_known"],
        "count_null": metrics["fields"]["count"]["reference_null"],
        "scope_known": metrics["fields"]["count_scope"]["reference_known"],
        "assertion_accuracy": metrics["assertion_accuracy"],
        "issue_detection": metrics["issue_detection"],
        "unknown_overfill": metrics["unknown_overfill"],
    }


def replay(directory: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Replay output directory already exists; choose a new directory.")
    manifest = verify_inputs(directory)
    summary = {
        "kind": "offline_normalization_replay", "reference_role": "known_regression_data",
        "created_at": datetime.now(timezone.utc).isoformat(), "model_requests": 0,
        "interpretation": "Same saved candidates under revised normalization; not new model output or independent held-out evidence.",
        "base_revision": BASE_REVISION,
        "base_manifest_sha256": file_hash(directory / "manifest.json"),
        "base_code_sha256": BASE_CODE_SHA256, "current_code_sha256": _code_digest(),
        "normalization_sha256": file_hash(ROOT / "src/normalization.py"),
        "replay_script_sha256": file_hash(Path(__file__)), "runs": {},
    }
    artifacts, changes = {}, []
    for split, paths in manifest["groups"].items():
        sources = validate_sources([row for source, _ in paths for row in read_jsonl(ROOT / source)])
        gold = validate_fixtures(sources, [row for _, reference in paths for row in read_jsonl(ROOT / reference)])
        by_id = {source["report_id"]: source for source in sources}
        for repeat in range(1, manifest["repeats"][split] + 1):
            for label in manifest["prompts"]:
                stem = f"{split}-{label}-r{repeat}"
                predictions_path = directory / f"{stem}.predictions.jsonl"
                saved = read_jsonl(predictions_path)
                verify_predictions(directory, manifest, sources, saved, split, repeat, label)
                old_metrics_path = directory / f"{stem}.metrics.json"
                old_metrics = json.loads(old_metrics_path.read_text())
                expected_provenance = {
                    "manifest_sha256": summary["base_manifest_sha256"],
                    "predictions_sha256": file_hash(predictions_path),
                    "source_sha256": _digest(sources), "gold_sha256": _digest(gold),
                    "split": split, "repeat": repeat,
                }
                if old_metrics.get("provenance") != expected_provenance:
                    raise ValueError(f"{stem}: original metric provenance mismatch")
                before = evaluate_predictions(sources, gold, saved)
                if any(before[key] != old_metrics.get(key) for key in before if key != "reference_role"):
                    raise ValueError(f"{stem}: original scores do not reproduce")
                replayed = [replay_row(by_id[row["report_id"]], row) for row in saved]
                after = evaluate_predictions(sources, gold, replayed)
                changed_ids = []
                for old, new in zip(saved, replayed):
                    if payload(old) != payload(new):
                        changed_ids.append(old["report_id"])
                        changes.append({"run": stem, "report_id": old["report_id"],
                                        "candidates": old["candidates"],
                                        "before": payload(old), "after": payload(new)})
                after["reference_role"] = "known_regression_data"
                after["provenance"] = {
                    **expected_provenance, "kind": summary["kind"],
                    "original_metrics_sha256": file_hash(old_metrics_path),
                    "current_code_sha256": summary["current_code_sha256"],
                    "replay_script_sha256": summary["replay_script_sha256"],
                }
                artifacts[f"{stem}.metrics.json"] = after
                summary["runs"][stem] = {
                    "saved_predictions_sha256": file_hash(predictions_path),
                    "original_metrics_sha256": file_hash(old_metrics_path),
                    "replayed_reports": len(saved), "changed_report_ids": changed_ids,
                    "extraction_checks_unchanged": before["extraction_checks"] == after["extraction_checks"],
                    "before": compact(before), "after": compact(after),
                }
    # Preflight and all scoring finish before creating outputs. Never modify the
    # frozen experiment or write new inference metadata onto old model responses.
    output.mkdir(parents=True, exist_ok=False)
    for name, value in {**artifacts, "changes.json": changes, "summary.json": summary}.items():
        with (output / name).open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/temporal-prompt-v2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = replay(args.input, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
    for name, run in summary["runs"].items():
        print(f"{name}: changed {run['changed_report_ids']}")
    print(f"Saved offline replay to {args.output}; no model requests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
