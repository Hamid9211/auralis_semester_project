"""Domain model and interface of module M1 (Glucose Logging).

No framework or library imports: services depend on ReadingRepository,
the infrastructure layer implements it (Dependency Inversion).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# FR-GL-02: accepted measurement range. Also enforced by a database CHECK constraint.
MIN_GLUCOSE_MG_DL = 20
MAX_GLUCOSE_MG_DL = 600


class ReadingContext(StrEnum):
    """When the reading was taken (FR-GL-01)."""

    FASTING = "fasting"
    BEFORE_MEAL = "before_meal"
    AFTER_MEAL = "after_meal"
    BEDTIME = "bedtime"


@dataclass(frozen=True)
class GlucoseReading:
    """One stored glucose measurement. Frozen, so other modules cannot change it."""

    id: int
    patient_id: int
    value_mg_dl: float
    measured_at: datetime
    context: ReadingContext


class ReadingRepository(ABC):
    """Storage of glucose readings."""

    @abstractmethod
    def add(self, patient_id: int, value_mg_dl: float, measured_at: datetime,
            context: ReadingContext) -> GlucoseReading:
        """Store a reading and return it with its id."""

    @abstractmethod
    def get(self, reading_id: int) -> GlucoseReading | None:
        """Return one reading or None."""

    @abstractmethod
    def find_by_patient(self, patient_id: int, start: datetime | None = None,
                        end: datetime | None = None) -> list[GlucoseReading]:
        """Return the patient's readings in [start, end], newest first."""

    @abstractmethod
    def delete(self, reading_id: int) -> bool:
        """Delete a reading; return False if it did not exist."""
