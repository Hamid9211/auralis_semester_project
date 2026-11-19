"""FR-TA-03 and FR-TA-04: pattern detectors (EP + BVA on counts and time windows)."""

from datetime import datetime, timedelta, timezone

from app.domain.glucose import GlucoseReading, ReadingContext
from app.services.trend_detectors import (
    POST_MEAL_HIGHS,
    TIME_OF_DAY_LOWS,
    PostMealHighDetector,
    TimeOfDayLowDetector,
)

AFTER = ReadingContext.AFTER_MEAL
BEFORE = ReadingContext.BEFORE_MEAL
BASE = datetime(2026, 11, 12, 8, 0, tzinfo=timezone.utc)


def _readings(*specs):
    """specs: (value, context, minutes after BASE). Each reading is on a different day."""
    return [GlucoseReading(id=i, patient_id=1, value_mg_dl=value,
                           measured_at=BASE + timedelta(days=i, minutes=minutes),
                           context=context)
            for i, (value, context, minutes) in enumerate(specs, start=1)]


# --- FR-TA-03: post-meal highs ------------------------------------------------------------

def test_two_post_meal_highs_are_not_flagged():
    assert not PostMealHighDetector().detect(_readings((200, AFTER, 0), (220, AFTER, 0)))


def test_three_post_meal_highs_are_flagged():
    findings = PostMealHighDetector().detect(
        _readings((200, AFTER, 0), (220, AFTER, 0), (181, AFTER, 0)))
    assert len(findings) == 1
    assert findings[0].code == POST_MEAL_HIGHS
    assert findings[0].reading_ids == (1, 2, 3)
    assert findings[0].message.startswith("3 of your after-meal readings")


def test_180_is_in_range_so_it_does_not_count():
    readings = _readings((200, AFTER, 0), (220, AFTER, 0), (180, AFTER, 0))
    assert not PostMealHighDetector().detect(readings)


def test_highs_in_other_contexts_do_not_count():
    readings = _readings((200, AFTER, 0), (220, AFTER, 0), (250, BEFORE, 0))
    assert not PostMealHighDetector().detect(readings)


def test_post_meal_threshold_is_configurable():
    assert len(PostMealHighDetector(min_count=1).detect(_readings((200, AFTER, 0)))) == 1


# --- FR-TA-04: time-of-day lows --------------------------------------------------------------

def test_one_low_is_not_flagged():
    assert not TimeOfDayLowDetector().detect(_readings((60, BEFORE, 0)))


def test_69_is_low_but_70_is_not():
    assert len(TimeOfDayLowDetector().detect(_readings((69, BEFORE, 0), (69, BEFORE, 30)))) == 1
    assert not TimeOfDayLowDetector().detect(_readings((69, BEFORE, 0), (70, BEFORE, 30)))


def test_two_lows_179_minutes_apart_are_flagged():
    findings = TimeOfDayLowDetector().detect(_readings((60, BEFORE, 0), (60, BEFORE, 179)))
    assert findings[0].code == TIME_OF_DAY_LOWS
    assert findings[0].reading_ids == (1, 2)


def test_two_lows_exactly_180_minutes_apart_are_flagged():
    assert len(TimeOfDayLowDetector().detect(_readings((60, BEFORE, 0), (60, BEFORE, 180)))) == 1


def test_two_lows_181_minutes_apart_are_not_flagged():
    assert not TimeOfDayLowDetector().detect(_readings((60, BEFORE, 0), (60, BEFORE, 181)))


def test_window_can_cross_midnight():
    # 23:30 and 01:00 on different days are 90 clock minutes apart.
    late = 15 * 60 + 30       # BASE is 08:00, so +930 min = 23:30
    early = 17 * 60           # +1020 min = 01:00 the next day
    findings = TimeOfDayLowDetector().detect(_readings((60, BEFORE, late), (60, BEFORE, early)))
    assert len(findings) == 1


def test_largest_group_is_reported():
    readings = _readings((60, BEFORE, 0), (60, BEFORE, 60), (60, BEFORE, 120),
                         (60, BEFORE, 600))
    findings = TimeOfDayLowDetector().detect(readings)
    assert findings[0].reading_ids == (1, 2, 3)
    assert findings[0].message.startswith("3 low readings")


def test_no_readings_gives_no_findings():
    assert not PostMealHighDetector().detect([])
    assert not TimeOfDayLowDetector().detect([])
