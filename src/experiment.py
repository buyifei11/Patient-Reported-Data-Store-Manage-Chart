"""A bounded paired experiment; frozen inputs and separate saved-output scoring."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from src.evaluation import evaluate_predictions
from src.openai_client import extract_candidates
from src.pipeline import (ROOT, _code_digest, _digest, load_settings, process_report,
                          read_jsonl, validate_fixtures, validate_predictions)
from src.schema import validate_sources


GROUPS = {
    "development": [("data/raw/reports.jsonl", "data/gold/expected.jsonl"),
                    ("data/dev/reports.jsonl", "data/dev/expected.jsonl")],
    "heldout": [("data/heldout/reports.jsonl", "data/heldout/expected.jsonl")],
}
PROMPTS = {"v1": "prompts/extraction_v1.txt", "v2": "prompts/extraction_v2.txt"}
REPEATS = {"development": 1, "heldout": 2}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _sources(manifest: dict, split: str) -> list[dict]:
    return validate_sources([row for source, _ in manifest["groups"][split]
                             for row in read_jsonl(ROOT / source)])


def freeze(directory: Path) -> None:
    """Preflight all authored references, then bind the experiment to file hashes."""
    sources_by_split = {}
    for split, paths in GROUPS.items():
        sources = validate_sources([row for source, _ in paths for row in read_jsonl(ROOT / source)])
        gold = [row for _, reference in paths for row in read_jsonl(ROOT / reference)]
        validate_fixtures(sources, gold)
        expected = 30 if split == "development" else 20
        if len(sources) != expected:
            raise ValueError(f"Expected {expected} {split} reports.")
        sources_by_split[split] = sources
    development = sources_by_split["development"]
    heldout = sources_by_split["heldout"]
    for field in ("report_id", "patient_id", "text"):
        overlap = {row[field] for row in development} & {row[field] for row in heldout}
        if overlap:
            raise ValueError(f"Cross-split duplicate {field}; review the split before inference.")
    for split in ("dev", "heldout"):
        cases = json.loads((ROOT / f"data/{split}/cases.json").read_text())
        ids = [row["report_id"] for row in cases]
        actual = {row["report_id"] for row in read_jsonl(ROOT / f"data/{split}/reports.jsonl")}
        if len(ids) != len(set(ids)) or set(ids) != actual:
            raise ValueError(f"Case manifest does not match {split} reports.")
    paths = {path for groups in GROUPS.values() for pair in groups for path in pair}
    paths.update(PROMPTS.values())
    paths.update({"data/dev/cases.json", "data/heldout/cases.json", "docs/prompt_experiment.md",
                  "data/dev/review.md", "data/heldout/review.md", "run_experiment.py", "requirements.txt"})
    paths.update(str(path.relative_to(ROOT)) for path in (ROOT / "src").glob("*.py"))
    manifest = {
        "experiment": "temporal-prompt-v2", "frozen_at": datetime.now(timezone.utc).isoformat(),
        "model": "gpt-5.4-mini-2026-03-17", "groups": GROUPS, "prompts": PROMPTS,
        "repeats": REPEATS, "planned_requests": 140,
        "order": "Alternate prompt order by report index and round; preserve source order",
        "files": {path: file_hash(ROOT / path) for path in sorted(paths)},
    }
    directory.mkdir(parents=True, exist_ok=True)
    _save(directory / "manifest.json", manifest)
    print("Frozen 30 development and 20 held-out reports, two prompts, and runtime code.")


def verify_manifest(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text())
    for relative, expected in manifest["files"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or file_hash(path) != expected:
            raise ValueError(f"Frozen input changed: {relative}. Do not silently alter this experiment.")
    return manifest


def run(directory: Path, split: str) -> int:
    """Read source reports only; gold is accessed by freeze/score, not this phase."""
    manifest = verify_manifest(directory)
    sources = _sources(manifest, split)
    api_key = load_settings().get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("Configure OPENAI_API_KEY locally before running inference.")
    paths = {(repeat, label): directory / f"{split}-{label}-r{repeat}.predictions.jsonl"
             for repeat in range(1, manifest["repeats"][split] + 1) for label in manifest["prompts"]}
    if any(path.exists() for path in paths.values()):
        raise ValueError("A run output already exists; results cannot be overwritten or selectively retried.")
    metadata = {
        "backend": "openai", "requested_model": manifest["model"],
        "experiment": manifest["experiment"], "split": split,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": file_hash(directory / "manifest.json"),
        "source_dataset_sha256": _digest(sources), "code_sha256": _code_digest(),
    }
    failures = 0
    with ExitStack() as stack:
        handles = {key: stack.enter_context(path.open("x", encoding="utf-8")) for key, path in paths.items()}
        for repeat in range(1, manifest["repeats"][split] + 1):
            for index, source in enumerate(sources):
                labels = list(manifest["prompts"])
                if (index + repeat) % 2:
                    labels.reverse()
                for label in labels:
                    extractor = lambda text: extract_candidates(
                        text, model=manifest["model"], api_key=api_key,
                        prompt_path=ROOT / manifest["prompts"][label], timeout=120,
                    )
                    result = process_report(source, extractor, {
                        **metadata, "repeat": repeat, "prompt_label": label,
                        "prompt_file": Path(manifest["prompts"][label]).name,
                        "prompt_file_sha256": manifest["files"][manifest["prompts"][label]],
                    })
                    failures += result["status"] != "ok"
                    # Keep predictions exact while omitting provider-specific account request IDs.
                    result["metadata"].pop("response_id", None)
                    handle = handles[repeat, label]
                    handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                    handle.flush()
                    print(f"{split} r{repeat} [{index + 1}/{len(sources)}] {source['report_id']} {label}: {result['status']}", flush=True)
                    if result["error_code"] in {"authentication_error", "http_error", "network_error", "invalid_config"}:
                        print("Stopped on service/configuration failure. No retry was attempted.", flush=True)
                        return 1
    verify_manifest(directory)
    return 1 if failures else 0


def verify_run_metadata(directory: Path, manifest: dict, sources: list[dict], predictions: list[dict],
                        split: str, repeat: int, label: str) -> None:
    expected = {
        "backend": "openai", "requested_model": manifest["model"],
        "experiment": manifest["experiment"], "split": split, "repeat": repeat,
        "prompt_label": label, "prompt_file_sha256": manifest["files"][manifest["prompts"][label]],
        "manifest_sha256": file_hash(directory / "manifest.json"),
        "source_dataset_sha256": _digest(sources), "code_sha256": _code_digest(),
    }
    for row in predictions:
        metadata = row.get("metadata", {})
        for field, value in expected.items():
            if type(metadata.get(field)) is not type(value) or metadata[field] != value:
                raise ValueError(f"{row.get('report_id')}: run metadata mismatch for {field}.")
        if row["status"] == "ok" or row.get("error_code") == "normalization_error":
            if metadata.get("returned_model") != manifest["model"]:
                raise ValueError(f"{row['report_id']}: response did not identify the pinned model.")


def score(directory: Path, split: str) -> None:
    """Rescore existing model outputs without reading credentials or making requests."""
    manifest = verify_manifest(directory)
    sources = _sources(manifest, split)
    gold = validate_fixtures(sources, [row for _, path in manifest["groups"][split]
                                      for row in read_jsonl(ROOT / path)])
    for repeat in range(1, manifest["repeats"][split] + 1):
        for label in manifest["prompts"]:
            stem = f"{split}-{label}-r{repeat}"
            path = directory / f"{stem}.predictions.jsonl"
            # Precreated empty files from an interrupted run mean missing reports,
            # not a perfect empty evaluation or a reason to lose the failure record.
            rows = read_jsonl(path) if path.read_text().strip() else []
            predictions = validate_predictions(sources, rows)
            verify_run_metadata(directory, manifest, sources, predictions, split, repeat, label)
            metrics = evaluate_predictions(sources, gold, predictions)
            metrics["reference_role"] = "synthetic_heldout" if split == "heldout" else "development_fixtures"
            metrics["provenance"] = {
                "manifest_sha256": file_hash(directory / "manifest.json"),
                "predictions_sha256": file_hash(path), "source_sha256": _digest(sources),
                "gold_sha256": _digest(gold), "split": split, "repeat": repeat,
            }
            _save(directory / f"{stem}.metrics.json", metrics)
            print(json.dumps({"run": stem, "completion": metrics["report_completion"],
                              "date_known": metrics["fields"]["event_date"]["reference_known"],
                              "assertion": metrics["assertion_accuracy"], "unknown_overfill": metrics["unknown_overfill"]}))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "run", "score"))
    parser.add_argument("--directory", type=Path, default=ROOT / "results/temporal-prompt-v2")
    parser.add_argument("--split", choices=tuple(GROUPS), default="development")
    args = parser.parse_args(argv)
    try:
        if args.command == "freeze":
            freeze(args.directory)
        elif args.command == "run":
            return run(args.directory, args.split)
        else:
            score(args.directory, args.split)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"{exc}\n")
    return 0
