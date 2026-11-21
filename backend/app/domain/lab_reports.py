"""Domain model and interfaces of module M4 (Medical Report Analyzer).

This module has no framework or library imports. Services depend on the
interfaces below; infrastructure classes implement them (Dependency Inversion).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ReportStatus(StrEnum):
    """Lifecycle of an uploaded report (FR-RA-02)."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class ReferenceRange:
    """Normal range of one lab test, plus the range of values we accept as readable."""

    test_name: str
    display_name: str
    unit: str
    normal_low: float
    normal_high: float
    plausible_low: float
    plausible_high: float

    def is_normal(self, value: float) -> bool:
        """True when the value lies inside the normal range (bounds included)."""
        return self.normal_low <= value <= self.normal_high

    def is_plausible(self, value: float) -> bool:
        """False for numbers that cannot be this test in this unit (e.g. HbA1c 48 mmol/mol)."""
        return self.plausible_low <= value <= self.plausible_high

    def describe(self) -> str:
        """Human-readable normal range, e.g. '4.0-5.6 %'."""
        return f"{self.normal_low:g}-{self.normal_high:g} {self.unit}"


@dataclass(frozen=True)
class LabValue:
    """One lab value detected in a report.

    Frozen (immutable) so it can be passed between threads safely
    (thread-safety point 4).
    """

    test_name: str
    value: float
    unit: str
    is_normal: bool


@dataclass(frozen=True)
class LabReport:
    """A stored report and its processing results."""

    id: int
    patient_id: int
    filename: str
    file_hash: str
    status: ReportStatus
    uploaded_at: datetime
    explanation: str | None = None
    explanation_source: str | None = None
    error_message: str | None = None
    values: tuple[LabValue, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReportJob:
    """Work item for the background worker.

    The worker gets its own immutable copy of the file bytes, so worker threads
    share no mutable state (thread-safety point 1).
    """

    report_id: int
    pdf_bytes: bytes


HBA1C = "hba1c"
FASTING_GLUCOSE = "fasting_glucose"
LDL_CHOLESTEROL = "ldl_cholesterol"
CREATININE = "creatinine"

# Adult reference ranges. Values outside the plausible range are ignored because
# they are probably in another unit (e.g. HbA1c in mmol/mol) or a misread number.
REFERENCE_RANGES: dict[str, ReferenceRange] = {
    HBA1C: ReferenceRange(HBA1C, "HbA1c", "%", 4.0, 5.6, 3.0, 20.0),
    FASTING_GLUCOSE: ReferenceRange(FASTING_GLUCOSE, "Fasting glucose", "mg/dL",
                                    70.0, 99.0, 20.0, 600.0),
    LDL_CHOLESTEROL: ReferenceRange(LDL_CHOLESTEROL, "LDL cholesterol", "mg/dL",
                                    0.0, 99.0, 10.0, 400.0),
    CREATININE: ReferenceRange(CREATININE, "Creatinine", "mg/dL", 0.6, 1.3, 0.1, 15.0),
}


class TextExtractor(ABC):
    """Extracts plain text from a PDF."""

    @abstractmethod
    def extract(self, pdf_bytes: bytes) -> str:
        """Return the text of the PDF or raise ExtractionError."""


class ExplanationGenerator(ABC):
    """Explains lab values in plain language.

    Contract (Liskov): return a non-empty explanation or raise ExplanationError.
    """

    source: str = "unknown"

    @abstractmethod
    def explain(self, values: list[LabValue], report_text: str) -> str:
        """Return a plain-language explanation of the values."""


class LabReportRepository(ABC):
    """Storage of lab reports and their results."""

    @abstractmethod
    def add(self, patient_id: int, filename: str, file_hash: str) -> LabReport:
        """Store a new pending report; raise DuplicateReportError if the file exists."""

    @abstractmethod
    def get(self, report_id: int) -> LabReport | None:
        """Return one report or None."""

    @abstractmethod
    def find_by_hash(self, patient_id: int, file_hash: str) -> LabReport | None:
        """Return the patient's report with this file hash, if any."""

    @abstractmethod
    def find_by_patient(self, patient_id: int) -> list[LabReport]:
        """Return the patient's reports, newest first."""

    @abstractmethod
    def update_status(self, report_id: int, status: ReportStatus,
                      error_message: str | None = None) -> None:
        """Change the status of a report."""

    @abstractmethod
    def save_results(self, report_id: int, values: list[LabValue], explanation: str,
                     explanation_source: str) -> None:
        """Store detected values and the explanation, and mark the report done."""

    @abstractmethod
    def fail_unfinished(self, message: str) -> int:
        """Mark every pending or processing report failed; return how many changed."""

    @abstractmethod
    def delete(self, report_id: int) -> None:
        """Remove a report and its values; raise NotFoundError if it does not exist."""

    @abstractmethod
    def replace_failed(self, report_id: int, patient_id: int, filename: str,
                       file_hash: str) -> LabReport:
        """Replace a failed report with a new pending one in one transaction.

        If the new report cannot be stored, the old one is kept unchanged.
        """
