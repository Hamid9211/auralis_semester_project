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


# --- CA-06: reports left unfinished by a restart, and re-upload after failure ---------

INTERRUPTED = "Processing was interrupted. Please upload the file again."


def test_fail_unfinished_marks_pending_and_processing_reports_failed(repo):
    pending = repo.add(PID, "a.pdf", HASH_A)
    processing = repo.add(PID, "b.pdf", HASH_B)
    repo.update_status(processing.id, ReportStatus.PROCESSING)
    done = repo.add(PID, "c.pdf", "c" * 64)
    repo.save_results(done.id, [], "fine", "template")

    assert repo.fail_unfinished(INTERRUPTED) == 2

    for report_id in (pending.id, processing.id):
        stored = repo.get(report_id)
        assert stored.status is ReportStatus.FAILED
        assert stored.error_message == INTERRUPTED
    assert repo.get(done.id).status is ReportStatus.DONE
    assert repo.get(done.id).error_message is None


def test_fail_unfinished_without_unfinished_reports_returns_zero(repo):
    assert repo.fail_unfinished(INTERRUPTED) == 0


def test_delete_removes_the_report_and_its_values(repo):
    report = repo.add(PID, "lab.pdf", HASH_A)
    values = LabValueParser().parse("HbA1c 6.8 %")
    repo.save_results(report.id, values, "explained", "template")

    repo.delete(report.id)

    assert repo.get(report.id) is None
    assert repo.find_by_hash(PID, HASH_A) is None
    # The UNIQUE(patient_id, file_hash) slot is free again.
    assert repo.add(PID, "lab.pdf", HASH_A).status is ReportStatus.PENDING


def test_delete_unknown_report_raises_not_found(repo):
    with pytest.raises(NotFoundError):
        repo.delete(999)


# --- INS-01 CA-11: re-upload replaces a failed report in one transaction -----------

def test_replace_failed_swaps_the_report_in_one_step(repo):
    old = repo.add(PID, "lab.pdf", HASH_A)
    repo.update_status(old.id, ReportStatus.FAILED, INTERRUPTED)

    new = repo.replace_failed(old.id, PID, "lab.pdf", HASH_A)

    # SQLite may reuse the freed id, so check the state rather than the id.
    assert new.status is ReportStatus.PENDING
    assert new.error_message is None
    assert repo.find_by_hash(PID, HASH_A) == new
    assert len(repo.find_by_patient(PID)) == 1


def test_replace_failed_keeps_the_old_report_when_the_insert_fails(repo):
    old = repo.add(PID, "old.pdf", HASH_A)
    repo.update_status(old.id, ReportStatus.FAILED, INTERRUPTED)
    repo.add(PID, "other.pdf", HASH_B)

    with pytest.raises(DuplicateReportError):
        # The insert breaks UNIQUE(patient_id, file_hash), so the transaction rolls back.
        repo.replace_failed(old.id, PID, "other.pdf", HASH_B)

    kept = repo.get(old.id)
    assert kept is not None
    assert kept.status is ReportStatus.FAILED
    assert kept.error_message == INTERRUPTED


def test_replace_failed_of_unknown_report_raises_not_found(repo):
    with pytest.raises(NotFoundError):
        repo.replace_failed(999, PID, "lab.pdf", HASH_A)
