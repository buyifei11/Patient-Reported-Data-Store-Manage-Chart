"""Explicit extraction and evaluation commands with no gold-to-model path."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

from pydantic import ValidationError

from src.evaluation import evaluate_predictions
from src.llm import ExtractionError, PROMPT_PATH, extract_candidates as extract_local
from src.normalization import NormalizationError, normalize_report
from src.schema import CandidateBatch, GoldRecord, NormalizedObservation, validate_sources


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{number}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected an object at {path}:{number}")
            rows.append(row)
    if not rows:
        raise ValueError(f"No records in {path}")
    return rows


def load_settings(path: Path = ROOT / ".env") -> dict[str, str]:
    """Read only KEY=VALUE entries; never execute shell code or expand values.

    Environment variables take precedence. Comments must use separate lines.
    Matching single or double quotes surrounding a value are optional.
    """
    settings = {}
    allowed = {"OPENAI_API_KEY", "OPENAI_MODEL"}
    if path.exists():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if not separator or key not in allowed:
                raise ValueError(f"Unsupported configuration entry on .env line {number}")
            if value.startswith(("'", '"')):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError(f"Unclosed quote on .env line {number}")
                value = value[1:-1]
            settings[key] = value
    settings.update({key: os.environ[key] for key in allowed if key in os.environ})
    return settings


def validate_fixtures(sources: list[dict], gold: list[dict]) -> list[dict]:
    validated = [GoldRecord.model_validate(row).model_dump(mode="json") for row in gold]
    # With no predictions, this performs linkage/provenance checks only.
    # These all-missing scores are deliberately not presented as a model run.
    evaluate_predictions(sources, validated, [])
    return validated


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _code_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted((ROOT / "src").glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def validate_predictions(sources: list[dict], rows: list[dict]) -> list[dict]:
    """Check saved payloads before evaluation; do not trust a success label."""
    by_id = {source["report_id"]: source for source in sources}
    for row in rows:
        report_id = row.get("report_id")
        if not isinstance(report_id, str) or report_id not in by_id:
            raise ValueError("Every prediction must reference an existing source report.")
        if row.get("status") not in {"ok", "error"}:
            raise ValueError(f"{report_id}: prediction status must be ok or error.")
        CandidateBatch.model_validate({"candidates": row.get("candidates")})
        observations = row.get("observations")
        if not isinstance(observations, list):
            raise ValueError(f"{report_id}: observations must be a list.")
        for observation in observations:
            NormalizedObservation.model_validate(observation)
        metadata = row.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError(f"{report_id}: metadata must be an object.")
        recorded_hash = metadata.get("source_sha256")
        if recorded_hash is not None and recorded_hash != _digest(by_id[report_id]):
            raise ValueError(f"{report_id}: prediction was generated from a different source report.")
    return rows


def process_report(report: dict, extractor, metadata: dict) -> dict:
    """Preserve model output and distinguish a failed report from an empty result."""
    started = time.perf_counter()
    result = {
        "report_id": report["report_id"],
        "status": "error",
        "candidates": [],
        "observations": [],
        "error": None,
        "error_code": None,
        "raw_response": None,
        "metadata": {**metadata, "source_sha256": _digest(report)},
    }
    try:
        extracted = extractor(report["text"])
        result["candidates"] = extracted["candidates"]
        result["raw_response"] = extracted["raw_response"]
        result["metadata"].update(extracted["metadata"])
        result["observations"] = normalize_report(report, result["candidates"])
        result["status"] = "ok"
    except ExtractionError as exc:
        result["error"], result["error_code"] = str(exc), exc.code
        result["raw_response"] = exc.raw_response
    except (NormalizationError, ValidationError, ValueError):
        # Do not dump source values through exception representations.
        result["error"] = "Candidates failed provenance or normalization checks; inspect the saved candidates."
        result["error_code"] = "normalization_error"
    result["metadata"]["elapsed_seconds"] = round(time.perf_counter() - started, 4)
    return result


def _extract(args, sources: list[dict]) -> int:
    # Check readability before creating output; clients read prompt bytes once per request.
    with (args.prompt_file or PROMPT_PATH).open("rb"):
        pass
    settings = load_settings()
    if args.provider == "openai":
        from src.openai_client import extract_candidates as extract_cloud

        model = args.model or settings.get("OPENAI_MODEL")
        key = settings.get("OPENAI_API_KEY", "")
        if not key.strip():
            raise ValueError("OPENAI_API_KEY is missing. Configure it locally in .env or the environment; never paste it into logs.")
        if not model:
            raise ValueError("Choose --model or set OPENAI_MODEL in .env.")
        extractor = lambda text: extract_cloud(text, model=model, api_key=key, timeout=args.timeout,
                                               prompt_path=args.prompt_file)
    else:
        model = args.model
        if not model:
            raise ValueError("The local adapter requires an explicit --model; no model is selected automatically.")
        extractor = lambda text: extract_local(text, model=model, base_url=args.base_url, timeout=args.timeout,
                                               prompt_path=args.prompt_file)
    selected = sources[:args.limit] if args.limit is not None else sources
    metadata = {
        "backend": args.provider,
        "requested_model": model,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "code_sha256": _code_digest(),
        "source_dataset_sha256": _digest(sources),
        "selected_report_count": len(selected),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    failures = 0
    # Exclusive creation protects previous run artifacts and original datasets.
    with args.output.open("x", encoding="utf-8") as handle:
        for number, report in enumerate(selected, 1):
            result = process_report(report, extractor, metadata)
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            handle.flush()
            failures += result["status"] != "ok"
            print(f"[{number}/{len(selected)}] {report['report_id']}: {result['status']}", flush=True)
            if result["error_code"] in {"authentication_error", "http_error", "network_error", "invalid_config"}:
                print("Stopped after a service/configuration failure; remaining reports were not requested.", flush=True)
                break
    print(f"Saved {number} reports to {args.output}; {failures} failed.")
    return 1 if failures else 0


def _positive_int(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("Must be a positive integer")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate source and reference fixtures without a model")
    extract = commands.add_parser("extract", help="Extract source text, then normalize; never reads gold")
    evaluate = commands.add_parser("evaluate", help="Compare a saved run with reference answers")
    for command in (validate, extract, evaluate):
        command.add_argument("--source", type=Path, default=ROOT / "data/raw/reports.jsonl")
    for command in (validate, evaluate):
        command.add_argument("--gold", type=Path, default=ROOT / "data/gold/expected.jsonl")
    extract.add_argument("--provider", choices=("openai", "ollama"), required=True)
    extract.add_argument("--model", help="Explicit model ID; OpenAI may also use OPENAI_MODEL from .env")
    extract.add_argument("--prompt-file", type=Path, default=None, help="Extraction prompt file; defaults to prompts/extraction.txt")
    extract.add_argument("--base-url", default="http://127.0.0.1:11434", help="Local Ollama origin only")
    extract.add_argument("--timeout", type=float, default=120)
    extract.add_argument("--limit", type=_positive_int)
    extract.add_argument("--output", type=Path, required=True, help="New JSONL file; existing files are never overwritten")
    evaluate.add_argument("--predictions", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True, help="New JSON metrics file")
    args = parser.parse_args(argv)
    try:
        sources = validate_sources(read_jsonl(args.source))
        if args.command == "extract":
            return _extract(args, sources)
        gold = validate_fixtures(sources, read_jsonl(args.gold))
        if args.command == "validate":
            print(f"Validated {len(sources)} reports, {sum(len(g['observations']) for g in gold)} observations, "
                  f"and {sum(len(g['extraction_checks']) for g in gold)} extraction checks.")
            return 0
        predictions = validate_predictions(sources, read_jsonl(args.predictions))
        metrics = evaluate_predictions(sources, gold, predictions)
        metrics["provenance"] = {
            "source_dataset_sha256": _digest(sources),
            "gold_dataset_sha256": _digest(gold),
            "predictions_file_sha256": hashlib.sha256(args.predictions.read_bytes()).hexdigest(),
            "evaluation_scope": "Development fixtures; not held-out or clinical validation",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print(json.dumps({key: metrics[key] for key in ("report_completion", "observation_detection", "extraction_checks")}, indent=2))
        print(f"Full field metrics and mismatches: {args.output}")
        return 0
    except ValidationError:
        parser.exit(2, "Input schema validation failed; check the documented source and gold contracts.\n")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
