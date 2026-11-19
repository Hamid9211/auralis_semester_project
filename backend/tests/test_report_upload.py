"""FR-RA-01 / NFR-06: upload validation (EP + BVA on file type and size) and queueing."""

import asyncio

import pytest
from report_fakes import FakeExtractor, FakeGenerator, InMemoryLabReportRepository, pdf_bytes

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
    report = await service.upload(PID, "lab.pdf", pdf_bytes())
    assert report.status is ReportStatus.PENDING
    assert repo.get(report.id).status is ReportStatus.PENDING
    job = await asyncio.wait_for(service.next_job(), timeout=1)
    assert job.report_id == report.id
    assert job.pdf_bytes == pdf_bytes()


# --- Size: boundary value analysis around 5 MB ---------------------------------------

@pytest.mark.parametrize("size", [len(pdf_bytes()), MAX_BYTES - 1, MAX_BYTES])
async def test_sizes_up_to_the_limit_are_accepted(service, size):
    report = await service.upload(PID, "lab.pdf", pdf_bytes(size=size))
    assert report.status is ReportStatus.PENDING


async def test_one_byte_over_the_limit_is_rejected(service):
    with pytest.raises(InvalidFileError, match="larger than 5 MB"):
        await service.upload(PID, "lab.pdf", pdf_bytes(size=MAX_BYTES + 1))


async def test_empty_file_is_rejected(service):
    with pytest.raises(InvalidFileError, match="empty"):
        await service.upload(PID, "lab.pdf", b"")


# --- Type: equivalence partitions ------------------------------------------------------

@pytest.mark.parametrize("filename", ["lab.txt", "lab.pdf.exe", "lab", "photo.png"])
async def test_non_pdf_extensions_are_rejected(service, filename):
    with pytest.raises(InvalidFileError, match="Only PDF"):
        await service.upload(PID, filename, pdf_bytes())


async def test_uppercase_extension_is_accepted(service):
    report = await service.upload(PID, "LAB.PDF", pdf_bytes())
    assert report.filename == "LAB.PDF"


async def test_pdf_name_with_wrong_content_is_rejected(service):
    with pytest.raises(InvalidFileError, match="not a valid PDF"):
        await service.upload(PID, "lab.pdf", b"PK\x03\x04 this is a zip file")


@pytest.mark.parametrize("filename", ["", "   ", None])
async def test_missing_filename_is_rejected(service, filename):
    with pytest.raises(InvalidFileError, match="file name is required"):
        await service.upload(PID, filename, pdf_bytes())


async def test_overlong_filename_is_rejected(service):
    name = "a" * (MAX_FILENAME_LENGTH - 3) + ".pdf"
    with pytest.raises(InvalidFileError, match="longer than"):
        await service.upload(PID, name, pdf_bytes())


async def test_path_in_filename_is_stripped(service):
    report = await service.upload(PID, r"C:\Users\hamid\Desktop\lab.pdf", pdf_bytes())
    assert report.filename == "lab.pdf"


async def test_rejected_upload_is_not_stored_or_queued(service, repo):
    with pytest.raises(InvalidFileError):
        await service.upload(PID, "lab.txt", pdf_bytes())
    assert not repo.find_by_patient(PID)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(service.next_job(), timeout=0.05)


# --- Duplicates and queries --------------------------------------------------------------

async def test_same_file_twice_is_rejected(service):
    await service.upload(PID, "lab.pdf", pdf_bytes())
    with pytest.raises(DuplicateReportError):
        await service.upload(PID, "renamed.pdf", pdf_bytes())


async def test_same_file_for_another_patient_is_allowed(service):
    await service.upload(PID, "lab.pdf", pdf_bytes())
    report = await service.upload(2, "lab.pdf", pdf_bytes())
    assert report.patient_id == 2


async def test_list_reports_newest_first(service):
    first = await service.upload(PID, "a.pdf", pdf_bytes("a"))
    second = await service.upload(PID, "b.pdf", pdf_bytes("b"))
    assert [r.id for r in service.list_reports(PID)] == [second.id, first.id]


def test_get_unknown_report_raises_not_found(service):
    with pytest.raises(NotFoundError):
        service.get_report(999)
