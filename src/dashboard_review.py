"""Explain existing review decisions without changing their eligibility rules."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo


def _quotes(observation: dict) -> list[str]:
    return list(dict.fromkeys(item["value"] for item in observation.get("evidence", [])
                              if item["path"] == "text" and isinstance(item["value"], str)))


def _source_conflict(observation: dict, prediction: dict, field: str) -> str:
    symptom = observation.get("symptom", "symptom")
    quotes = _quotes(observation)
    # Match the candidate to this observation's own evidence, not another
    # symptom or a different dated claim elsewhere in the same submission.
    candidates = [candidate for candidate in prediction.get("candidates", [])
                  if candidate.get("symptom") == symptom and candidate.get("quote") in quotes]
    source_field = "count" if field == "assertion" else field
    questionnaire = list(dict.fromkeys(item["value"] for item in observation.get("evidence", [])
                                      if item["path"].endswith("." + source_field)))
    if source_field == "severity":
        values = {(c.get("severity_value"), c.get("severity_scale_max")) for c in candidates}
        if len(values) == 1 and len(questionnaire) == 1:
            value, scale = next(iter(values))
            if value is not None and scale is not None and questionnaire[0] is not None:
                return (f"{symptom.capitalize()} severity: text reports {value}/{scale}; "
                        f"questionnaire reports {questionnaire[0]}/5.")
    elif source_field == "count":
        values = {c.get("count") for c in candidates}
        if len(values) == 1 and None not in values and len(questionnaire) == 1 and questionnaire[0] is not None:
            return (f"{symptom.capitalize()} count: text reports {next(iter(values))}; "
                    f"questionnaire reports {questionnaire[0]}.")
    parts = [f'Text: “{quote}”' for quote in quotes]
    parts.extend(f"Questionnaire {source_field}: {value}" for value in questionnaire)
    return (f"{symptom.capitalize()} {field}: sources disagree. " + "; ".join(parts)).strip()


def _local_submission(report: dict) -> str:
    value = datetime.fromisoformat(report["reported_at"])
    if report.get("patient_timezone"):
        value = value.astimezone(ZoneInfo(report["patient_timezone"]))
    return value.strftime("%H:%M")


def _impact(review: dict, observation: dict, daily: dict | None) -> str:
    field, symptom = review["field"], observation.get("symptom")
    if field == "event_date":
        if review["reason"] == "outside_followup":
            return "Observation falls outside the displayed follow-up period."
        if observation.get("assertion") == "hypothetical":
            return "Hypothetical symptom is excluded from episode totals; no date is assigned."
        return "This observation is not assigned to a daily statistic."
    if field == "correction":
        return "Replacement not applied; original and replacement records are retained."
    if field == "report":
        return "This report supplies no usable symptom values; the submission day needs review."
    if daily and (field in {"count", "count_scope"} or field == "assertion" and symptom == "vomiting"):
        if daily.get("count_status") == "review":
            return "Daily vomiting count excluded pending review."
        if daily.get("count_status") == "usable":
            return (f"A supported daily vomiting count of {daily['vomiting_count']} remains usable; "
                    "this flagged value adds no extra episodes.")
        return "No usable daily vomiting count is available."
    if daily and field == "severity" and symptom in {"nausea", "vomiting"}:
        status_field = "nausea_status" if symptom == "nausea" else "vomiting_severity_status"
        value_field = f"{symptom}_severity"
        if daily.get(status_field) == "usable":
            return (f"Daily {symptom} severity remains usable ({daily[value_field]}/5) "
                    "from supported evidence.")
        result = f"Daily {symptom} severity excluded pending review."
        if daily.get("count_status") == "usable":
            result += f" Daily vomiting count remains usable ({daily['vomiting_count']})."
        return result
    return "This field remains flagged for review; consult the linked source."


def review_details(data: dict) -> list[dict]:
    """Return copied review rows with detail, impact, and related source links.

    This is a display adapter. Stored diagnostics, source values, and derived
    counts remain untouched; no new conflict or eligibility decision is made.
    """
    reports = {row["report_id"]: row for row in data.get("reports", [])}
    predictions = {row["report_id"]: row for row in data.get("predictions", [])}
    daily = {(row["patient_id"], row["event_date"]): row for row in data.get("daily", [])}
    effective = set(data.get("effective_report_ids", reports))
    result = []
    for original in data.get("review", []):
        row = deepcopy(original)
        report = reports.get(row["report_id"], {})
        prediction = predictions.get(row["report_id"], {})
        observation = next((o for o in prediction.get("observations", [])
                            if o["observation_id"] == row.get("observation_id")), {})
        reason, field = row["reason"], row["field"]
        source_ids = [row["report_id"]]
        quotes = _quotes(observation)
        evidence = " ".join(f'Source: “{quote}”' for quote in quotes)
        if reason in {"conflicting_sources", "daily_count_conflict"}:
            detail = _source_conflict(observation, prediction, field)
        elif reason in {"decreasing_or_conflicting_cumulative_count", "decreasing_or_conflicting_daily_severity"}:
            related = []
            for rid, other in reports.items():
                if rid not in effective or other["patient_id"] != row["patient_id"]:
                    continue
                for value in predictions.get(rid, {}).get("observations", []):
                    if (value.get("event_date") == row.get("event_date")
                            and value.get("symptom") == observation.get("symptom")
                            and (value.get("assertion") != "hypothetical" if field == "count"
                                 else value.get("assertion") == "present")
                            and (field != "count" or value.get("count_scope") == "day_to_date")
                            and value.get(field) is not None):
                        related.append((other, value))
            related.sort(key=lambda pair: (datetime.fromisoformat(pair[0]["reported_at"]), pair[0]["report_id"]))
            source_ids = list(dict.fromkeys([r["report_id"] for r, _ in related] + source_ids))
            scope = "cumulative count" if field == "count" else "worst-so-far severity"
            detail = f"Daily {observation.get('symptom', 'symptom')} {scope} decreases or conflicts: "
            detail += "; ".join(f"{value[field]}{'/5' if field == 'severity' else ''} "
                                f"(submitted at {_local_submission(r)} in {r['report_id']})"
                                for r, value in related) + "."
            if related and all(r.get("supersedes_report_id") is None for r, _ in related):
                detail += " No correction was declared."
        elif reason in {"date_unknown", "date_unallocated", "unsupported_time_range"}:
            detail = "No single calendar date was assigned to this observation. " + evidence
        elif reason in {"count_unknown", "latest_daily_count_unresolved"}:
            detail = ("The latest daily update does not establish a single usable vomiting count. "
                      if reason.startswith("latest_") else "No exact vomiting count is available. ")
            if evidence:
                detail += evidence
            elif any(answer.get("symptom") == observation.get("symptom")
                     and answer.get("event_date") == observation.get("event_date")
                     and answer.get("count") is None
                     for answer in report.get("questionnaire_answers", [])):
                detail += "The questionnaire provides no numerical count."
        elif reason == "unresolved_count_relationship":
            scope = observation.get("count_scope") or "unspecified"
            count = observation.get("count")
            detail = (f"The reported {scope} count ({count if count is not None else 'unknown'}) "
                      "is not an established daily total; overlap with other reports is unresolved. " + evidence)
        else:
            descriptions = {
                "outside_followup": "The symptom date lies outside the patient's follow-up period.",
                "snapshot_endpoint_unresolved": "The cumulative report's cutoff time cannot be established.",
                "conflicting_completed_totals": "Completed-day totals disagree or include an unknown count.",
                "completed_total_below_reported_count": "The completed-day total is below another reported count.",
                "reported_occurrence_conflicts_with_zero": "A reported vomiting occurrence conflicts with a daily count of zero.",
                "partial_count_exceeds_daily_count": "An event or interval count exceeds the selected cumulative daily count.",
                "severity_context_unknown": "The severity rating does not identify the required daily reporting context.",
                "unsupported_severity_context": "The severity rating does not describe the required worst-so-far daily context.",
                "extraction_failed": "Processing failed; this report has no usable extracted observations.",
                "missing_extraction": "No extraction result is available for this report.",
                "incomplete_replacement": "The replacement omits an existing symptom/date context or required value.",
                "branching_correction": "Multiple replacements target the same report.",
                "failed_replacement": "The replacement report could not be processed.",
                "correction_target_not_effective": "The report being replaced is not the current record.",
                "correction_target_not_comparable": "The original report has no comparable successful extraction.",
            }
            detail = descriptions.get(reason, f"Review required: {reason.replace('_', ' ')}.")
            if evidence:
                detail += " " + evidence
        if field == "correction" and report.get("supersedes_report_id"):
            source_ids.append(report["supersedes_report_id"])
        row.update(detail=detail.strip(), impact=_impact(row, observation, daily.get((row["patient_id"], row.get("event_date")))),
                   source_report_ids=list(dict.fromkeys(source_ids)))
        result.append(row)
    return result
