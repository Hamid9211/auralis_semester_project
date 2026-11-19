"""FR-TA-02 and the Strategy wiring of TrendService."""

from datetime import timedelta

import pytest
from glucose_fakes import NOW, InMemoryReadingRepository, fixed_clock

from app.core.exceptions import InvalidReadingError
from app.domain.glucose import ReadingContext
from app.domain.trends import Finding, TrendDetector
from app.services.glucose_service import GlucoseService
from app.services.trend_service import TrendService

PID = 1
DAY = timedelta(days=1)


class RecordingDetector(TrendDetector):
    """Test strategy: records what it receives and returns one finding."""

    def __init__(self):
        self.received = None

    def detect(self, readings):
        self.received = list(readings)
        return [Finding("test", "test finding", tuple(r.id for r in readings))]


@pytest.fixture(name="glucose")
def fixture_glucose() -> GlucoseService:
    return GlucoseService(InMemoryReadingRepository(), clock=fixed_clock)


def _log(glucose, value, age, context=ReadingContext.FASTING):
    return glucose.log_reading(PID, value, NOW - age, context)


# --- FR-TA-02 ------------------------------------------------------------------------------

def test_time_in_range_of_a_known_dataset(glucose):
    for value in (65, 100, 150, 200):          # low, in range, in range, high
        _log(glucose, value, DAY)
    report = TrendService(glucose, []).analyze(PID, 7)
    assert (report.total, report.low, report.in_range, report.high) == (4, 1, 2, 1)
    assert report.time_in_range_percent == 50.0


def test_time_in_range_is_rounded_to_one_decimal(glucose):
    for value in (100, 100, 200):
        _log(glucose, value, DAY)
    assert TrendService(glucose, []).analyze(PID, 7).time_in_range_percent == 66.7


def test_no_readings_gives_no_percentage_instead_of_dividing_by_zero(glucose):
    report = TrendService(glucose, []).analyze(PID, 7)
    assert report.total == 0
    assert report.time_in_range_percent is None


@pytest.mark.parametrize("days", [7, 14, 30])
def test_allowed_periods(glucose, days):
    assert TrendService(glucose, []).analyze(PID, days).days == days


@pytest.mark.parametrize("days", [0, 1, 10, 31, -7])
def test_other_periods_are_rejected(glucose, days):
    with pytest.raises(InvalidReadingError, match="period"):
        TrendService(glucose, []).analyze(PID, days)


def test_period_includes_only_readings_inside_it(glucose):
    inside = _log(glucose, 100, 13 * DAY)
    _log(glucose, 100, 15 * DAY)
    report = TrendService(glucose, []).analyze(PID, 14)
    assert [r.id for r in report.readings] == [inside.id]


# --- Strategy wiring -------------------------------------------------------------------------

def test_every_injected_detector_runs_and_findings_are_collected(glucose):
    _log(glucose, 100, DAY)
    first, second = RecordingDetector(), RecordingDetector()
    report = TrendService(glucose, [first, second]).analyze(PID, 7)
    assert first.received is not None and second.received is not None
    assert len(report.findings) == 2


def test_detectors_only_see_the_last_7_days_even_for_a_30_day_report(glucose):
    recent = _log(glucose, 100, 6 * DAY)
    _log(glucose, 100, 7 * DAY + timedelta(minutes=1))
    _log(glucose, 100, 20 * DAY)
    detector = RecordingDetector()
    report = TrendService(glucose, [detector]).analyze(PID, 30)
    assert [r.id for r in detector.received] == [recent.id]
    assert report.total == 3


def test_reading_exactly_7_days_old_is_inside_the_detection_window(glucose):
    edge = _log(glucose, 100, 7 * DAY)
    detector = RecordingDetector()
    TrendService(glucose, [detector]).analyze(PID, 7)
    assert [r.id for r in detector.received] == [edge.id]
