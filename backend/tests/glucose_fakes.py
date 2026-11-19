"""In-memory ReadingRepository for unit tests (substitutable for the SQL one)."""

import itertools
from datetime import datetime, timezone

from app.domain.glucose import GlucoseReading, ReadingContext, ReadingRepository

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def fixed_clock() -> datetime:
    """A clock that always returns NOW."""
    return NOW


class InMemoryReadingRepository(ReadingRepository):
    """Stores readings in a dictionary."""

    def __init__(self) -> None:
        self._readings: dict[int, GlucoseReading] = {}
        self._ids = itertools.count(1)

    def add(self, patient_id: int, value_mg_dl: float, measured_at: datetime,
            context: ReadingContext) -> GlucoseReading:
        reading = GlucoseReading(id=next(self._ids), patient_id=patient_id,
                                 value_mg_dl=value_mg_dl, measured_at=measured_at,
                                 context=context)
        self._readings[reading.id] = reading
        return reading

    def get(self, reading_id: int) -> GlucoseReading | None:
        return self._readings.get(reading_id)

    def find_by_patient(self, patient_id: int, start: datetime | None = None,
                        end: datetime | None = None) -> list[GlucoseReading]:
        found = [r for r in self._readings.values()
                 if r.patient_id == patient_id
                 and (start is None or r.measured_at >= start)
                 and (end is None or r.measured_at <= end)]
        return sorted(found, key=lambda r: (r.measured_at, r.id), reverse=True)

    def delete(self, reading_id: int) -> bool:
        return self._readings.pop(reading_id, None) is not None
