"""SqlReadingRepository stores, filters and deletes readings and keeps times in UTC."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.glucose import ReadingContext
from app.infrastructure.db.init_db import DEFAULT_PATIENT_ID, init_database
from app.infrastructure.db.reading_repository import SqlReadingRepository
from app.infrastructure.db.session import create_db_engine, create_session_factory

PID = DEFAULT_PATIENT_ID
T0 = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


@pytest.fixture(name="repo")
def fixture_repo():
    engine = create_db_engine("sqlite://")
    init_database(engine)
    yield SqlReadingRepository(create_session_factory(engine))
    engine.dispose()


def test_add_and_get_round_trip(repo):
    added = repo.add(PID, 145.5, T0, ReadingContext.AFTER_MEAL)
    assert repo.get(added.id) == added
    assert added.measured_at == T0
    assert added.measured_at.tzinfo is not None


def test_time_in_another_zone_is_stored_as_utc(repo):
    pakistan = timezone(timedelta(hours=5))
    added = repo.add(PID, 100, T0.astimezone(pakistan), ReadingContext.FASTING)
    assert repo.get(added.id).measured_at == T0


def test_find_by_patient_newest_first(repo):
    first = repo.add(PID, 100, T0, ReadingContext.FASTING)
    second = repo.add(PID, 110, T0 + HOUR, ReadingContext.FASTING)
    assert [r.id for r in repo.find_by_patient(PID)] == [second.id, first.id]


def test_find_by_patient_with_inclusive_range(repo):
    ids = [repo.add(PID, 100, T0 + i * HOUR, ReadingContext.FASTING).id for i in range(4)]
    found = repo.find_by_patient(PID, start=T0 + HOUR, end=T0 + 2 * HOUR)
    assert [r.id for r in found] == [ids[2], ids[1]]


def test_find_with_only_start_or_only_end(repo):
    ids = [repo.add(PID, 100, T0 + i * HOUR, ReadingContext.FASTING).id for i in range(3)]
    assert [r.id for r in repo.find_by_patient(PID, start=T0 + HOUR)] == [ids[2], ids[1]]
    assert [r.id for r in repo.find_by_patient(PID, end=T0)] == [ids[0]]


def test_delete_existing_and_unknown(repo):
    added = repo.add(PID, 100, T0, ReadingContext.FASTING)
    assert repo.delete(added.id) is True
    assert repo.get(added.id) is None
    assert repo.delete(added.id) is False


def test_get_unknown_returns_none(repo):
    assert repo.get(999) is None


def test_time_without_zone_is_taken_as_utc(repo):
    added = repo.add(PID, 100, T0.replace(tzinfo=None), ReadingContext.FASTING)
    assert repo.get(added.id).measured_at == T0
