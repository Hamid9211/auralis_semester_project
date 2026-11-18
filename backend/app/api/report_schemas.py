"""Response schemas of the lab report API."""

from datetime import datetime

from pydantic import BaseModel

from app.domain.lab_reports import REFERENCE_RANGES, LabReport, LabValue, ReportStatus


class LabValueOut(BaseModel):
    """One detected lab value, with its normal range for display."""

    test_name: str
    display_name: str
    value: float
    unit: str
    is_normal: bool
    normal_range: str

    @classmethod
    def from_domain(cls, value: LabValue) -> "LabValueOut":
        """Build the response from a domain LabValue."""
        reference = REFERENCE_RANGES[value.test_name]
        return cls(test_name=value.test_name, display_name=reference.display_name,
                   value=value.value, unit=value.unit, is_normal=value.is_normal,
                   normal_range=reference.describe())


class LabReportOut(BaseModel):
    """A report, its status and (when done) its results."""

    id: int
    filename: str
    status: ReportStatus
    uploaded_at: datetime
    explanation: str | None
    explanation_source: str | None
    error_message: str | None
    values: list[LabValueOut]

    @classmethod
    def from_domain(cls, report: LabReport) -> "LabReportOut":
        """Build the response from a domain LabReport."""
        return cls(id=report.id, filename=report.filename, status=report.status,
                   uploaded_at=report.uploaded_at, explanation=report.explanation,
                   explanation_source=report.explanation_source,
                   error_message=report.error_message,
                   values=[LabValueOut.from_domain(v) for v in report.values])
