"""Resolve source-grounded candidates into per-report observations.

This module does not extract text, read reference answers, apply corrections, or
aggregate reports. A rejected candidate fails the report instead of disappearing.
"""

from __future__ import annotations

import calendar
import json
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from src.schema import CandidateBatch, NormalizedObservation, SourceReport


class NormalizationError(ValueError):
    """A candidate cannot be grounded in its report or violates time rules."""


def _issue(field: str, code: str) -> dict:
    return {"field": field, "code": code}


def _unique(items: list[dict]) -> list[dict]:
    result = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _explicit_date_supported(value: str, quote: str) -> bool:
    """Recognize ISO dates and explicit English month/day/year anchors."""
    if re.search(rf"(?<!\d){re.escape(value)}(?!\d)", quote):
        return True
    parsed = date.fromisoformat(value)
    month = "(?:" + calendar.month_name[parsed.month] + "|" + calendar.month_abbr[parsed.month] + r"\.?)"
    day = rf"0?{parsed.day}(?:st|nd|rd|th)?"
    return bool(re.search(
        rf"\b(?:{month}\s+{day},?\s+{parsed.year}|{day}\s+{month},?\s+{parsed.year})\b",
        quote,
        flags=re.IGNORECASE,
    ))


def _clock_supported(value: str, quote: str) -> bool:
    hour, minute = map(int, value.split(":"))
    pattern = r"(?<!\d)(\d{1,2}):(\d{2})(?:\s*([ap]\.?m\.?))?(?!\w)"
    for match in re.finditer(pattern, quote, flags=re.IGNORECASE):
        source_hour, source_minute = int(match[1]), int(match[2])
        meridiem = match[3]
        if meridiem is not None:
            if not 1 <= source_hour <= 12:
                continue
            source_hour = source_hour % 12 + (12 if meridiem.lower().startswith("p") else 0)
        if (source_hour, source_minute) != (hour, minute):
            continue
        before, after = quote[:match.start()], quote[match.end():]
        approximate_before = re.search(
            r"(?:\b(?:around|about|roughly|approximately|approx\.?|circa|between)|~)\s*(?:at\s*)?$",
            before, re.IGNORECASE,
        )
        approximate_after = re.match(
            r"[\s-]*(?:or\s+so|ish|approximately|roughly|give\s+or\s+take)\b",
            after, re.IGNORECASE,
        )
        if not approximate_before and not approximate_after:
            return True
    return False


def _ground_candidate(candidate: dict, report: dict) -> None:
    quote = candidate["quote"]
    if not quote or quote not in report["text"]:
        raise NormalizationError("Candidate quote must be an exact nonempty source substring.")
    time_text = candidate["time_text"]
    if time_text is not None and (not time_text or time_text not in quote):
        raise NormalizationError("Candidate time_text must be an exact substring of its quote.")
    medication = candidate["medication_relation"]
    if medication is not None and medication["medication"] not in quote:
        raise NormalizationError("Candidate medication label must occur in its quote.")
    reference = candidate["day_reference"]
    if reference == "today" and not re.search(
        r"\b(?:today|tonight|this\s+(?:morning|afternoon|evening))\b", quote, re.IGNORECASE
    ):
        raise NormalizationError("A today reference requires a supported same-day expression.")
    if reference == "yesterday" and not re.search(r"\byesterday\b", quote, re.IGNORECASE):
        raise NormalizationError("A yesterday reference requires an explicit yesterday anchor.")
    if reference == "explicit":
        if not candidate["explicit_date"] or not _explicit_date_supported(candidate["explicit_date"], quote):
            raise NormalizationError("An explicit date requires a matching calendar-date anchor.")
    elif candidate["explicit_date"] is not None:
        raise NormalizationError("Only an explicit day reference may contain explicit_date.")
    if candidate["clock_time"] is not None and not _clock_supported(candidate["clock_time"], quote):
        raise NormalizationError("An exact clock time requires a matching explicit source time.")


