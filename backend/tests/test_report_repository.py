"""SqlLabReportRepository stores reports and results and rejects duplicates."""

import pytest

from app.core.exceptions import DuplicateReportError, NotFoundError
from app.domain.lab_reports import CREATININE, HBA1C, ReportStatus
from app.infrastructure.db.init_db import DEFAULT_PATIENT_ID, init_database
from app.infrastructure.db.report_repository import SqlLabReportRepository
from app.infrastructure.db.session import create_db_engine, create_session_factory
from app.services.lab_value_parser import LabValueParser

PID = DEFAULT_PATIENT_ID
HASH_A = "a" * 64
HASH_B = "b" * 64


@pytest.fixture(name="repo")
def fixture_repo():
    engine = create_db_engine("sqlite://")
    init_database(engine)
    yield SqlLabReportRepository(create_session_factory(engine))
    engine.dispose()


def test_add_creates_a_pending_report(repo):
    report = repo.add(PID, "lab.pdf", HASH_A)
    assert report.id is not None
    assert report.status is ReportStatus.PENDING
    assert report.values == ()
    assert repo.get(report.id) == report


def test_same_file_twice_raises_duplicate_error(repo):
    repo.add(PID, "lab.pdf", HASH_A)
    with pytest.raises(DuplicateReportError):
        repo.add(PID, "copy.pdf", HASH_A)


def test_find_by_hash(repo):
    added = repo.add(PID, "lab.pdf", HASH_A)
    assert repo.find_by_hash(PID, HASH_A).id == added.id
    assert repo.find_by_hash(PID, HASH_B) is None


def test_get_unknown_report_returns_none(repo):
    assert repo.get(999) is None


def test_update_status_and_error_message(repo):
    report = repo.add(PID, "lab.pdf", HASH_A)
    repo.update_status(report.id, ReportStatus.FAILED, "corrupt file")
    stored = repo.get(report.id)
    assert stored.status is ReportStatus.FAILED
    assert stored.error_message == "corrupt file"


def test_update_status_of_unknown_report_raises_not_found(repo):
    with pytest.raises(NotFoundError):
        repo.update_status(999, ReportStatus.PROCESSING)


def test_save_results_stores_values_and_marks_done(repo):
    report = repo.add(PID, "lab.pdf", HASH_A)
    values = [LabValueParser.classify(HBA1C, 6.8), LabValueParser.classify(CREATININE, 0.9)]
    repo.save_results(report.id, values, "Explained.", "template")
    stored = repo.get(report.id)
    assert stored.status is ReportStatus.DONE
    assert stored.values == tuple(values)
    assert stored.explanation == "Explained."
    assert stored.explanation_source == "template"


def test_find_by_patient_returns_newest_first(repo):
    first = repo.add(PID, "first.pdf", HASH_A)
    second = repo.add(PID, "second.pdf", HASH_B)
    assert [r.id for r in repo.find_by_patient(PID)] == [second.id, first.id]


def test_find_by_patient_for_patient_without_reports(repo):
    assert not repo.find_by_patient(42)
