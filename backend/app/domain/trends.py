"""Domain model of module M2 (Health Trend Analysis): levels, findings, detector interface."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.glucose import GlucoseReading

# FR-TA-01 thresholds (mg/dL). Named constants, so the boundaries are defined in one place.
LOW_BELOW_MG_DL = 70     # Low: value < 70
HIGH_ABOVE_MG_DL = 180   # High: value > 180; In range: 70 to 180 inclusive


class GlucoseLevel(StrEnum):
    """Classification of one reading."""

    LOW = "low"
    IN_RANGE = "in_range"
    HIGH = "high"


def classify(value_mg_dl: float) -> GlucoseLevel:
    """Classify a glucose value (FR-TA-01)."""
    if value_mg_dl < LOW_BELOW_MG_DL:
        return GlucoseLevel.LOW
    if value_mg_dl > HIGH_ABOVE_MG_DL:
        return GlucoseLevel.HIGH
    return GlucoseLevel.IN_RANGE


@dataclass(frozen=True)
class Finding:
    """A pattern found in the readings, with guidance for the patient (FR-TA-05)."""

    code: str
    message: str
    reading_ids: tuple[int, ...]


@dataclass(frozen=True)
class TrendReport:
    """Result of analysing a patient's readings over a period."""

    days: int
    total: int
    low: int
    in_range: int
    high: int
    time_in_range_percent: float | None
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    readings: tuple[GlucoseReading, ...] = field(default_factory=tuple)


class TrendDetector(ABC):
    """One pattern check (Strategy). TrendService runs every detector it is given."""

    @abstractmethod
    def detect(self, readings: Sequence[GlucoseReading]) -> list[Finding]:
        """Return the findings of this check for the given readings (last 7 days)."""
