"""FR-RA-01 / NFR-06: upload validation (EP + BVA on file type and size) and queueing."""

import asyncio

import pytest
from report_fakes import FakeExtractor, FakeGenerator, InMemoryLabReportRepository, fake_pdf

from app.core.config import Settings
from app.core.exceptions import DuplicateReportError, InvalidFileError, NotFoundError
from app.domain.lab_reports import ReportStatus
from app.services.report_service import MAX_FILENAME_LENGTH, ReportService

PID = 1
MAX_BYTES = Settings().max_upload_bytes  # 5 MB, from NFR-06


@pytest.fixture(name="repo")
def fixture_repo() -> InMemoryLabReportRepository:
    return InMemoryLabReportRepository()


@pytest.fixture(name="service")
def fixture_service(repo) -> ReportService:
    return ReportService(repository=repo, extractor=FakeExtractor(), generator=FakeGenerator(),
                         fallback=FakeGenerator("template"), max_upload_bytes=MAX_BYTES)


async def test_upload_returns_pending_report_and_queues_it(service, repo):
    report = await service.upload(PID, "lab.pdf", fake_pdf())
    assert report.status is ReportStatus.PENDING
    assert repo.get(report.id).status is ReportStatus.PENDING
    job = await asyncio.wait_for(service.next_job(), timeout=1)
    assert job.report_id == report.id
    assert job.pdf_bytes == fake_pdf()


# --- Size: boundary value analysis around 5 MB ---------------------------------------

@pytest.mark.parametrize("size", [len(fake_pdf()), MAX_BYTES - 1, MAX_BYTES])
async def test_sizes_up_to_the_limit_are_accepted(service, size):
    report = await service.upload(PID, "lab.pdf", fake_pdf(size=size))
    assert report.status is ReportStatus.PENDING


async def test_one_byte_over_the_limit_is_rejected(service):
    with pytest.raises(InvalidFileError, match="larger than 5 MB"):
        await service.upload(PID, "lab.pdf", fake_pdf(size=MAX_BYTES + 1))


async def test_empty_file_is_rejected(service):
    with pytest.raises(InvalidFileError, match="empty"):
        await service.upload(PID, "lab.pdf", b"")


# --- Type: equivalence partitions ------------------------------------------------------

@pytest.mark.parametrize("filename", ["lab.txt", "lab.pdf.exe", "lab", "photo.png"])
async def test_non_pdf_extensions_are_rejected(service, filename):
    with pytest.raises(InvalidFileError, match="Only PDF"):
        await service.upload(PID, filename, fake_pdf())


async def test_uppercase_extension_is_accepted(service):
    report = await service.upload(PID, "LAB.PDF", fake_pdf())
    assert report.filename == "LAB.PDF"


async def test_pdf_name_with_wrong_content_is_rejected(service):
    with pytest.raises(InvalidFileError, match="not a valid PDF"):
        await service.upload(PID, "lab.pdf", b"PK\x03\x04 this is a zip file")


@pytest.mark.parametrize("filename", ["", "   ", None])
async def test_missing_filename_is_rejected(service, filename):
    with pytest.raises(InvalidFileError, match="file name is required"):
        await service.upload(PID, filename, fake_pdf())


async def test_overlong_filename_is_rejected(service):
    name = "a" * (MAX_FILENAME_LENGTH - 3) + ".pdf"
    with pytest.raises(InvalidFileError, match="longer than"):
        await service.upload(PID, name, fake_pdf())


async def test_path_in_filename_is_stripped(service):
    report = await service.upload(PID, r"C:\Users\hamid\Desktop\lab.pdf", fake_pdf())
    assert report.filename == "lab.pdf"


async def test_rejected_upload_is_not_stored_or_queued(service, repo):
    with pytest.raises(InvalidFileError):
        await service.upload(PID, "lab.txt", fake_pdf())
    assert not repo.find_by_patient(PID)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(service.next_job(), timeout=0.05)


# --- Duplicates and queries --------------------------------------------------------------

async def test_same_file_twice_is_rejected(service):
    await service.upload(PID, "lab.pdf", fake_pdf())
    with pytest.raises(DuplicateReportError):
        await service.upload(PID, "renamed.pdf", fake_pdf())


async def test_same_file_for_another_patient_is_allowed(service):
    await service.upload(PID, "lab.pdf", fake_pdf())
    report = await service.upload(2, "lab.pdf", fake_pdf())
    assert report.patient_id == 2


async def test_list_reports_newest_first(service):
    first = await service.upload(PID, "a.pdf", fake_pdf("a"))
    second = await service.upload(PID, "b.pdf", fake_pdf("b"))
    assert [r.id for r in service.list_reports(PID)] == [second.id, first.id]


def test_get_unknown_report_raises_not_found(service):
    with pytest.raises(NotFoundError):
        service.get_report(999)


# --- CA-06: interrupted reports and re-upload after failure -------------------------------

INTERRUPTED = "Processing was interrupted. Please upload the file again."


async def test_recover_interrupted_marks_unfinished_reports_failed(service, repo):
    pending = await service.upload(PID, "a.pdf", fake_pdf("a"))
    processing = await service.upload(PID, "b.pdf", fake_pdf("b"))
    repo.update_status(processing.id, ReportStatus.PROCESSING)

    assert await service.recover_interrupted() == 2

    for report_id in (pending.id, processing.id):
        stored = repo.get(report_id)
        assert stored.status is ReportStatus.FAILED
        assert stored.error_message == INTERRUPTED


async def test_recover_interrupted_leaves_finished_reports_alone(service, repo):
    report = await service.upload(PID, "a.pdf", fake_pdf("a"))
    repo.save_results(report.id, [], "fine", "template")
    assert await service.recover_interrupted() == 0
    assert repo.get(report.id).status is ReportStatus.DONE


async def test_failed_report_can_be_uploaded_again(service, repo):
    first = await service.upload(PID, "lab.pdf", fake_pdf())
    await asyncio.wait_for(service.next_job(), timeout=1)
    repo.update_status(first.id, ReportStatus.FAILED, INTERRUPTED)

    second = await service.upload(PID, "lab.pdf", fake_pdf())

    assert second.id != first.id
    assert second.status is ReportStatus.PENDING
    assert repo.get(first.id) is None
    assert [r.id for r in service.list_reports(PID)] == [second.id]
    job = await asyncio.wait_for(service.next_job(), timeout=1)
    assert job.report_id == second.id


@pytest.mark.parametrize("status", [ReportStatus.PROCESSING, ReportStatus.DONE])
async def test_unfailed_report_still_blocks_a_duplicate(service, repo, status):
    first = await service.upload(PID, "lab.pdf", fake_pdf())
    repo.update_status(first.id, status)
    with pytest.raises(DuplicateReportError):
        await service.upload(PID, "lab.pdf", fake_pdf())
