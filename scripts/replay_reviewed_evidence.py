"""Apply an explicitly reviewed evidence-only exception to saved output, offline."""

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.normalization import normalize_report
from src.pipeline import _code_digest, _digest, read_jsonl, validate_predictions
from src.schema import validate_sources


def reviewed_replay(source, saved, review):
    """Restore only a reviewed quote span; never repair semantic field values.

    Hashes bind the review to this exact source and candidate. Literal checks
    establish provenance, not semantic equivalence: the latter is an explicit
    source-review decision recorded in the review file.
    """
    if source["report_id"] != saved["report_id"] or review["report_id"] != source["report_id"]:
        raise ValueError("Review report does not match the source and prediction.")
    if review["source_sha256"] != _digest(source):
        raise ValueError("Review source hash is stale.")
    if saved["status"] != "ok" and saved.get("error_code") != "normalization_error":
        raise ValueError("An evidence review cannot repair an extraction failure.")
    matches = [i for i, c in enumerate(saved["candidates"]) if _digest(c) == review["candidate_sha256"]]
    if len(matches) != 1:
        raise ValueError("Review must identify exactly one unchanged candidate.")
    index = matches[0]
    original = saved["candidates"][index]
    fragments = review["original_fragments"]
    span = review["accepted_source_span"]
    if not review["reason"].strip() or not fragments or " ".join(fragments) != original["quote"]:
        raise ValueError("Review must explain and preserve the original quoted fragments.")
    if not span or span not in source["text"]:
        raise ValueError("Accepted evidence must be one exact continuous source span.")
    end = 0
    for fragment in fragments:
        start = span.find(fragment, end)
        if not fragment or start < 0:
            raise ValueError("Original fragments must occur in their original order.")
        end = start + len(fragment)
    working = copy.deepcopy(saved["candidates"])
    working[index]["quote"] = span
    result = copy.deepcopy(saved)
    result["observations"] = normalize_report(source, working)
    result.update(status="ok", error=None, error_code=None)
    result["evidence_review"] = {
        "kind": "review_assisted_evidence_only_replay", "model_requests": 0,
        "review_sha256": _digest(review), "review": review,
        "normalization_runtime_sha256": _code_digest(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "interpretation": "Raw candidates, response and extraction metadata are unchanged. Only a working quote span was restored from source for normalization after semantic review.",
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = validate_sources(read_jsonl(args.source))
    saved = validate_predictions(sources, read_jsonl(args.predictions))
    review = json.loads(args.review.read_text())
    by_id = {s["report_id"]: s for s in sources}
    if sum(r["report_id"] == review["report_id"] for r in saved) != 1:
        raise ValueError("Expected exactly one reviewed report in saved predictions.")
    rows = [reviewed_replay(by_id[r["report_id"]], r, review)
            if r["report_id"] == review["report_id"] else r for r in saved]
    validate_predictions(sources, rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Saved {len(rows)} reports; one evidence review applied; zero model requests.")


if __name__ == "__main__":
    main()