def _candidate_observation(candidate: dict, report: dict, local_submission: datetime) -> dict:
    _ground_candidate(candidate, report)
    today = local_submission.date()
    issues = []
    reference = candidate["day_reference"]
    if reference == "today":
        event_date, date_basis = today, "relative_text"
    elif reference == "yesterday":
        event_date, date_basis = today - timedelta(days=1), "relative_text"
    elif reference == "explicit":
        event_date, date_basis = date.fromisoformat(candidate["explicit_date"]), "explicit_text"
    else:
        event_date, date_basis = None, "unknown"
        issues.append(_issue("event_date", "unsupported_time_range" if reference == "multiple_days" else "date_unknown"))

    assertion = candidate["assertion"]
    symptom = candidate["symptom"]
    count = candidate["count"]
    scope = candidate["count_scope"]
    if symptom == "nausea" and (count is not None or scope is not None):
        raise NormalizationError("Nausea does not support episode counts in this schema.")
    if assertion in ("hypothetical", "uncertain") and count is not None:
        raise NormalizationError("Hypothetical or uncertain occurrence cannot supply an observed count.")
    if assertion == "present" and count == 0:
        raise NormalizationError("A present assertion cannot have count zero.")
    if assertion == "absent" and count not in (None, 0):
        raise NormalizationError("An absent assertion cannot have a positive count.")
    if count is not None and scope is None:
        raise NormalizationError("A count requires an identified count scope.")
    if reference == "multiple_days" and scope not in (None, "window"):
        raise NormalizationError("A multi-day count must retain window scope.")
    if scope == "day_total" and (event_date is None or event_date >= today):
        raise NormalizationError("A day_total requires a completed calendar day before submission.")
    if scope == "day_to_date" and event_date != today:
        raise NormalizationError("A day_to_date count must target the local submission day.")
    if assertion in ("present", "absent") and event_date is not None:
        if event_date > today:
            raise NormalizationError("An actual observation cannot be dated after submission.")
        if event_date == today and candidate["clock_time"] is not None:
            if candidate["clock_time"] > local_submission.strftime("%H:%M"):
                raise NormalizationError("An actual observation time cannot be after submission.")
    if symptom == "vomiting":
        if assertion == "absent" and scope is not None:
            count = 0
        elif assertion == "present" and count is None:
            issues.append(_issue("count", "count_unknown"))

    severity = None
    rating = candidate["severity_value"]
    if rating is not None:
        if assertion in ("absent", "hypothetical", "uncertain"):
            raise NormalizationError("A numeric observed severity requires a present assertion.")
        if candidate["severity_scale_max"] != 5 or not 1 <= rating <= 5:
            issues.append(_issue("severity", "unsupported_scale"))
        context = candidate["severity_context"]
        if context in (None, "unknown"):
            issues.append(_issue("severity", "severity_context_unknown"))
        elif context != "worst_today_so_far" or event_date != today:
            issues.append(_issue("severity", "unsupported_severity_context"))
        if not any(issue["field"] == "severity" for issue in issues):
            severity = rating

    return {
        "symptom": symptom,
        "assertion": assertion,
        "count": count,
        "count_scope": scope,
        "severity": severity,
        "event_date": event_date.isoformat() if event_date is not None else None,
        "event_time": candidate["clock_time"],
        "time_text": candidate["time_text"],
        "date_basis": date_basis,
        "medication_relation": candidate["medication_relation"],
        "evidence": [{"path": "text", "value": candidate["quote"]}],
        "issues": issues,
    }


def _questionnaire_observation(answer: dict, index: int) -> dict | None:
    if answer["count"] is None and answer["severity"] is None:
        return None
    prefix = f"questionnaire_answers.{index}."
    fields = ["symptom", "event_date"]
    fields.extend(field for field in ("count", "severity") if answer[field] is not None)
    return {
        "symptom": answer["symptom"],
        "assertion": "absent" if answer["count"] == 0 else "present",
        "count": answer["count"],
        "count_scope": "day_to_date" if answer["symptom"] == "vomiting" else None,
        "severity": answer["severity"],
        "event_date": answer["event_date"],
        "event_time": None,
        "time_text": None,
        "date_basis": "questionnaire",
        "medication_relation": None,
        "evidence": [{"path": prefix + field, "value": answer[field]} for field in fields],
        "issues": [_issue("count", "count_unknown")] if answer["symptom"] == "vomiting" and answer["count"] is None else [],
    }


