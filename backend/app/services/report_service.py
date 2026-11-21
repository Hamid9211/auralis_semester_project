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

from app.core.exceptions import (
    AuralisError,
    DuplicateReportError,
    ExplanationError,
    ExtractionError,
    InvalidFileError,
    NotFoundError,
)
from app.core.logging_config import get_logger
from app.domain.lab_reports import (
    ExplanationGenerator,
    LabReport,
    LabReportRepository,
    LabValue,
    ReportJob,
    ReportStatus,
    TextExtractor,
)
from app.services.lab_value_parser import LabValueParser

logger = get_logger("reports.service")

PDF_SIGNATURE = b"%PDF-"
PDF_EXTENSION = ".pdf"
MAX_FILENAME_LENGTH = 255
UNEXPECTED_ERROR_MESSAGE = "An unexpected error occurred while processing the report."
INTERRUPTED_MESSAGE = "Processing was interrupted. Please upload the file again."


class ReportService:
    """Validates uploads, queues them, and processes queued reports."""

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
            existing = self._repository.find_by_hash(patient_id, file_hash)
            if existing is not None:
                if existing.status is not ReportStatus.FAILED:
                    raise DuplicateReportError("This report has already been uploaded.")
                # CA-06: a failed report may be uploaded again; it replaces the old one.
                # CA-11: delete and insert are one transaction, so a failed insert
                # keeps the old report.
                report = self._repository.replace_failed(existing.id, patient_id,
                                                         clean_name, file_hash)
            else:
                report = self._repository.add(patient_id, clean_name, file_hash)
        await self._queue.put(ReportJob(report_id=report.id, pdf_bytes=bytes(data)))
        # CA-12: log only the id; file names can contain a patient's name.
        logger.info("Report %s queued", report.id)
        return report

    async def recover_interrupted(self) -> int:
        """Mark reports left unfinished by a restart as failed (CA-06).

        The queue lives in memory and the PDF bytes are not stored, so these
        reports cannot be re-queued; the patient is asked to upload them again.
        """
        async with self._lock:
            count = self._repository.fail_unfinished(INTERRUPTED_MESSAGE)
        if count:
            logger.warning("Marked %d interrupted report(s) as failed", count)
        return count

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

    # --- Processing --------------------------------------------------------------

    async def process(self, job: ReportJob) -> None:
        """Extract, classify and explain one report, updating its status (FR-RA-02)."""
        await self._set_status(job.report_id, ReportStatus.PROCESSING)
        try:
            text = await asyncio.to_thread(self._extractor.extract, job.pdf_bytes)
        except ExtractionError as exc:
            logger.warning("Report %s failed: %s", job.report_id, exc.message)
            await self._set_status(job.report_id, ReportStatus.FAILED, exc.message)
            return
        values = self._parser.parse(text)
        explanation, source = await self._explain(values, text)
        async with self._lock:
            self._repository.save_results(job.report_id, values, explanation, source)
        logger.info("Report %s done: %d values, %s explanation",
                    job.report_id, len(values), source)

    async def mark_failed(self, report_id: int, message: str) -> None:
        """Mark a report as failed (used by the worker for unexpected errors)."""
        await self._set_status(report_id, ReportStatus.FAILED, message)

    async def _explain(self, values: list[LabValue], text: str) -> tuple[str, str]:
        try:
            explanation = await asyncio.to_thread(self._generator.explain, values, text)
            return explanation, self._generator.source
        except ExplanationError as exc:
            # NFR-03: the report still gets its values and a template explanation.
            logger.warning("Primary explanation failed (%s); using %s fallback",
                           exc.message, self._fallback.source)
            return self._fallback.explain(values, text), self._fallback.source

    async def _set_status(self, report_id: int, status: ReportStatus,
                          error_message: str | None = None) -> None:
        async with self._lock:
            self._repository.update_status(report_id, status, error_message)

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


class ReportWorker:
    """Background task that processes queued reports one after another.

    Several workers can run at once; each one stays alive whatever happens to a
    single report (NFR-03).
    """

    def __init__(self, service: ReportService, name: str) -> None:
        self._service = service
        self._name = name

    async def run(self) -> None:
        """Process jobs until the task is cancelled at shutdown."""
        logger.info("%s started", self._name)
        while True:
            job = await self._service.next_job()
            try:
                await self._service.process(job)
            except AuralisError as exc:
                logger.warning("%s: report %s failed: %s", self._name, job.report_id,
                               exc.message)
                await self._fail_quietly(job.report_id, exc.message)
            except Exception:  # pylint: disable=broad-exception-caught
                # Last-resort boundary: an unknown error in one report must not
                # stop the worker. The full traceback is logged.
                logger.exception("%s: unexpected error on report %s", self._name,
                                 job.report_id)
                await self._fail_quietly(job.report_id, UNEXPECTED_ERROR_MESSAGE)
            finally:
                self._service.job_done()

    async def _fail_quietly(self, report_id: int, message: str) -> None:
        try:
            await self._service.mark_failed(report_id, message)
        except AuralisError as exc:
            logger.error("%s: could not mark report %s as failed: %s", self._name,
                         report_id, exc.message)
