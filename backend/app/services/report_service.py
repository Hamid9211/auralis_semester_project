"""Report upload and background processing (module M4, FR-RA-01 to FR-RA-05).

Thread-safety strategy (full description in docs/m2/thread-safety.md):
1. Worker threads only run text extraction (and the blocking LLM call) on their
   own immutable ReportJob; they share no mutable state.
2. Every report write (create, status change, results) happens on the event
   loop while holding one asyncio.Lock, so no update is lost or interleaved.
3. The duplicate check and the insert happen under the same lock, and the
   database UNIQUE(patient_id, file_hash) constraint backs it up.
4. Extracted lab values are frozen dataclasses and cannot change after creation.
"""

import asyncio
import hashlib

from app.core.exceptions import DuplicateReportError, InvalidFileError, NotFoundError
from app.core.logging_config import get_logger
from app.domain.lab_reports import (
    ExplanationGenerator,
    LabReport,
    LabReportRepository,
    ReportJob,
    TextExtractor,
)
from app.services.lab_value_parser import LabValueParser

logger = get_logger("reports.service")

PDF_SIGNATURE = b"%PDF-"
PDF_EXTENSION = ".pdf"
MAX_FILENAME_LENGTH = 255


class ReportService:
    """Validates uploads and queues them for background processing."""

    def __init__(self, *, repository: LabReportRepository, extractor: TextExtractor,
                 generator: ExplanationGenerator, fallback: ExplanationGenerator,
                 max_upload_bytes: int) -> None:
        self._repository = repository
        self._extractor = extractor
        self._generator = generator
        self._fallback = fallback
        self._max_upload_bytes = max_upload_bytes
        self._parser = LabValueParser()
        # Private: callers cannot change report state without going through the lock.
        self._queue: asyncio.Queue[ReportJob] = asyncio.Queue()
        self._lock = asyncio.Lock()

    # --- Upload and queries ----------------------------------------------------

    async def upload(self, patient_id: int, filename: str, data: bytes) -> LabReport:
        """Validate and store a new report, queue it, and return it as pending."""
        clean_name = self._validate(filename, data)
        file_hash = hashlib.sha256(data).hexdigest()
        async with self._lock:
            if self._repository.find_by_hash(patient_id, file_hash) is not None:
                raise DuplicateReportError("This report has already been uploaded.")
            report = self._repository.add(patient_id, clean_name, file_hash)
        await self._queue.put(ReportJob(report_id=report.id, pdf_bytes=bytes(data)))
        logger.info("Report %s (%s) queued", report.id, clean_name)
        return report

    def list_reports(self, patient_id: int) -> list[LabReport]:
        """All reports of a patient, newest first (FR-RA-05)."""
        return self._repository.find_by_patient(patient_id)

    def get_report(self, report_id: int) -> LabReport:
        """One report, or NotFoundError."""
        report = self._repository.get(report_id)
        if report is None:
            raise NotFoundError(f"Lab report {report_id} does not exist.")
        return report

    # --- Queue access for workers ----------------------------------------------

    async def next_job(self) -> ReportJob:
        """Wait for the next queued report."""
        return await self._queue.get()

    def job_done(self) -> None:
        """Tell the queue that one job has been handled."""
        self._queue.task_done()

    async def wait_until_idle(self) -> None:
        """Wait until every queued report has been handled."""
        await self._queue.join()

    # --- Validation (FR-RA-01, NFR-06) --------------------------------------------

    def _validate(self, filename: str, data: bytes) -> str:
        # Browsers on Windows may send a full path; keep only the file name.
        name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not name:
            raise InvalidFileError("A file name is required.")
        if len(name) > MAX_FILENAME_LENGTH:
            raise InvalidFileError(
                f"The file name is longer than {MAX_FILENAME_LENGTH} characters.")
        if not name.lower().endswith(PDF_EXTENSION):
            raise InvalidFileError("Only PDF files can be uploaded.")
        if not data:
            raise InvalidFileError("The file is empty.")
        if len(data) > self._max_upload_bytes:
            limit_mb = self._max_upload_bytes / (1024 * 1024)
            raise InvalidFileError(f"The file is larger than {limit_mb:g} MB.")
        if not data.startswith(PDF_SIGNATURE):
            raise InvalidFileError("The file is not a valid PDF.")
        return name

