"""Concrete TrendDetector strategies (FR-TA-03, FR-TA-04).

Each pattern is its own class with its own thresholds. A new pattern is added
by writing a new detector and passing it to TrendService; no existing class
changes (Open/Closed).
"""

from collections.abc import Sequence

from app.domain.glucose import GlucoseReading, ReadingContext
from app.domain.trends import Finding, GlucoseLevel, TrendDetector, classify

MINUTES_PER_DAY = 24 * 60

POST_MEAL_HIGHS = "post_meal_highs"
TIME_OF_DAY_LOWS = "time_of_day_lows"


class PostMealHighDetector(TrendDetector):
    """Flags 3 or more High after-meal readings (FR-TA-03)."""

    def __init__(self, min_count: int = 3) -> None:
        self._min_count = min_count

    def detect(self, readings: Sequence[GlucoseReading]) -> list[Finding]:
        """Return one finding when enough after-meal readings are High."""
        highs = [r for r in readings
                 if r.context is ReadingContext.AFTER_MEAL
                 and classify(r.value_mg_dl) is GlucoseLevel.HIGH]
        if len(highs) < self._min_count:
            return []
        message = (f"{len(highs)} of your after-meal readings in the last 7 days were above "
                   "180 mg/dL. Look at what you ate before them and discuss it with your doctor.")
        return [Finding(POST_MEAL_HIGHS, message, tuple(r.id for r in highs))]


class TimeOfDayLowDetector(TrendDetector):
    """Flags 2 or more Low readings at a similar time of day (FR-TA-04).

    "Similar time" means within a window of `window_minutes` on the clock,
    whatever the date; a window may cross midnight (23:30 and 01:00).
    """

    def __init__(self, min_count: int = 2, window_minutes: int = 180) -> None:
        self._min_count = min_count
        self._window_minutes = window_minutes

    def detect(self, readings: Sequence[GlucoseReading]) -> list[Finding]:
        """Return one finding for the largest group of lows inside one window."""
        lows = [r for r in readings if classify(r.value_mg_dl) is GlucoseLevel.LOW]
        best: list[GlucoseReading] = []
        for start in lows:
            group = [r for r in lows
                     if _minutes_after(start, r) <= self._window_minutes]
            if len(group) > len(best):
                best = group
        if len(best) < self._min_count:
            return []
        message = (f"{len(best)} low readings in the last 7 days happened at a similar time of "
                   "day (within 3 hours). Consider a snack or ask your doctor about this time.")
        return [Finding(TIME_OF_DAY_LOWS, message, tuple(sorted(r.id for r in best)))]


def _minute_of_day(reading: GlucoseReading) -> int:
    return reading.measured_at.hour * 60 + reading.measured_at.minute


def _minutes_after(start: GlucoseReading, other: GlucoseReading) -> int:
    """Clock minutes from `start` forward to `other`, wrapping past midnight."""
    return (_minute_of_day(other) - _minute_of_day(start)) % MINUTES_PER_DAY
