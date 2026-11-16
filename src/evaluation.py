"""Reference-based development metrics, independent of the LLM and its client."""

from __future__ import annotations

import json
from typing import Any


FIELDS = (
    "symptom", "assertion", "count", "count_scope", "severity", "event_date",
    "event_time", "time_text", "date_basis", "medication_relation",
)
_MISSING = object()


def _fraction(correct: int, total: int) -> dict:
    return {"correct": correct, "total": total,
            "accuracy": correct / total if total else None}


def _detection(tp: int, fp: int, fn: int) -> dict:
    return {
        "true_positive": tp, "false_positive": fp, "false_negative": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    }


def _index(records: list[dict], label: str) -> dict[str, dict]:
    result = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"Each {label} record must be an object")
        report_id = record.get("report_id")
        if not isinstance(report_id, str) or not report_id:
            raise ValueError(f"Each {label} record needs a nonempty report_id")
        if report_id in result:
            raise ValueError(f"Duplicate {label} report_id: {report_id}")
        result[report_id] = record
    return result


def _objects(record: dict, key: str) -> list[dict]:
    values = record.get(key)
    if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
        raise ValueError(f"{record['report_id']}: {key} must be a list of objects")
    return values


def _source_value(source: dict, path: str) -> Any:
    value = source
    try:
        for part in path.split("."):
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value
    except (KeyError, IndexError, TypeError, ValueError):
        return _MISSING


def _valid_evidence(source: dict, evidence: dict) -> bool:
    path = evidence.get("path")
    if not isinstance(path, str) or "value" not in evidence:
        return False
    actual, quoted = _source_value(source, path), evidence["value"]
    if path == "text":
        return isinstance(actual, str) and isinstance(quoted, str) and bool(quoted) and quoted in actual
    return actual is not _MISSING and type(actual) is type(quoted) and actual == quoted


