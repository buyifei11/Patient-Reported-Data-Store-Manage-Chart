"""Conservative, query-specific daily aggregation of stored report claims.

Only normalized daily claims supply daily counts. Episode/window observations
remain reviewable source data and are never silently summed into daily totals.
This module reads neither gold answers nor model credentials and mutates no input.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
import re
from zoneinfo import ZoneInfo

from src.schema import NormalizedObservation, validate_sources


def _timestamp(report: dict) -> datetime:
    return datetime.fromisoformat(report["reported_at"])


def _submission_day(report: dict) -> str:
    return _timestamp(report).astimezone(ZoneInfo(report["patient_timezone"])).date().isoformat()


def _context(observation: dict) -> tuple:
    return observation["symptom"], observation["event_date"]


def _has_issue(observation: dict, field: str, code: str | None = None) -> bool:
    return any(issue["field"] == field and (code is None or issue["code"] == code)
               for issue in observation["issues"])


def _complete_replacement(old: list[dict], new: list[dict]) -> bool:
    # Structural omission checks cannot prove author intent. A valid edit action
    # is still required by the source contract; partial edits are not inferred.
    # Changing a symptom's dated context is also routed to review: this MVP
    # cannot distinguish a date correction from silently dropping the old claim.
    previous = Counter(_context(value) for value in old)
    replacement = Counter(_context(value) for value in new)
    if any(replacement[key] < count for key, count in previous.items()):
        return False
    for observation in old:
        compatible = [value for value in new if _context(value) == _context(observation)]
        for field in ("count", "severity"):
            if observation[field] is not None and not any(
                value[field] is not None or _has_issue(value, field)
                or value["assertion"] == "absent" for value in compatible
            ):
                return False
    return True


def _resolve_corrections(reports: list[dict], predictions: dict) -> tuple[set, list]:
    by_id = {report["report_id"]: report for report in reports}
    children = Counter(report["supersedes_report_id"] for report in reports if report["supersedes_report_id"])
    effective = {report["report_id"] for report in reports if report["supersedes_report_id"] is None}
    corrections = []
    for report in sorted(reports, key=lambda value: (_timestamp(value), value["report_id"])):
        target = report["supersedes_report_id"]
        if target is None:
            continue
        current = predictions.get(report["report_id"], {})
        original = predictions.get(target, {})
        reason = None
        if children[target] > 1:
            reason = "branching_correction"
        elif target not in effective:
            reason = "correction_target_not_effective"
        elif current.get("status") != "ok":
            reason = "failed_replacement"
        elif original.get("status") != "ok":
            reason = "correction_target_not_comparable"
        elif not _complete_replacement(original["observations"], current["observations"]):
            reason = "incomplete_replacement"
        if reason is None:
            effective.remove(target)
            effective.add(report["report_id"])
        corrections.append({"report_id": report["report_id"], "target_report_id": target,
                            "status": "rejected" if reason else "applied", "reason": reason})
    return effective, corrections


def _snapshot_time(item: dict) -> datetime | None:
    """Order explicitly timed cumulative cutoffs, never episode timestamps.

    A bounded set of source cutoff phrases supplies a snapshot endpoint for
    comparison only. It does not populate observation.event_time. Untimed claims
    use submission time; an unsupported earlier cutoff is left unresolved.
    Conflicting equal-time claims are never array-ordered.
    """
    report, observation = item["report"], item["observation"]
    source = observation["time_text"] or ""
    marker = r"(?:by|as\s+of|up\s+to|until|through|to)"
    matches = list(re.finditer(rf"\b{marker}\s+(\d{{1,2}}):(\d{{2}})\b", source, re.I))
    if len(matches) > 1:
        return None
    if matches:
        match = matches[0]
        hour, minute = map(int, match.groups())
        # Unqualified 12-hour forms and malformed times are not interpreted.
        suffix = source[match.end():]
        if hour < 24 and minute < 60 and not re.match(r"\s*[ap]\.?m", suffix, re.I):
            value = datetime.combine(date.fromisoformat(observation["event_date"]), time(hour, minute),
                                     ZoneInfo(report["patient_timezone"]))
            if value <= _timestamp(report):
                return value
        # A recognized but future, malformed, or unsupported cutoff cannot
        # silently become the report's current submission endpoint.
        return None
    if re.search(rf"\b{marker}\s+noon\b", source, re.I):
        value = datetime.combine(date.fromisoformat(observation["event_date"]), time(12),
                                 ZoneInfo(report["patient_timezone"]))
        return value if value <= _timestamp(report) else None
    remainder = re.sub(
        rf"\b{marker}\s+(?:now|this\s+(?:submission|report|message)|"
        r"(?:the\s+)?time\s+of\s+this\s+(?:submission|report|message))\b",
        " ", source, flags=re.I,
    )
    if re.search(rf"\b(?:{marker}|earlier|previously)\b", remainder, re.I):
        return None
    return _timestamp(report)


def aggregate(patients: list[dict], reports: list[dict], predictions: list[dict]) -> dict:
    """Return daily rows, review diagnostics, correction decisions, and active IDs.

    Daily count values are reported counts, not complete capture of real events.
    ``count_basis`` distinguishes a completed day from a cumulative partial day.
    A usable numeric field can coexist with a review issue on another field.
    """
    reports = validate_sources(reports)
    by_id = {report["report_id"]: report for report in reports}
    patient_map = {}
    for patient in patients:
        patient_id = patient["patient_id"]
        if patient_id in patient_map:
            raise ValueError("Patient identifiers must be unique.")
        start, end = date.fromisoformat(patient["followup_start"]), date.fromisoformat(patient["followup_end"])
        if start > end:
            raise ValueError("Patient follow-up start must not follow its end.")
        ZoneInfo(patient["patient_timezone"])
        patient_map[patient_id] = patient
    if any(report["patient_id"] not in patient_map for report in reports):
        raise ValueError("Every report must belong to a configured patient.")
    prediction_map = {}
    for prediction in predictions:
        report_id = prediction["report_id"]
        if report_id in prediction_map or report_id not in by_id:
            raise ValueError("Predictions must have unique, known report identifiers.")
        if prediction.get("status") not in {"ok", "error"}:
            raise ValueError("Prediction status must be ok or error.")
        observations = prediction.get("observations")
        if not isinstance(observations, list):
            raise ValueError("Prediction observations must be a list.")
        validated = [NormalizedObservation.model_validate(o).model_dump(mode="json") for o in observations]
        ids = [value["observation_id"] for value in validated]
        if len(ids) != len(set(ids)):
            raise ValueError("Observation identifiers must be unique within a report.")
        prediction_map[report_id] = {**prediction, "observations": validated}

    effective, corrections = _resolve_corrections(reports, prediction_map)
    review = []
    seen_review = set()

    def flag(report: dict, observation: dict | None, field: str, reason: str,
             event_date: str | None = None) -> None:
        value = {"patient_id": report["patient_id"], "report_id": report["report_id"],
                 "observation_id": observation["observation_id"] if observation else None,
                 "event_date": observation["event_date"] if observation else event_date,
                 "field": field, "reason": reason}
        key = tuple(value.values())
        if key not in seen_review:
            seen_review.add(key)
            review.append(value)

    for correction in corrections:
        if correction["reason"]:
            report = by_id[correction["report_id"]]
            flag(report, None, "correction", correction["reason"], _submission_day(report))

    groups = defaultdict(list)
    day_reports = defaultdict(set)
    failed_days = defaultdict(list)
    for report in reports:
        if report["report_id"] not in effective:
            continue
        key = report["patient_id"], _submission_day(report)
        day_reports[key].add(report["report_id"])
        prediction = prediction_map.get(report["report_id"])
        if prediction is None or prediction["status"] != "ok":
            reason = "missing_extraction" if prediction is None else "extraction_failed"
            flag(report, None, "report", reason, key[1])
            failed_days[key].append(report)
            continue
        patient = patient_map[report["patient_id"]]
        for observation in prediction["observations"]:
            for issue in observation["issues"]:
                flag(report, observation, issue["field"], issue["code"])
            event_date = observation["event_date"]
            if event_date is None:
                flag(report, observation, "event_date", "date_unallocated")
                continue
            if not patient["followup_start"] <= event_date <= patient["followup_end"]:
                flag(report, observation, "event_date", "outside_followup")
                continue
            key = report["patient_id"], event_date
            groups[key].append({"report": report, "observation": observation})
            day_reports[key].add(report["report_id"])

    def daily_count(items: list[dict], blocked: bool) -> tuple:
        vomiting = [item for item in items if item["observation"]["symptom"] == "vomiting"
                    and item["observation"]["assertion"] != "hypothetical"]
        daily = [item for item in vomiting if item["observation"]["count_scope"] in {"day_to_date", "day_total"}]
        partial = [item for item in vomiting if item not in daily]
        for item in partial:
            flag(item["report"], item["observation"], "count", "unresolved_count_relationship")
        if blocked:
            return None, None, "review"
        if not daily:
            return None, None, "review" if vomiting else "missing"
        completed = [item for item in daily if item["observation"]["count_scope"] == "day_total"]
        uncertain = [item for item in daily if item["observation"]["assertion"] == "uncertain"
                     or _has_issue(item["observation"], "count", "conflicting_sources")
                     or _has_issue(item["observation"], "assertion", "conflicting_sources")]
        if uncertain:
            for item in uncertain:
                flag(item["report"], item["observation"], "count", "daily_count_conflict")
            return None, None, "review"

        def zero_conflicts(count: int, selected: list[dict]) -> bool:
            # Known occurrence establishes a contradiction with a zero daily
            # result even if its number is unknown or its interval is excluded
            # from summation. Keep the result unknown; do not manufacture one.
            present = [item for item in vomiting if item["observation"]["assertion"] == "present"]
            if count != 0 or not present:
                return False
            for item in present + selected:
                flag(item["report"], item["observation"], "count", "reported_occurrence_conflicts_with_zero")
            return True

        if completed:
            values = {item["observation"]["count"] for item in completed}
            if None in values or len(values) != 1:
                for item in completed:
                    flag(item["report"], item["observation"], "count", "conflicting_completed_totals")
                return None, None, "review"
            count = next(iter(values))
            if zero_conflicts(count, completed):
                return None, None, "review"
            if any(item["observation"]["count"] is not None and item["observation"]["count"] > count
                   for item in daily + partial):
                for item in completed:
                    flag(item["report"], item["observation"], "count", "completed_total_below_reported_count")
                return None, None, "review"
            return count, "day_total", "usable"
        unresolved = [item for item in daily if _snapshot_time(item) is None]
        if unresolved:
            for item in unresolved:
                flag(item["report"], item["observation"], "count", "snapshot_endpoint_unresolved")
            return None, None, "review"
        ordered = sorted(daily, key=lambda item: (_snapshot_time(item), item["report"]["report_id"]))
        peak = None
        latest_time = _snapshot_time(ordered[-1])
        latest = [item for item in ordered if _snapshot_time(item) == latest_time]
        latest_values = {item["observation"]["count"] for item in latest}
        if None in latest_values or len(latest_values) != 1:
            for item in latest:
                flag(item["report"], item["observation"], "count", "latest_daily_count_unresolved")
            return None, None, "review"
        grouped = defaultdict(list)
        for item in ordered:
            grouped[_snapshot_time(item)].append(item)
        for same_time in grouped.values():
            known = {item["observation"]["count"] for item in same_time if item["observation"]["count"] is not None}
            if len(known) > 1 or (known and peak is not None and min(known) < peak):
                for item in same_time:
                    flag(item["report"], item["observation"], "count", "decreasing_or_conflicting_cumulative_count")
                return None, None, "review"
            if known:
                peak = max(known) if peak is None else max(peak, *known)
        count = next(iter(latest_values))
        if zero_conflicts(count, latest):
            return None, None, "review"
        for item in partial:
            if (_timestamp(item["report"]) <= latest_time and item["observation"]["count"] is not None
                    and item["observation"]["count"] > count):
                flag(item["report"], item["observation"], "count", "partial_count_exceeds_daily_count")
                return None, None, "review"
        return count, "day_to_date", "usable"

    def daily_severity(items: list[dict], symptom: str, blocked: bool) -> tuple:
        values = [item for item in items if item["observation"]["symptom"] == symptom]
        if blocked:
            return None, "review"
        conflict = [item for item in values if _has_issue(item["observation"], "severity", "conflicting_sources")]
        if conflict:
            return None, "review"
        eligible = [item for item in values if item["observation"]["assertion"] == "present"
                    and item["observation"]["severity"] is not None]
        if not eligible:
            problematic = any(_has_issue(item["observation"], "severity") for item in values)
            return None, "review" if problematic else "missing"
        groups = defaultdict(list)
        for item in sorted(eligible, key=lambda item: _timestamp(item["report"])):
            groups[_timestamp(item["report"])].append(item)
        peak = None
        for same_time in groups.values():
            known = {item["observation"]["severity"] for item in same_time}
            if len(known) > 1 or (peak is not None and min(known) < peak):
                for item in same_time:
                    flag(item["report"], item["observation"], "severity", "decreasing_or_conflicting_daily_severity")
                return None, "review"
            peak = max(known) if peak is None else max(peak, *known)
        return peak, "usable"

    result = []
    for patient_id, patient in sorted(patient_map.items()):
        day, end = date.fromisoformat(patient["followup_start"]), date.fromisoformat(patient["followup_end"])
        while day <= end:
            key = patient_id, day.isoformat()
            items = groups[key]
            blocked = bool(failed_days[key])
            count, basis, status = daily_count(items, blocked)
            nausea, nausea_status = daily_severity(items, "nausea", blocked)
            vomiting, vomiting_status = daily_severity(items, "vomiting", blocked)
            result.append({"patient_id": patient_id, "event_date": key[1],
                           "week_start": (day - timedelta(days=day.weekday())).isoformat(),
                           "vomiting_count": count, "count_basis": basis, "count_status": status,
                           "nausea_severity": nausea, "nausea_status": nausea_status,
                           "vomiting_severity": vomiting, "vomiting_severity_status": vomiting_status,
                           "report_count": len(day_reports[key]), "source_report_ids": sorted(day_reports[key]),
                           "review_reasons": sorted({row["reason"] for row in review
                                                     if (row["patient_id"], row["event_date"]) == key})})
            day += timedelta(days=1)
    return {"daily": result,
            "review": sorted(review, key=lambda row: (row["patient_id"], row["event_date"] or "",
                                                       row["report_id"], row["observation_id"] or "", row["field"], row["reason"])),
            "corrections": corrections, "effective_report_ids": sorted(effective)}
