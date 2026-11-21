# Thread-safety strategy: Medical Report Analyzer (M4)

## The concurrent operation

`POST /api/reports` validates the PDF, stores the report as **pending**, puts a
`ReportJob` on an `asyncio.Queue` and returns `202 Accepted` at once.
Two `ReportWorker` tasks (`REPORT_WORKER_COUNT` in `app/main.py`) are started
with the application. Each one takes jobs from the queue and runs:

1. status → **processing**
2. PDF text extraction in a worker thread (`asyncio.to_thread`)
3. lab value detection and classification
4. the explanation (the Groq call also runs in a worker thread)
5. status → **done** with results, or **failed** with a reason

Several reports are processed at the same time without blocking the server.
The test `test_two_workers_extract_two_reports_at_the_same_time` shows two
extractions running in parallel.

## The four rules (as planned in Milestone 1)

| # | Rule | Where it is implemented | Test that checks it |
|---|---|---|---|
| 1 | Worker threads only work on their own copy of the file bytes and share no mutable state. | `ReportJob` is a frozen dataclass holding `bytes` (immutable). Threads only run `TextExtractor.extract` and `ExplanationGenerator.explain`, which use only their arguments. | `test_extraction_runs_in_worker_threads_not_the_event_loop` |
| 2 | All report status changes happen only on the event loop, under one `asyncio.Lock`. | Every repository write in `ReportService` (`add`, `replace_failed`, `update_status`, `save_results`, `fail_unfinished`) is inside `async with self._lock` and is never called from a thread. The queue and lock are private attributes. | `test_100_concurrent_uploads_are_each_processed_exactly_once` (every report ends with exactly pending → processing → done; no update lost) |
| 3 | The same file cannot be processed twice. | The duplicate check (`find_by_hash`) and the insert happen under the same lock, so two simultaneous uploads cannot both pass the check. The database constraint `UNIQUE(patient_id, file_hash)` is a second safety net; `SqlLabReportRepository.add` turns its violation into `DuplicateReportError` (HTTP 409). | `test_100_concurrent_uploads_of_one_file_store_it_once`, `test_same_file_cannot_be_stored_twice_for_a_patient` |
| 4 | Extracted lab values are immutable. | `LabValue`, `LabReport` and `ReferenceRange` are frozen dataclasses; `LabReport.values` is a tuple. | `test_values_are_immutable` |

## Other decisions

- **Database sessions.** `SqlLabReportRepository` opens a new short-lived
  `Session` in every method, so no session is shared between requests, workers
  or threads.
- **Fault tolerance (NFR-03).** An `ExtractionError` marks only that report as
  failed. If the LLM fails (`ExplanationError`), the template explanation is used
  and the values are kept. If the template also fails, the report is marked
  failed with a clear message (CA-14). Any other error is caught at the worker's outer
  boundary, logged with its traceback, and the report is marked failed, so the
  worker keeps running.
- **Restart recovery (CA-06).** The queue lives in memory and the PDF bytes are
  not stored, so a report left **pending** or **processing** by a restart cannot
  be resumed. At start-up `ReportService.recover_interrupted` marks every such
  report **failed** (`fail_unfinished`, under the lock), and the patient is asked
  to upload the file again. Tests: `test_unfinished_reports_are_marked_failed_at_startup`,
  `test_recover_interrupted_marks_unfinished_reports_failed`.
- **Re-upload of a failed report (CA-06, CA-11).** A file whose report failed may
  be uploaded again. `replace_failed` deletes the old report and inserts the new
  one in a single database transaction, under the same lock as the duplicate
  check, so a failed insert keeps the old report. Tests:
  `test_failed_report_can_be_uploaded_again`,
  `test_replace_failed_keeps_the_old_report_when_the_insert_fails`.
- **Shutdown.** The workers are cancelled when the application stops.
  `asyncio.CancelledError` is not caught by the worker, so cancellation always
  works.
- **Why `asyncio` and not raw threads.** The lock, the queue and the status
  writes all stay on one thread, which removes data races on report state by
  design. Only the blocking calls that need it (PyMuPDF, the Groq SDK) go to
  threads.
