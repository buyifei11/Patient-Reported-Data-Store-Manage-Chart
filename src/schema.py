"""Executable data contracts shared by extraction and normalization.

Strings remain strings at the JSON boundary; dates and timestamps are validated
without accepting coercions such as string counts, booleans, or missing nulls.
"""

from __future__ import annotations

from datetime import date, datetime, time
import re
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, model_validator


Symptom = Literal["nausea", "vomiting"]
Assertion = Literal["present", "absent", "hypothetical", "uncertain"]
CountScope = Literal["event", "window", "day_to_date", "day_total"]
SeverityContext = Literal["worst_today_so_far", "current", "other", "unknown"]
DayReference = Literal["today", "yesterday", "explicit", "unknown", "multiple_days"]
DateBasis = Literal["relative_text", "explicit_text", "questionnaire", "unknown"]
NonemptyString = Annotated[str, StringConstraints(min_length=1)]
NonnegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]
Severity = Annotated[int, Field(ge=1, le=5)]


def _valid_date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Date must use YYYY-MM-DD.")
    date.fromisoformat(value)
    return value


def _valid_clock(value: str) -> str:
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ValueError("Clock time must use HH:MM.")
    time.fromisoformat(value)
    return value


def _valid_timestamp(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)", value):
        raise ValueError("reported_at must be an ISO timestamp with seconds and an explicit UTC offset.")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("reported_at must have an explicit UTC offset.")
    return value


def _valid_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("patient_timezone must be an available IANA timezone name.") from exc
    return value


DateString = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$"), AfterValidator(_valid_date)]
ClockString = Annotated[str, StringConstraints(pattern=r"^\d{2}:\d{2}$"), AfterValidator(_valid_clock)]
TimestampString = Annotated[str, AfterValidator(_valid_timestamp)]
TimezoneString = Annotated[str, AfterValidator(_valid_timezone)]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class QuestionnaireAnswer(StrictModel):
    symptom: Symptom
    event_date: DateString
    count: NonnegativeInt | None
    severity: Severity | None

    @model_validator(mode="after")
    def coherent_answer(self):
        if self.symptom == "nausea" and self.count is not None:
            raise ValueError("Nausea questionnaire counts must be null.")
        if self.count == 0 and self.severity is not None:
            raise ValueError("Explicit absence cannot carry a severity rating.")
        return self


class SourceReport(StrictModel):
    report_id: NonemptyString
    patient_id: NonemptyString
    reported_at: TimestampString
    patient_timezone: TimezoneString
    text: str
    questionnaire_answers: list[QuestionnaireAnswer]
    supersedes_report_id: NonemptyString | None

    @property
    def reported_datetime(self) -> datetime:
        return datetime.fromisoformat(self.reported_at)

    @property
    def local_date(self) -> date:
        return self.reported_datetime.astimezone(ZoneInfo(self.patient_timezone)).date()

    @model_validator(mode="after")
    def coherent_context(self):
        if self.supersedes_report_id == self.report_id:
            raise ValueError("A report cannot supersede itself.")
        seen = set()
        for answer in self.questionnaire_answers:
            if date.fromisoformat(answer.event_date) != self.local_date:
                raise ValueError("Questionnaire event_date must equal the patient-local submission date.")
            key = (answer.symptom, answer.event_date)
            if key in seen:
                raise ValueError("Questionnaire symptom/date entries must be unique within a report.")
            seen.add(key)
        return self


class MedicationRelation(StrictModel):
    medication: NonemptyString
    relation: Literal["after_taking"]


class Candidate(StrictModel):
    symptom: Symptom
    assertion: Assertion
    count: NonnegativeInt | None
    count_scope: CountScope | None
    severity_value: NonnegativeInt | None
    severity_scale_max: PositiveInt | None
    severity_context: SeverityContext | None
    time_text: NonemptyString | None
    day_reference: DayReference
    explicit_date: DateString | None
    clock_time: ClockString | None
    quote: NonemptyString
    medication_relation: MedicationRelation | None


class CandidateBatch(StrictModel):
    candidates: list[Candidate]


class Evidence(StrictModel):
    path: Annotated[str, StringConstraints(pattern=r"^(text|questionnaire_answers\.\d+\.(symptom|event_date|count|severity))$")]
    value: str | int | None


