"""Business rules of module M1 (Glucose Logging, FR-GL-01 to FR-GL-04).

Modules M2 and M3 read glucose data only through this service, never
through M1's table (low coupling, as planned in Milestone 1).
"""

from collections.abc import Callable
from datetime import datetime, timezone

from app.core.exceptions import InvalidReadingError, NotFoundError
from app.core.logging_config import get_logger
from app.domain.glucose import (
    MAX_GLUCOSE_MG_DL,
    MIN_GLUCOSE_MG_DL,
    GlucoseReading,
    ReadingContext,
    ReadingRepository,
)

logger = get_logger("glucose.service")


def utc_now() -> datetime:
    """Current time in UTC (default clock)."""
    return datetime.now(timezone.utc)


def as_utc(moment: datetime) -> datetime:
    """Treat a time without a zone as UTC; convert any other zone to UTC."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


class GlucoseService:
    """Records, validates, lists and deletes glucose readings."""

    def __init__(self, repository: ReadingRepository,
                 clock: Callable[[], datetime] = utc_now) -> None:
        self._repository = repository
        # The clock is injected so tests can fix "now" for the future-date rule.
        self._clock = clock

    def now(self) -> datetime:
        """The service's current time (UTC)."""
        return as_utc(self._clock())

    def log_reading(self, patient_id: int, value_mg_dl: float, measured_at: datetime,
                    context: ReadingContext) -> GlucoseReading:
        """Validate and store a reading (FR-GL-01, FR-GL-02)."""
        if not MIN_GLUCOSE_MG_DL <= value_mg_dl <= MAX_GLUCOSE_MG_DL:
            raise InvalidReadingError(
                f"Glucose must be between {MIN_GLUCOSE_MG_DL} and {MAX_GLUCOSE_MG_DL} mg/dL."
            )
        measured_at = as_utc(measured_at)
        if measured_at > self.now():
            raise InvalidReadingError("A reading cannot be dated in the future.")
        reading = self._repository.add(patient_id, value_mg_dl, measured_at,
                                       ReadingContext(context))
        logger.info("Reading %s stored (%s mg/dL, %s)", reading.id, value_mg_dl, context)
        return reading

    def list_readings(self, patient_id: int, start: datetime | None = None,
                      end: datetime | None = None) -> list[GlucoseReading]:
        """Readings in [start, end], newest first (FR-GL-03)."""
        start = as_utc(start) if start is not None else None
        end = as_utc(end) if end is not None else None
        if start is not None and end is not None and start > end:
            raise InvalidReadingError("The start date must not be after the end date.")
        return self._repository.find_by_patient(patient_id, start, end)

    def delete_reading(self, reading_id: int) -> None:
        """Delete a reading, or raise NotFoundError (FR-GL-04)."""
        if not self._repository.delete(reading_id):
            raise NotFoundError(f"Glucose reading {reading_id} does not exist.")
        logger.info("Reading %s deleted", reading_id)
