"""Freeze, run, and score the bounded scope/evidence prompt comparison."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation import evaluate_predictions
from src.experiment import file_hash, run as run_frozen, verify_manifest, verify_run_metadata
from src.pipeline import _digest, read_jsonl, validate_fixtures, validate_predictions
from src.schema import validate_sources


GROUPS = {
    "regression": [("data/raw/reports.jsonl", "data/gold/expected.jsonl"),
                   ("data/dev/reports.jsonl", "data/dev/expected.jsonl"),
                   ("data/heldout/reports.jsonl", "data/heldout/expected.jsonl")],
    "heldout_v3": [("data/heldout_v3/reports.jsonl", "data/heldout_v3/expected.jsonl")],
}
PROMPTS = {"v1": "prompts/extraction_v1.txt", "v3": "prompts/extraction_v3.txt"}
ROLES = {"regression": "known_regression_data", "heldout_v3": "fresh_synthetic_validation"}
MODEL = "gpt-5.4-mini-2026-03-17"
EXPERIMENT = "scope-evidence-v3"
DIAGNOSTIC_FIELDS = {"time_text", "date_basis"}


def save(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def sources_for(manifest: dict, split: str) -> list[dict]:
    return validate_sources([row for source, _ in manifest["groups"][split]
                             for row in read_jsonl(ROOT / source)])


def freeze(directory: Path) -> None:
    """Validate the authored references, then freeze runtime and all inputs."""
    if (directory / "manifest.json").exists():
        raise ValueError("A frozen manifest already exists; choose a new directory.")
    sources_by_split = {}
    for split, paths in GROUPS.items():
        sources = validate_sources([row for source, _ in paths for row in read_jsonl(ROOT / source)])
        validate_fixtures(sources, [row for _, reference in paths for row in read_jsonl(ROOT / reference)])
        if len(sources) != (50 if split == "regression" else 20):
            raise ValueError(f"Unexpected source count for {split}.")
        sources_by_split[split] = sources
    for field in ("report_id", "patient_id", "text"):
        if ({row[field] for row in sources_by_split["regression"]}
                & {row[field] for row in sources_by_split["heldout_v3"]}):
            raise ValueError(f"Cross-split duplicate {field}; review before inference.")
    for folder in ("dev", "heldout", "heldout_v3"):
        cases = json.loads((ROOT / f"data/{folder}/cases.json").read_text())
        ids = [row["report_id"] for row in cases]
        actual = {row["report_id"] for row in read_jsonl(ROOT / f"data/{folder}/reports.jsonl")}
        if len(ids) != len(set(ids)) or set(ids) != actual:
            raise ValueError(f"Case manifest does not match {folder} reports.")
    paths = {path for groups in GROUPS.values() for pair in groups for path in pair}
    paths.update(PROMPTS.values())
    for folder in ("dev", "heldout", "heldout_v3"):
        paths.update({f"data/{folder}/cases.json", f"data/{folder}/review.md"})
    paths.update({"docs/prompt_v3_experiment.md", "requirements.txt", "scripts/run_prompt_v3.py"})
    paths.update(str(path.relative_to(ROOT)) for path in (ROOT / "src").glob("*.py"))
    manifest = {
        "experiment": EXPERIMENT, "frozen_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL, "groups": GROUPS, "prompts": PROMPTS,
        "repeats": {split: 2 for split in GROUPS}, "reference_roles": ROLES,
        "planned_requests": 280,
        "order": "Alternate prompt order by report index and round; preserve source order",
        "files": {path: file_hash(ROOT / path) for path in sorted(paths)},
    }
    directory.mkdir(parents=True, exist_ok=True)
    save(directory / "manifest.json", manifest)
    print("Frozen 50 known regression and 20 fresh synthetic reports; 280 planned requests.")


def checked_manifest(directory: Path) -> dict:
    manifest = verify_manifest(directory)
    if (manifest.get("experiment") != EXPERIMENT or manifest.get("model") != MODEL
            or manifest.get("prompts") != PROMPTS
            or manifest.get("groups") != json.loads(json.dumps(GROUPS))
            or manifest.get("repeats") != {split: 2 for split in GROUPS}
            or manifest.get("reference_roles") != ROLES
            or manifest.get("planned_requests") != 280):
        raise ValueError("Manifest does not describe the bounded v3 comparison.")
    return manifest


def run(directory: Path, split: str) -> int:
    checked_manifest(directory)
    # The existing runner is manifest-driven; reuse its exact client settings,
    # alternating order, failure recording, and no-retry/no-overwrite behavior.
    return run_frozen(directory, split)


def material_mismatches(metrics: dict, report_id: str) -> list[dict]:
    result = []
    for mismatch in metrics["mismatches"]:
        if mismatch["report_id"] != report_id:
            continue
        if mismatch["kind"] == "field" and mismatch["field"] in DIAGNOSTIC_FIELDS:
            continue
        value = dict(mismatch)
        if value["kind"] == "extraction_check":
            value["differences"] = [d for d in value["differences"] if d["field"] not in DIAGNOSTIC_FIELDS]
            if not value["differences"]:
                continue
        result.append(value)
    return result


def paired_reports(sources: list[dict], metrics: dict[str, dict], rows: dict[str, list[dict]]) -> list[dict]:
    """Expose paired errors for manual review, never automatically promote a prompt."""
    indexed = {label: {row["report_id"]: row for row in values} for label, values in rows.items()}
    result = []
    for source in sources:
        report_id = source["report_id"]
        problems = {label: material_mismatches(metrics[label], report_id) for label in PROMPTS}
        if problems["v1"] == problems["v3"]:
            classification = "unchanged_errors" if problems["v1"] else "no_material_mismatches"
        elif not problems["v3"]:
            classification = "resolved_errors"
        elif not problems["v1"]:
            classification = "new_errors"
        else:
            classification = "changed_errors_requires_review"
        result.append({
            "report_id": report_id, "classification": classification,
            "status": {label: indexed[label].get(report_id, {}).get("status", "missing") for label in PROMPTS},
            "error_code": {label: indexed[label].get(report_id, {}).get("error_code") for label in PROMPTS},
            "material_mismatches": problems,
        })
    return result


def score(directory: Path, split: str) -> None:
    """Read saved outputs and references only; no credential loading or requests."""
    manifest = checked_manifest(directory)
    sources = sources_for(manifest, split)
    gold = validate_fixtures(sources, [row for _, path in manifest["groups"][split]
                                      for row in read_jsonl(ROOT / path)])
    outputs = {}
    for repeat in range(1, manifest["repeats"][split] + 1):
        metrics_by_label, rows_by_label = {}, {}
        for label in manifest["prompts"]:
            stem = f"{split}-{label}-r{repeat}"
            path = directory / f"{stem}.predictions.jsonl"
            rows = read_jsonl(path) if path.read_text().strip() else []
            predictions = validate_predictions(sources, rows)
            verify_run_metadata(directory, manifest, sources, predictions, split, repeat, label)
            metrics = evaluate_predictions(sources, gold, predictions)
            metrics["reference_role"] = manifest["reference_roles"][split]
            metrics["provenance"] = {
                "manifest_sha256": file_hash(directory / "manifest.json"),
                "predictions_sha256": file_hash(path), "source_sha256": _digest(sources),
                "gold_sha256": _digest(gold), "split": split, "repeat": repeat,
            }
            outputs[f"{stem}.metrics.json"] = metrics
            metrics_by_label[label], rows_by_label[label] = metrics, predictions
        outputs[f"{split}-r{repeat}.paired.json"] = {
            "reference_role": manifest["reference_roles"][split],
            "interpretation": "Diagnostic mismatches in time_text and date_basis are excluded here; full metrics retain them. Matching ambiguity and mixed changes require manual review. No automatic adoption decision.",
            "manifest_sha256": file_hash(directory / "manifest.json"), "repeat": repeat,
            "reports": paired_reports(sources, metrics_by_label, rows_by_label),
        }
    if any((directory / name).exists() for name in outputs):
        raise ValueError("A score output already exists; choose a new review directory.")
    for name, value in outputs.items():
        save(directory / name, value)
        if name.endswith(".metrics.json"):
            print(json.dumps({"run": name, "completion": value["report_completion"],
                              "scope_known": value["fields"]["count_scope"]["reference_known"],
                              "count_known": value["fields"]["count"]["reference_known"]}))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "run", "score"))
    parser.add_argument("--directory", type=Path, default=ROOT / "results/scope-evidence-v3")
    parser.add_argument("--split", choices=tuple(GROUPS), default="regression")
    args = parser.parse_args(argv)
    try:
        if args.command == "freeze":
            freeze(args.directory)
        elif args.command == "run":
            return run(args.directory, args.split)
        else:
            score(args.directory, args.split)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