class Issue(StrictModel):
    field: Literal[
        "symptom", "assertion", "count", "count_scope", "severity", "event_date",
        "event_time", "time_text", "date_basis", "medication_relation", "evidence",
    ]
    code: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]


class NormalizedObservation(StrictModel):
    observation_id: NonemptyString
    symptom: Symptom
    assertion: Assertion
    count: NonnegativeInt | None
    count_scope: CountScope | None
    severity: Severity | None
    event_date: DateString | None
    event_time: ClockString | None
    time_text: NonemptyString | None
    date_basis: DateBasis
    medication_relation: MedicationRelation | None
    evidence: Annotated[list[Evidence], Field(min_length=1)]
    issues: list[Issue]

    @model_validator(mode="after")
    def coherent_observation(self):
        if self.symptom == "nausea" and (self.count is not None or self.count_scope is not None):
            raise ValueError("Nausea count and count_scope must be null.")
        if self.assertion == "absent" and (self.count not in {None, 0} or self.severity is not None):
            raise ValueError("Absent symptoms cannot have a positive count or severity.")
        if self.assertion == "present" and self.count == 0:
            raise ValueError("A present symptom cannot have a zero count.")
        if self.assertion == "hypothetical" and (self.count is not None or self.severity is not None):
            raise ValueError("Hypothetical symptoms cannot have observed counts or severity.")
        if (self.event_date is None) != (self.date_basis == "unknown"):
            raise ValueError("An unknown date and unknown date_basis must occur together.")
        return self


class ExtractionCheck(StrictModel):
    source: Evidence
    expected_fields: dict[str, Any]

    @model_validator(mode="after")
    def known_candidate_fields(self):
        if not self.expected_fields:
            raise ValueError("An extraction check must name at least one expected candidate field.")
        unknown = self.expected_fields.keys() - Candidate.model_fields.keys()
        if unknown:
            raise ValueError(f"Unknown candidate fields in extraction check: {sorted(unknown)}")
        for name, value in self.expected_fields.items():
            field = Candidate.model_fields[name]
            annotation = Annotated[field.annotation, *field.metadata] if field.metadata else field.annotation
            TypeAdapter(annotation).validate_python(value, strict=True)
        return self


class GoldRecord(StrictModel):
    report_id: NonemptyString
    extraction_checks: list[ExtractionCheck]
    observations: list[NormalizedObservation]

    @model_validator(mode="after")
    def unique_observations(self):
        ids = [observation.observation_id for observation in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("Gold observation IDs must be unique within a report.")
        return self


def local_date(report: SourceReport | dict) -> date:
    """Return the submission date in the patient's timezone, never system time."""
    source = report if isinstance(report, SourceReport) else SourceReport.model_validate(report)
    return source.local_date


def validate_sources(rows: list[dict]) -> list[dict]:
    """Validate reports and correction links without discarding earlier versions.

    Correction completeness still needs downstream evidence/review; a valid link
    alone does not prove that a replacement repeated all relevant content.
    """
    reports = [SourceReport.model_validate(row) for row in rows]
    by_id = {}
    for report in reports:
        if report.report_id in by_id:
            raise ValueError(f"Duplicate report_id: {report.report_id}")
        by_id[report.report_id] = report
    for report in reports:
        target_id = report.supersedes_report_id
        if target_id is None:
            continue
        target = by_id.get(target_id)
        if target is None:
            raise ValueError(f"Correction target does not exist: {target_id}")
        if target.patient_id != report.patient_id:
            raise ValueError(f"Correction target belongs to another patient: {target_id}")
        if target.reported_datetime >= report.reported_datetime:
            raise ValueError(f"Correction target must precede its replacement: {target_id}")
    # Strictly earlier timestamps already preclude cycles; retain an explicit
    # graph check to document this invariant if timestamp rules evolve later.
    for report in reports:
        visited = set()
        cursor = report
        while cursor.supersedes_report_id is not None:
            if cursor.report_id in visited:
                raise ValueError("Correction links contain a cycle.")
            visited.add(cursor.report_id)
            cursor = by_id[cursor.supersedes_report_id]
    return [report.model_dump(mode="json") for report in reports]