def _compatible_with_questionnaire(candidate: dict, observation: dict, questionnaire: dict) -> bool:
    if observation["symptom"] != questionnaire["symptom"] or observation["event_date"] != questionnaire["event_date"]:
        return False
    if observation["assertion"] not in ("present", "absent"):
        return False
    if observation["event_time"] is not None or observation["medication_relation"] is not None:
        return False
    if observation["symptom"] == "vomiting":
        if observation["count_scope"] != "day_to_date":
            return False
        # Earlier within-day snapshots and a submission-time form answer can
        # both be correct. Do not collapse their different reporting windows.
        return not re.search(
            r"\b(?:earlier|previously|before|after|morning|afternoon|evening|tonight|"
            r"breakfast|lunch|dinner|noon|midnight|as\s+of)\b|\b(?:by|at)\s+\d",
            candidate["quote"],
            re.IGNORECASE,
        )
    # A daily nausea score is comparable; a current or morning-only claim is not.
    if candidate["severity_context"] == "worst_today_so_far":
        return True
    if candidate["severity_context"] in ("current", "other"):
        return False
    time_text = observation["time_text"] or ""
    return bool(re.search(r"\btoday\b", time_text, re.IGNORECASE)) and not re.search(
        r"\b(?:morning|afternoon|evening|tonight|dinner|lunch|breakfast|now|currently)\b",
        time_text,
        re.IGNORECASE,
    )


def _merge_daily(observations: list[dict]) -> dict:
    """Combine comparable claims without letting disagreement contaminate other fields."""
    text_observations = sorted((item for item in observations if item["date_basis"] != "questionnaire"), key=_canonical)
    form_observations = [item for item in observations if item["date_basis"] == "questionnaire"]
    ordered = text_observations + form_observations
    merged = dict(ordered[0])
    issues = _unique([issue for item in ordered for issue in item["issues"]])
    merged["evidence"] = _unique([evidence for item in ordered for evidence in item["evidence"]])
    assertions = {item["assertion"] for item in ordered}
    assertion_conflict = len(assertions) > 1
    if assertion_conflict:
        merged["assertion"] = "uncertain"
        issues.append(_issue("assertion", "conflicting_sources"))
    for field in ("count", "severity"):
        values = {item[field] for item in ordered if item[field] is not None}
        conflict = len(values) > 1 or (assertion_conflict and bool(values))
        if conflict:
            merged[field] = None
            issues.append(_issue(field, "conflicting_sources"))
        else:
            # Only normalized, eligible values enter this comparison. A valid
            # form score can supply the value when a text score was rejected;
            # the rejected source's issue and evidence still remain visible.
            merged[field] = next(iter(values)) if values else None
        if field == "count" and (conflict or merged[field] is not None):
            issues = [issue for issue in issues if issue != _issue("count", "count_unknown")]
    merged["issues"] = _unique(issues)
    return merged


def _sort_key(observation: dict) -> tuple:
    return (
        observation["event_date"] is None, observation["event_date"] or "",
        observation["event_time"] is None, observation["event_time"] or "",
        observation["symptom"], observation["count_scope"] or "", observation["assertion"],
        _canonical(observation),
    )


def normalize_report(report: dict, candidates: list[dict]) -> list[dict]:
    """Validate and normalize one report; never read gold or other reports.

    Schema errors and NormalizationError deliberately propagate so the caller can
    record a failed report separately from a successful empty extraction.
    """
    report = SourceReport.model_validate(report).model_dump(mode="json")
    candidates = CandidateBatch.model_validate({"candidates": candidates}).model_dump(mode="json")["candidates"]
    local_submission = datetime.fromisoformat(report["reported_at"]).astimezone(ZoneInfo(report["patient_timezone"]))
    # Exact repeated output is one source claim; different excerpts stay distinct.
    candidates = _unique(candidates)
    pairs = [(candidate, _candidate_observation(candidate, report, local_submission)) for candidate in candidates]
    observations = []
    consumed = set()
    for index, answer in enumerate(report["questionnaire_answers"]):
        questionnaire = _questionnaire_observation(answer, index)
        if questionnaire is None:
            continue
        matches = []
        for candidate_index, (candidate, observation) in enumerate(pairs):
            if _compatible_with_questionnaire(candidate, observation, questionnaire):
                consumed.add(candidate_index)
                matches.append(observation)
        observations.append(_merge_daily(matches + [questionnaire]) if matches else questionnaire)
    daily_groups = {}
    for index, (candidate, observation) in enumerate(pairs):
        if index in consumed:
            continue
        # Apply the same compatibility gate to multiple text claims, even when
        # no form answer exists. Events and windows remain separate records.
        if _compatible_with_questionnaire(candidate, observation, observation):
            key = (observation["symptom"], observation["event_date"])
            daily_groups.setdefault(key, []).append(observation)
        else:
            observations.append(observation)
    for group in daily_groups.values():
        observations.append(_merge_daily(group) if len(group) > 1 else group[0])
    result = []
    for index, observation in enumerate(sorted(observations, key=_sort_key), start=1):
        observation["observation_id"] = f"{report['report_id']}-O{index}"
        result.append(NormalizedObservation.model_validate(observation).model_dump(mode="json"))
    return result