def _spans(text: str, quote: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    while True:
        position = text.find(quote, start)
        if position < 0:
            return spans
        spans.append((position, position + len(quote)))
        start = position + 1


def _evidence_score(left: dict, right: dict, source: dict) -> float:
    """Only source provenance enters matching, never the values being graded."""
    best = 0.0
    for a in left.get("evidence", []):
        if not _valid_evidence(source, a):
            continue
        for b in right.get("evidence", []):
            if a["path"] != b.get("path") or not _valid_evidence(source, b):
                continue
            if a["path"] != "text":
                if type(a["value"]) is type(b["value"]) and a["value"] == b["value"]:
                    best = 1.0
                continue
            for start_a, end_a in _spans(source["text"], a["value"]):
                for start_b, end_b in _spans(source["text"], b["value"]):
                    overlap = max(0, min(end_a, end_b) - max(start_a, start_b))
                    best = max(best, 2 * overlap / (end_a - start_a + end_b - start_b))
    return best


def _content_key(observation: dict) -> str:
    # Identical duplicates may share one match; the remaining copies are extras.
    content = {k: v for k, v in observation.items() if k != "observation_id"}
    for key in ("evidence", "issues"):
        if key in content:
            content[key] = sorted(content[key], key=lambda item: json.dumps(item, sort_keys=True))
    return json.dumps(content, sort_keys=True)


def _match_observations(expected: list[dict], actual: list[dict], source: dict) -> tuple[dict, list]:
    matches, ambiguous = {}, []
    symptoms = sorted({o.get("symptom", "") for o in expected + actual})
    for symptom in symptoms:
        refs = {i for i, o in enumerate(expected) if o.get("symptom") == symptom}
        preds = {i for i, o in enumerate(actual) if o.get("symptom") == symptom}
        if len(refs) == len(preds) == 1:
            matches[next(iter(refs))] = next(iter(preds))
            continue
        while refs and preds:
            scores = {(g, p): _evidence_score(expected[g], actual[p], source)
                      for g in refs for p in preds}
            choices = {}
            for g in sorted(refs):
                best = max(scores[g, p] for p in preds)
                options = [p for p in sorted(preds) if scores[g, p] == best and best > 0]
                if options and len({_content_key(actual[p]) for p in options}) == 1:
                    choices[g] = options[0]
            pairs = []
            for g, p in choices.items():
                best = max(scores[other, p] for other in refs)
                rivals = [other for other in refs if scores[other, p] == best]
                if rivals == [g]:
                    pairs.append((g, p))
            if not pairs:
                ambiguous.append({"symptom": symptom, "reference_indexes": sorted(refs),
                                  "prediction_indexes": sorted(preds),
                                  "reason": "No unique source-evidence alignment"})
                break
            for g, p in pairs:
                matches[g] = p
                refs.remove(g)
                preds.remove(p)
    return matches, ambiguous


def _issues(observation: dict) -> set[tuple[str, str]]:
    return {(issue["field"], issue["code"]) for issue in observation.get("issues", [])}


def _issue_objects(issues: set[tuple[str, str]]) -> list[dict]:
    return [{"field": field, "code": code} for field, code in sorted(issues)]


def _equal(left: Any, right: Any) -> bool:
    # Python considers False == 0; JSON/schema semantics must not do so.
    return type(left) is type(right) and left == right


def evaluate_predictions(sources: list[dict], gold: list[dict], predictions: list[dict]) -> dict:
    """Compare normalized observations and pre-reconciliation text candidates.

    Missing/error reports remain in reference denominators. Schema validation is
    the pipeline's responsibility; this function validates record linkage and
    refuses malformed collection envelopes instead of silently dropping them.
    """
    source_map = _index(sources, "source")
    gold_map = _index(gold, "gold")
    prediction_map = _index(predictions, "prediction")
    if source_map.keys() != gold_map.keys():
        raise ValueError("Source and gold report_id sets must match exactly")
    unknown = prediction_map.keys() - source_map.keys()
    if unknown:
        raise ValueError(f"Unknown prediction report_id: {', '.join(sorted(unknown))}")
    for report_id, reference in gold_map.items():
        for observation in _objects(reference, "observations"):
            if any(field not in observation for field in FIELDS):
                raise ValueError(f"{report_id}: gold observation is missing an evaluated field")
            if not all(_valid_evidence(source_map[report_id], item)
                       for item in observation.get("evidence", [])):
                raise ValueError(f"{report_id}: gold evidence does not match its source")
        for check in _objects(reference, "extraction_checks"):
            if not _valid_evidence(source_map[report_id], check.get("source", {})):
                raise ValueError(f"{report_id}: extraction-check evidence does not match its source")
            if not isinstance(check.get("expected_fields"), dict) or not check["expected_fields"]:
                raise ValueError(f"{report_id}: extraction check needs expected_fields")
    for prediction in prediction_map.values():
        if prediction.get("status") not in {"ok", "error"}:
            raise ValueError(f"{prediction['report_id']}: status must be ok or error")
        _objects(prediction, "observations")
        _objects(prediction, "candidates")

    counts = {"total": len(sources), "ok": 0, "error": 0, "missing": 0}
    field_counts = {field: {"known_correct": 0, "known_total": 0, "null_correct": 0,
                            "null_total": 0, "overfilled": 0, "missing_predictions": 0}
                    for field in FIELDS}
    observation_tp = observation_fp = observation_fn = 0
    issue_tp = issue_fp = issue_fn = 0
    check_passed = check_total = 0
    check_fields: dict[str, list[int]] = {}
    mismatches, ambiguous_groups = [], []

    for report_id in sorted(source_map):
        source, reference = source_map[report_id], gold_map[report_id]
        prediction = prediction_map.get(report_id)
        status = prediction["status"] if prediction else "missing"
        counts[status] += 1
        expected = reference["observations"]
        actual = prediction["observations"] if status == "ok" else []
        # A later normalization failure must not erase a completed extraction.
        # The pipeline validates retained candidates before assigning this code.
        extracted = status == "ok" or (
            status == "error" and prediction.get("error_code") == "normalization_error"
        )
        candidates = prediction["candidates"] if extracted else []
        if status != "ok":
            mismatches.append({"report_id": report_id, "kind": "report_failure", "status": status,
                               "error": prediction.get("error") if prediction else None})
        matches, ambiguous = _match_observations(expected, actual, source)
        ambiguous_groups.extend({"report_id": report_id, **item} for item in ambiguous)
        observation_tp += len(matches)
        observation_fp += len(actual) - len(matches)
        observation_fn += len(expected) - len(matches)
        for index, observation in enumerate(expected):
            predicted_index = matches.get(index)
            found = actual[predicted_index] if predicted_index is not None else None
            location = {"report_id": report_id, "reference_index": index,
                        "reference_id": observation.get("observation_id"),
                        "prediction_index": predicted_index}
            if found is None:
                mismatches.append({**location, "kind": "missing_observation",
                                   "symptom": observation["symptom"], "evidence": observation.get("evidence", [])})
            for field in FIELDS:
                truth = observation[field]
                value = found.get(field, _MISSING) if found is not None else _MISSING
                bucket = "null" if truth is None else "known"
                stats = field_counts[field]
                stats[f"{bucket}_total"] += 1
                if value is not _MISSING and _equal(truth, value):
                    stats[f"{bucket}_correct"] += 1
                else:
                    if value is _MISSING:
                        stats["missing_predictions"] += 1
                    if truth is None and value is not _MISSING and value is not None:
                        stats["overfilled"] += 1
                    if found is not None:
                        mismatches.append({**location, "kind": "field", "field": field,
                                           "expected": truth, "predicted": None if value is _MISSING else value,
                                           "prediction_missing": value is _MISSING})
            wanted_issues = _issues(observation)
            actual_issues = _issues(found) if found is not None else set()
            issue_tp += len(wanted_issues & actual_issues)
            issue_fp += len(actual_issues - wanted_issues)
            issue_fn += len(wanted_issues - actual_issues)
            if wanted_issues != actual_issues:
                mismatches.append({**location, "kind": "issues",
                                   "missing": _issue_objects(wanted_issues - actual_issues),
                                   "extra": _issue_objects(actual_issues - wanted_issues)})
        for index, observation in enumerate(actual):
            if index not in matches.values():
                issue_fp += len(_issues(observation))
                mismatches.append({"report_id": report_id, "kind": "extra_observation",
                                   "prediction_index": index, "symptom": observation.get("symptom"),
                                   "evidence": observation.get("evidence", [])})

        for index, check in enumerate(reference["extraction_checks"]):
            check_total += 1
            wanted = check["expected_fields"]
            scores = []
            for candidate_index, candidate in enumerate(candidates):
                if "symptom" in wanted and candidate.get("symptom") != wanted["symptom"]:
                    continue
                score = _evidence_score({"evidence": [check["source"]]},
                                        {"evidence": [{"path": "text", "value": candidate.get("quote")}]}, source)
                if score > 0:
                    scores.append((score, candidate_index))
            best = max((score for score, _ in scores), default=0)
            indexes = [i for score, i in scores if score == best]
            found = None
            if indexes and len({_content_key(candidates[i]) for i in indexes}) == 1:
                found = candidates[indexes[0]]
            differences = []
            for field, truth in wanted.items():
                value = found.get(field, _MISSING) if found is not None else _MISSING
                passed = value is not _MISSING and _equal(truth, value)
                check_fields.setdefault(field, [0, 0])
                check_fields[field][0] += int(passed)
                check_fields[field][1] += 1
                if not passed:
                    differences.append({"field": field, "expected": truth,
                                        "predicted": None if value is _MISSING else value,
                                        "prediction_missing": value is _MISSING})
            if not differences:
                check_passed += 1
            else:
                mismatches.append({"report_id": report_id, "kind": "extraction_check", "check_index": index,
                                   "source": check["source"], "candidate_found": found is not None,
                                   "ambiguous_candidates": found is None and len(indexes) > 1,
                                   "differences": differences})

    fields = {}
    for field, stats in field_counts.items():
        fields[field] = {
            "reference_known": _fraction(stats["known_correct"], stats["known_total"]),
            "reference_null": {**_fraction(stats["null_correct"], stats["null_total"]),
                               "overfilled": stats["overfilled"]},
            "missing_predictions": stats["missing_predictions"],
        }
    counts["rate"] = counts["ok"] / counts["total"] if counts["total"] else None
    null_total = sum(stats["null_total"] for stats in field_counts.values())
    overfilled = sum(stats["overfilled"] for stats in field_counts.values())
    return {
        "evaluation_version": "1.0", "reference_role": "development_fixtures",
        "report_completion": counts,
        "observation_detection": _detection(observation_tp, observation_fp, observation_fn),
        "fields": fields, "assertion_accuracy": fields["assertion"]["reference_known"],
        "unknown_overfill": {"errors": overfilled, "reference_null_fields": null_total,
                             "rate": overfilled / null_total if null_total else None},
        "issue_detection": _detection(issue_tp, issue_fp, issue_fn),
        "extraction_checks": {"passed": check_passed, "total": check_total,
                              "accuracy": check_passed / check_total if check_total else None,
                              "fields": {field: _fraction(*value) for field, value in sorted(check_fields.items())}},
        "matching": {"ambiguous_groups": ambiguous_groups}, "mismatches": mismatches,
    }
