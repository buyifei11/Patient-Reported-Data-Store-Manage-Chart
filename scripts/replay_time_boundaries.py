"""Recheck saved candidates with stricter time boundaries, without model calls."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.replay_normalization import file_hash, payload, replay_row
from src.normalization import normalize_report
from src.pipeline import _code_digest, _digest, read_jsonl, validate_predictions
from src.schema import validate_sources


BASE_REVISION = "66a55605303a818a99c77d7f768006966351a01b"
BASE_CODE_SHA256 = "d9dedbf210c524f0783aa11470d2cf47a1f0a937c035dc5598c82adc39384ed6"
BASE_MANIFEST_SHA256 = "30078111ab94c0a0ffc3296f6da18faa2a0f1594f0cd7216ed18720d34dbaf78"
BASE_SUMMARY_SHA256 = "18bcf1408ffb75962ddbd3cb3b7ea2130ccadf60beaeaf2cf43e247b0ddcc835"


def verify_inputs(directory: Path) -> tuple[dict, dict]:
    """Only normalization may differ among the original frozen runtime files."""
    if file_hash(directory / "manifest.json") != BASE_MANIFEST_SHA256:
        raise ValueError("This replay requires the unchanged scope-evidence-v3 manifest.")
    if file_hash(directory / "summary.json") != BASE_SUMMARY_SHA256:
        raise ValueError("Historical rejection reasons must come from the unchanged original summary.")
    manifest = json.loads((directory / "manifest.json").read_text())
    summary = json.loads((directory / "summary.json").read_text())
    for relative, expected in manifest["files"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError(f"Invalid frozen path: {relative}")
        if relative != "src/normalization.py" and file_hash(path) != expected:
            raise ValueError(f"Frozen input changed: {relative}")
    return manifest, summary


def verify_run(directory: Path, manifest: dict, historical: dict, sources: list[dict],
               split: str, repeat: int, label: str) -> list[dict]:
    stem = f"{split}-{label}-r{repeat}"
    predictions_path = directory / f"{stem}.predictions.jsonl"
    metrics_path = directory / f"{stem}.metrics.json"
    recorded = historical["runs"][stem]
    if file_hash(predictions_path) != recorded["predictions_sha256"]:
        raise ValueError(f"{stem}: original predictions changed.")
    if file_hash(metrics_path) != recorded["metrics_sha256"]:
        raise ValueError(f"{stem}: original metric provenance changed.")
    metrics = json.loads(metrics_path.read_text())
    references = [row for _, path in manifest["groups"][split] for row in read_jsonl(ROOT / path)]
    expected_provenance = {
        "manifest_sha256": BASE_MANIFEST_SHA256,
        "predictions_sha256": file_hash(predictions_path),
        "source_sha256": _digest(sources), "gold_sha256": _digest(references),
        "split": split, "repeat": repeat,
    }
    if metrics["provenance"] != expected_provenance:
        raise ValueError(f"{stem}: source/reference provenance mismatch.")
    rows = validate_predictions(sources, read_jsonl(predictions_path))
    by_id = {source["report_id"]: source for source in sources}
    ids = [row["report_id"] for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(by_id):
        raise ValueError(f"{stem}: expected exactly one saved output per source.")
    expected = {
        "backend": "openai", "requested_model": manifest["model"],
        "experiment": manifest["experiment"], "split": split, "repeat": repeat,
        "prompt_label": label, "prompt_file": Path(manifest["prompts"][label]).name,
        "prompt_file_sha256": manifest["files"][manifest["prompts"][label]],
        "manifest_sha256": BASE_MANIFEST_SHA256,
        "source_dataset_sha256": _digest(sources), "code_sha256": BASE_CODE_SHA256,
    }
    for row in rows:
        for field, value in {**expected, "source_sha256": _digest(by_id[row["report_id"]])}.items():
            actual = row["metadata"].get(field)
            if type(actual) is not type(value) or actual != value:
                raise ValueError(f"{stem}/{row['report_id']}: metadata mismatch for {field}.")
        if row["status"] == "ok" or row.get("error_code") == "normalization_error":
            if row["metadata"].get("returned_model") != manifest["model"]:
                raise ValueError(f"{stem}/{row['report_id']}: wrong returned model.")
    return rows


def rejection_reason(source: dict, row: dict) -> str | None:
    if row["status"] == "ok":
        return None
    if row.get("error_code") != "normalization_error":
        return row.get("error_code") or "recorded_extraction_failure"
    try:
        normalize_report(source, row["candidates"])
    except ValueError as exc:
        return str(exc).splitlines()[0]
    raise ValueError("Recorded replay normalization failure did not reproduce.")


def replay(directory: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Output directory already exists; choose a new directory.")
    manifest, historical = verify_inputs(directory)
    summary = {
        "kind": "offline_time_boundary_replay", "reference_role": "known_regression_data",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "interpretation": "Same saved candidates under stricter time guards. More rejected reports mean unsupported clock claims are exposed, not that model extraction accuracy improved.",
        "base_revision": BASE_REVISION, "base_manifest_sha256": BASE_MANIFEST_SHA256,
        "base_summary_sha256": BASE_SUMMARY_SHA256, "base_code_sha256": BASE_CODE_SHA256,
        "current_code_sha256": _code_digest(), "normalization_sha256": file_hash(ROOT / "src/normalization.py"),
        "replay_script_sha256": file_hash(Path(__file__)),
        "replay_helper_sha256": file_hash(ROOT / "scripts/replay_normalization.py"),
        "model_requests": 0, "unique_reports": 70, "saved_outputs": 0,
        "unchanged_extraction_payloads": 0, "changed_outputs": 0,
        "before_status_counts": {}, "after_status_counts": {}, "runs": {},
    }
    changes, all_before, all_after = [], Counter(), Counter()
    for split, paths in manifest["groups"].items():
        sources = validate_sources([row for path, _ in paths for row in read_jsonl(ROOT / path)])
        by_id = {row["report_id"]: row for row in sources}
        for repeat in range(1, manifest["repeats"][split] + 1):
            for label in manifest["prompts"]:
                stem = f"{split}-{label}-r{repeat}"
                saved = verify_run(directory, manifest, historical, sources, split, repeat, label)
                before_reasons = {r["report_id"]: r["first_normalization_rejection"]
                                  for r in historical["runs"][stem]["failures"]}
                if set(before_reasons) != {row["report_id"] for row in saved if row["status"] == "error"}:
                    raise ValueError(f"{stem}: historical rejection list disagrees with saved outputs.")
                before, after, first_after = Counter(), Counter(), {}
                changed_ids = []
                for old in saved:
                    source = by_id[old["report_id"]]
                    new = replay_row(source, old)
                    # Inference metadata remains historical; only normalized
                    # payloads are compared and saved as new code-review output.
                    if any(new.get(k) != old.get(k) for k in ("candidates", "raw_response", "metadata")):
                        raise ValueError("Offline replay modified the saved extraction payload.")
                    summary["unchanged_extraction_payloads"] += 1
                    before[old["status"]] += 1
                    after[new["status"]] += 1
                    reason = rejection_reason(source, new)
                    if reason is not None:
                        first_after[old["report_id"]] = reason
                    if payload(old) != payload(new):
                        changed_ids.append(old["report_id"])
                        changes.append({"run": stem, "report_id": old["report_id"],
                                        "candidates": old["candidates"],
                                        "before": payload(old), "after": payload(new),
                                        "first_rejection_before": before_reasons.get(old["report_id"]),
                                        "first_rejection_after": reason})
                summary["saved_outputs"] += len(saved)
                all_before.update(before)
                all_after.update(after)
                summary["runs"][stem] = {
                    "predictions_sha256": historical["runs"][stem]["predictions_sha256"],
                    "original_metrics_sha256": historical["runs"][stem]["metrics_sha256"],
                    "saved_outputs": len(saved), "changed_report_ids": changed_ids,
                    "before_status_counts": dict(before), "after_status_counts": dict(after),
                    "first_rejections_before": before_reasons, "first_rejections_after": first_after,
                }
    summary["changed_outputs"] = len(changes)
    summary["before_status_counts"], summary["after_status_counts"] = dict(all_before), dict(all_after)
    if summary["saved_outputs"] != 280:
        raise ValueError("Expected all 280 frozen outputs.")
    verify_inputs(directory)
    # All validation and replay finish before output creation. No old artifacts
    # are edited, no credentials are loaded, and no model client is invoked.
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (("summary.json", summary), ("changes.json", changes)):
        with (output / name).open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/scope-evidence-v3")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = replay(args.input, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
    print(f"Replayed {summary['saved_outputs']} outputs; {summary['changed_outputs']} changed; no model requests.")
    print(f"Status counts: {summary['before_status_counts']} -> {summary['after_status_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
