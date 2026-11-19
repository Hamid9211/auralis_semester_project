"""Request and response schemas of the glucose and trends API."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.glucose import (
    MAX_GLUCOSE_MG_DL,
    MIN_GLUCOSE_MG_DL,
    GlucoseReading,
    ReadingContext,
)
from app.domain.trends import Finding, GlucoseLevel, TrendReport, classify


class ReadingIn(BaseModel):
    """A new reading. Field limits give per-field errors (NFR-05, NFR-06);
    GlucoseService checks the same rules again."""

    value_mg_dl: float = Field(ge=MIN_GLUCOSE_MG_DL, le=MAX_GLUCOSE_MG_DL)
    measured_at: datetime
    context: ReadingContext


class ReadingOut(BaseModel):
    """A stored reading."""

    id: int
    value_mg_dl: float
    measured_at: datetime
    context: ReadingContext

    @classmethod
    def from_domain(cls, reading: GlucoseReading) -> "ReadingOut":
        """Build the response from a domain reading."""
        return cls(id=reading.id, value_mg_dl=reading.value_mg_dl,
                   measured_at=reading.measured_at, context=reading.context)


class TrendPointOut(ReadingOut):
    """A reading with its classification, for the chart (FR-TA-05)."""

    level: GlucoseLevel

    @classmethod
    def from_domain(cls, reading: GlucoseReading) -> "TrendPointOut":
        """Build a chart point from a domain reading."""
        return cls(id=reading.id, value_mg_dl=reading.value_mg_dl,
                   measured_at=reading.measured_at, context=reading.context,
                   level=classify(reading.value_mg_dl))


class FindingOut(BaseModel):
    """A detected pattern with guidance."""

    code: str
    message: str
    reading_ids: list[int]

    @classmethod
    def from_domain(cls, finding: Finding) -> "FindingOut":
        """Build the response from a domain finding."""
        return cls(code=finding.code, message=finding.message,
                   reading_ids=list(finding.reading_ids))


class TrendReportOut(BaseModel):
    """Trend analysis for one period."""

    days: int
    total: int
    low: int
    in_range: int
    high: int
    time_in_range_percent: float | None
    findings: list[FindingOut]
    points: list[TrendPointOut]

    @classmethod
    def from_domain(cls, report: TrendReport) -> "TrendReportOut":
        """Build the response from a domain report; chart points oldest first."""
        return cls(days=report.days, total=report.total, low=report.low,
                   in_range=report.in_range, high=report.high,
                   time_in_range_percent=report.time_in_range_percent,
                   findings=[FindingOut.from_domain(f) for f in report.findings],
                   points=[TrendPointOut.from_domain(r) for r in reversed(report.readings)])
