"""FR-RA-02..04, NFR-03, NFR-04: background processing, fault tolerance and concurrency."""

import asyncio
import threading

import pytest
from report_fakes import FakeExtractor, FakeGenerator, InMemoryLabReportRepository, fake_pdf

from app.core.exceptions import ExtractionError
from app.domain.lab_reports import HBA1C, ReportStatus
from app.services.report_service import UNEXPECTED_ERROR_MESSAGE, ReportService, ReportWorker

PID = 1
WAIT_SECONDS = 5
EXPLANATION_FAILED = ("The lab values were read, but no explanation could be generated. "
                      "Please upload the file again later.")


class Harness:
    """A ReportService with fakes and a set of running workers."""

    def __init__(self, extractor=None, generator=None, workers=1):
        self.repo = InMemoryLabReportRepository()
        self.extractor = extractor or FakeExtractor()
        self.generator = generator or FakeGenerator("llm")
        self.fallback = FakeGenerator("template")
        self.service = ReportService(repository=self.repo, extractor=self.extractor,
                                     generator=self.generator, fallback=self.fallback,
                                     max_upload_bytes=1024 * 1024)
        self.tasks: list[asyncio.Task] = []
        for _ in range(workers):
            self.start_worker()

    def start_worker(self):
        name = f"w{len(self.tasks)}"
        self.tasks.append(asyncio.create_task(ReportWorker(self.service, name).run()))

    async def idle(self):
        await asyncio.wait_for(self.service.wait_until_idle(), timeout=WAIT_SECONDS)

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


@pytest.fixture(name="make_harness")
async def fixture_make_harness():
    created: list[Harness] = []

    def make(**kwargs) -> Harness:
        harness = Harness(**kwargs)
        created.append(harness)
        return harness

    yield make
    for harness in created:
        await harness.stop()


# --- State transitions (FR-RA-02) ----------------------------------------------------

async def test_report_goes_pending_processing_done(make_harness):
    h = make_harness()
    report = await h.service.upload(PID, "lab.pdf", fake_pdf())
    await h.idle()
    assert h.repo.status_history[report.id] == [
        ReportStatus.PENDING, ReportStatus.PROCESSING, ReportStatus.DONE]


async def test_done_report_has_values_and_llm_explanation(make_harness):
    h = make_harness()
    report = await h.service.upload(PID, "lab.pdf", fake_pdf())
    await h.idle()
    stored = h.service.get_report(report.id)
    assert {v.test_name for v in stored.values} >= {HBA1C}
    assert stored.explanation_source == "llm"
    assert stored.explanation == "llm explanation of 4 values"


async def test_corrupt_pdf_is_marked_failed_with_reason(make_harness):
    h = make_harness(extractor=FakeExtractor(error=ExtractionError("cannot read PDF")))
    report = await h.service.upload(PID, "lab.pdf", fake_pdf())
    await h.idle()
    stored = h.service.get_report(report.id)
    assert stored.status is ReportStatus.FAILED
    assert stored.error_message == "cannot read PDF"
    assert h.repo.status_history[report.id][-2:] == [ReportStatus.PROCESSING,
                                                    ReportStatus.FAILED]


# --- Fault tolerance (NFR-03) -----------------------------------------------------------

async def test_llm_failure_falls_back_to_template_and_keeps_values(make_harness):
    h = make_harness(generator=FakeGenerator("llm", fail=True))
    report = await h.service.upload(PID, "lab.pdf", fake_pdf())
    await h.idle()
    stored = h.service.get_report(report.id)
    assert stored.status is ReportStatus.DONE
    assert stored.explanation_source == "template"
    assert len(stored.values) == 4
    assert h.generator.calls == 1 and h.fallback.calls == 1


async def test_fallback_failure_marks_report_failed_with_a_clear_message(make_harness):
    # INS-01 CA-14: the fallback path needs its own failure test (C5, C12).
    h = make_harness(generator=FakeGenerator("llm", fail=True))
    h.fallback.fail = True
    report = await h.service.upload(PID, "lab.pdf", fake_pdf())
    await h.idle()
    stored = h.service.get_report(report.id)
    assert stored.status is ReportStatus.FAILED
    assert stored.error_message == EXPLANATION_FAILED
    assert h.repo.status_history[report.id][-2:] == [ReportStatus.PROCESSING,
                                                    ReportStatus.FAILED]
    assert h.generator.calls == 1 and h.fallback.calls == 1


