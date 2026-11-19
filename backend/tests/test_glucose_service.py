"""FR-GL-01 to FR-GL-04: GlucoseService rules (EP + BVA on value and date)."""

from datetime import datetime, timedelta, timezone

import pytest
from glucose_fakes import NOW, InMemoryReadingRepository, fixed_clock

from app.core.exceptions import InvalidReadingError, NotFoundError
from app.domain.glucose import ReadingContext
from app.services.glucose_service import GlucoseService

PID = 1
FASTING = ReadingContext.FASTING
HOUR = timedelta(hours=1)


@pytest.fixture(name="service")
def fixture_service() -> GlucoseService:
    return GlucoseService(InMemoryReadingRepository(), clock=fixed_clock)


# --- FR-GL-01 ------------------------------------------------------------------------

def test_valid_reading_is_stored_with_all_fields(service):
    reading = service.log_reading(PID, 110, NOW - HOUR, ReadingContext.AFTER_MEAL)
    assert reading.id is not None
    assert reading.value_mg_dl == 110
    assert reading.measured_at == NOW - HOUR
    assert reading.context is ReadingContext.AFTER_MEAL


@pytest.mark.parametrize("context", list(ReadingContext))
def test_all_four_contexts_are_accepted(service, context):
    assert service.log_reading(PID, 100, NOW, context).context is context


def test_context_given_as_text_is_converted(service):
    assert service.log_reading(PID, 100, NOW, "bedtime").context is ReadingContext.BEDTIME


# --- FR-GL-02: value, boundary value analysis ---------------------------------------------

@pytest.mark.parametrize("value", [20, 21, 599, 600])
def test_values_inside_the_range_are_accepted(service, value):
    assert service.log_reading(PID, value, NOW, FASTING).value_mg_dl == value


@pytest.mark.parametrize("value", [19, 19.9, 600.1, 601, 0, -5])
def test_values_outside_the_range_are_rejected(service, value):
    with pytest.raises(InvalidReadingError, match="between 20 and 600"):
        service.log_reading(PID, value, NOW, FASTING)


# --- FR-GL-02: date ------------------------------------------------------------------------

def test_reading_dated_now_is_accepted(service):
    assert service.log_reading(PID, 100, NOW, FASTING).measured_at == NOW


@pytest.mark.parametrize("delta", [timedelta(seconds=1), timedelta(minutes=1), timedelta(days=1)])
def test_reading_in_the_future_is_rejected(service, delta):
    with pytest.raises(InvalidReadingError, match="future"):
        service.log_reading(PID, 100, NOW + delta, FASTING)


def test_time_without_zone_is_treated_as_utc(service):
    naive = (NOW - HOUR).replace(tzinfo=None)
    assert service.log_reading(PID, 100, naive, FASTING).measured_at == NOW - HOUR


def test_time_in_another_zone_is_converted_to_utc(service):
    pakistan = timezone(timedelta(hours=5))
    local = (NOW - HOUR).astimezone(pakistan)
    assert service.log_reading(PID, 100, local, FASTING).measured_at == NOW - HOUR


def test_future_check_uses_utc_not_local_time(service):
    # 16:30 in Pakistan is 11:30 UTC, which is before NOW (12:00 UTC).
    pakistan = timezone(timedelta(hours=5))
    local = datetime(2026, 11, 19, 16, 30, tzinfo=pakistan)
    assert service.log_reading(PID, 100, local, FASTING).measured_at < NOW


# --- FR-GL-03 ------------------------------------------------------------------------------

def test_list_is_newest_first(service):
    old = service.log_reading(PID, 100, NOW - 3 * HOUR, FASTING)
    new = service.log_reading(PID, 120, NOW - HOUR, FASTING)
    assert [r.id for r in service.list_readings(PID)] == [new.id, old.id]


def test_list_filters_by_inclusive_date_range(service):
    times = [NOW - 5 * HOUR, NOW - 3 * HOUR, NOW - HOUR]
    ids = [service.log_reading(PID, 100, t, FASTING).id for t in times]
    found = service.list_readings(PID, start=NOW - 3 * HOUR, end=NOW - HOUR)
    assert [r.id for r in found] == [ids[2], ids[1]]


def test_list_only_returns_the_patients_own_readings(service):
    service.log_reading(2, 100, NOW, FASTING)
    assert service.list_readings(PID) == []


def test_start_after_end_is_rejected(service):
    with pytest.raises(InvalidReadingError, match="start date"):
        service.list_readings(PID, start=NOW, end=NOW - HOUR)


# --- FR-GL-04 ------------------------------------------------------------------------------

def test_delete_removes_the_reading(service):
    reading = service.log_reading(PID, 100, NOW, FASTING)
    service.delete_reading(reading.id)
    assert service.list_readings(PID) == []


def test_delete_unknown_reading_raises_not_found(service):
    with pytest.raises(NotFoundError):
        service.delete_reading(999)
