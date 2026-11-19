"""Health trend analysis (module M2, FR-TA-01 to FR-TA-04).

TrendService reads glucose data only through GlucoseService (not M1's table)
and delegates each pattern check to a TrendDetector strategy.
"""

from collections.abc import Sequence
from datetime import timedelta

from app.core.exceptions import InvalidReadingError
from app.domain.glucose import GlucoseReading
from app.domain.trends import Finding, GlucoseLevel, TrendDetector, TrendReport, classify
from app.services.glucose_service import GlucoseService

ALLOWED_PERIODS_DAYS = (7, 14, 30)   # FR-TA-02
DETECTION_WINDOW_DAYS = 7            # FR-TA-03, FR-TA-04


class TrendService:
    """Computes time in range and runs the pattern detectors."""

    def __init__(self, glucose: GlucoseService, detectors: Sequence[TrendDetector]) -> None:
        self._glucose = glucose
        self._detectors = tuple(detectors)

    def analyze(self, patient_id: int, days: int) -> TrendReport:
        """Classify the period's readings, compute time in range and detect patterns."""
        if days not in ALLOWED_PERIODS_DAYS:
            raise InvalidReadingError(f"The period must be one of {ALLOWED_PERIODS_DAYS} days.")
        now = self._glucose.now()
        readings = self._glucose.list_readings(patient_id, start=now - timedelta(days=days),
                                               end=now)
        levels = [classify(r.value_mg_dl) for r in readings]
        window_start = now - timedelta(days=DETECTION_WINDOW_DAYS)
        recent = [r for r in readings if r.measured_at >= window_start]
        return TrendReport(
            days=days,
            total=len(readings),
            low=levels.count(GlucoseLevel.LOW),
            in_range=levels.count(GlucoseLevel.IN_RANGE),
            high=levels.count(GlucoseLevel.HIGH),
            time_in_range_percent=self.time_in_range(readings),
            findings=tuple(self._detect(recent)),
            readings=tuple(readings),
        )

    @staticmethod
    def time_in_range(readings: Sequence[GlucoseReading]) -> float | None:
        """Percentage of readings In Range, rounded to 1 decimal; None if there are none."""
        if not readings:
            return None
        in_range = sum(1 for r in readings
                       if classify(r.value_mg_dl) is GlucoseLevel.IN_RANGE)
        return round(100 * in_range / len(readings), 1)

    def _detect(self, readings: Sequence[GlucoseReading]) -> list[Finding]:
        findings: list[Finding] = []
        for detector in self._detectors:
            findings.extend(detector.detect(readings))
        return findings
