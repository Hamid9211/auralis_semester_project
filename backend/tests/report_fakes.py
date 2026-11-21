"""Test doubles for module M4.

They implement the same domain interfaces as the real classes (Liskov), so
ReportService can be tested without a database, PyMuPDF or the Groq API.
"""

import itertools
import threading
from dataclasses import replace
from datetime import datetime, timezone

from app.core.exceptions import DuplicateReportError, ExplanationError, NotFoundError
from app.domain.lab_reports import (
    ExplanationGenerator,
    LabReport,
    LabReportRepository,
    LabValue,
    ReportStatus,
    TextExtractor,
)

SAMPLE_TEXT = "HbA1c 6.8 %\nFasting glucose 126 mg/dL\nLDL 80\nCreatinine 0.9"


def fake_pdf(tag: str = "sample", size: int = 0) -> bytes:
    """Bytes that pass upload validation; a different tag gives a different file."""
    body = f"%PDF-1.4 {tag}".encode()
    return body + b"0" * max(0, size - len(body))


class InMemoryLabReportRepository(LabReportRepository):
    """Dictionary-backed repository that also records every status change."""

    def __init__(self) -> None:
        self._reports: dict[int, LabReport] = {}
        self._ids = itertools.count(1)
        self.status_history: dict[int, list[ReportStatus]] = {}

    def add(self, patient_id: int, filename: str, file_hash: str) -> LabReport:
        if self.find_by_hash(patient_id, file_hash) is not None:
            raise DuplicateReportError("duplicate")
        report = LabReport(id=next(self._ids), patient_id=patient_id, filename=filename,
                           file_hash=file_hash, status=ReportStatus.PENDING,
                           uploaded_at=datetime.now(timezone.utc))
        self._reports[report.id] = report
        self.status_history[report.id] = [ReportStatus.PENDING]
        return report

    def get(self, report_id: int) -> LabReport | None:
        return self._reports.get(report_id)

    def find_by_hash(self, patient_id: int, file_hash: str) -> LabReport | None:
        return next((r for r in self._reports.values()
                     if r.patient_id == patient_id and r.file_hash == file_hash), None)

    def find_by_patient(self, patient_id: int) -> list[LabReport]:
        reports = [r for r in self._reports.values() if r.patient_id == patient_id]
        return sorted(reports, key=lambda r: r.id, reverse=True)

    def update_status(self, report_id: int, status: ReportStatus,
                      error_message: str | None = None) -> None:
        self._change(report_id, status=status, error_message=error_message)

    def save_results(self, report_id: int, values: list[LabValue], explanation: str,
                     explanation_source: str) -> None:
        self._change(report_id, status=ReportStatus.DONE, values=tuple(values),
                     explanation=explanation, explanation_source=explanation_source,
                     error_message=None)

    def fail_unfinished(self, message: str) -> int:
        unfinished = [r.id for r in self._reports.values()
                      if r.status in (ReportStatus.PENDING, ReportStatus.PROCESSING)]
        for report_id in unfinished:
            self._change(report_id, status=ReportStatus.FAILED, error_message=message)
        return len(unfinished)

    def replace_failed(self, report_id: int, patient_id: int, filename: str,
                       file_hash: str) -> LabReport:
        """Like the SQL version: the old report is restored if the new one cannot be stored."""
        if report_id not in self._reports:
            raise NotFoundError(f"Lab report {report_id} does not exist.")
        old = self._reports.pop(report_id)
        try:
            return self.add(patient_id, filename, file_hash)
        except Exception:
            self._reports[report_id] = old
            raise

    def delete(self, report_id: int) -> None:
        """Remove a report (also used to simulate a report disappearing while queued)."""
        if report_id not in self._reports:
            raise NotFoundError(f"Lab report {report_id} does not exist.")
        del self._reports[report_id]

    def _change(self, report_id: int, **changes) -> None:
        if report_id not in self._reports:
            raise NotFoundError(f"Lab report {report_id} does not exist.")
        self._reports[report_id] = replace(self._reports[report_id], **changes)
        self.status_history[report_id].append(changes["status"])


class FakeExtractor(TextExtractor):
    """Returns fixed text; can raise, block on a barrier, and records its threads."""

    def __init__(self, text: str = SAMPLE_TEXT, error: Exception | None = None,
                 barrier: threading.Barrier | None = None) -> None:
        self.text = text
        self.error = error
        self.barrier = barrier
        self.calls: list[bytes] = []
        self.thread_ids: set[int] = set()
        self._calls_lock = threading.Lock()

    def extract(self, pdf_bytes: bytes) -> str:
        with self._calls_lock:
            self.calls.append(pdf_bytes)
            self.thread_ids.add(threading.get_ident())
        if self.barrier is not None:
            self.barrier.wait()
        if self.error is not None:
            raise self.error
        return self.text


class FakeGenerator(ExplanationGenerator):
    """Returns a fixed explanation, or raises ExplanationError when told to fail."""

    def __init__(self, source: str = "llm", fail: bool = False) -> None:
        self.source = source
        self.fail = fail
        self.calls = 0

    def explain(self, values: list[LabValue], report_text: str) -> str:
        self.calls += 1
        if self.fail:
            raise ExplanationError("LLM unavailable")
        return f"{self.source} explanation of {len(values)} values"