async def test_worker_keeps_running_after_a_corrupt_pdf(make_harness):
    extractor = FakeExtractor(error=ExtractionError("bad"))
    h = make_harness(extractor=extractor)
    bad = await h.service.upload(PID, "bad.pdf", fake_pdf("bad"))
    await h.idle()
    extractor.error = None
    good = await h.service.upload(PID, "good.pdf", fake_pdf("good"))
    await h.idle()
    assert h.service.get_report(bad.id).status is ReportStatus.FAILED
    assert h.service.get_report(good.id).status is ReportStatus.DONE


async def test_unexpected_error_marks_failed_and_worker_survives(make_harness):
    extractor = FakeExtractor(error=RuntimeError("bug in extractor"))
    h = make_harness(extractor=extractor)
    bad = await h.service.upload(PID, "bad.pdf", fake_pdf("bad"))
    await h.idle()
    extractor.error = None
    good = await h.service.upload(PID, "good.pdf", fake_pdf("good"))
    await h.idle()
    stored = h.service.get_report(bad.id)
    assert stored.status is ReportStatus.FAILED
    assert stored.error_message == UNEXPECTED_ERROR_MESSAGE
    assert "bug" not in stored.error_message
    assert h.service.get_report(good.id).status is ReportStatus.DONE


async def test_report_deleted_while_queued_does_not_stop_the_worker(make_harness):
    h = make_harness(workers=0)
    gone = await h.service.upload(PID, "gone.pdf", fake_pdf("gone"))
    h.repo.delete(gone.id)
    kept = await h.service.upload(PID, "kept.pdf", fake_pdf("kept"))
    h.start_worker()
    await h.idle()
    assert h.service.get_report(kept.id).status is ReportStatus.DONE


# --- Concurrency and thread safety (NFR-04) ---------------------------------------------

async def test_extraction_runs_in_worker_threads_not_the_event_loop(make_harness):
    h = make_harness()
    await h.service.upload(PID, "lab.pdf", fake_pdf())
    await h.idle()
    assert threading.get_ident() not in h.extractor.thread_ids


async def test_two_workers_extract_two_reports_at_the_same_time(make_harness):
    # The barrier only opens when two extractions are running at once;
    # if processing were sequential, both reports would fail with BrokenBarrierError.
    extractor = FakeExtractor(barrier=threading.Barrier(2, timeout=WAIT_SECONDS))
    h = make_harness(extractor=extractor, workers=2)
    first = await h.service.upload(PID, "a.pdf", fake_pdf("a"))
    second = await h.service.upload(PID, "b.pdf", fake_pdf("b"))
    await h.idle()
    assert h.service.get_report(first.id).status is ReportStatus.DONE
    assert h.service.get_report(second.id).status is ReportStatus.DONE
    assert len(extractor.thread_ids) == 2


async def test_100_concurrent_uploads_of_one_file_store_it_once(make_harness):
    h = make_harness(workers=2)
    results = await asyncio.gather(
        *(h.service.upload(PID, f"copy{i}.pdf", fake_pdf("same")) for i in range(100)),
        return_exceptions=True)
    await h.idle()
    stored = [r for r in results if not isinstance(r, Exception)]
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(stored) == 1
    assert len(errors) == 99
    assert {type(e).__name__ for e in errors} == {"DuplicateReportError"}
    assert len(h.extractor.calls) == 1


async def test_100_concurrent_uploads_are_each_processed_exactly_once(make_harness):
    h = make_harness(workers=3)
    reports = await asyncio.gather(
        *(h.service.upload(PID, f"r{i}.pdf", fake_pdf(f"r{i}")) for i in range(100)))
    await h.idle()
    assert len(h.extractor.calls) == 100
    assert len(set(h.extractor.calls)) == 100
    for report in reports:
        assert h.repo.status_history[report.id] == [
            ReportStatus.PENDING, ReportStatus.PROCESSING, ReportStatus.DONE]
