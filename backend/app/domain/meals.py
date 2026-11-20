"""Domain model and interfaces of module M3 (Meal and Nutrition Logging).

No framework or library imports. FoodRepository (read-only search) is kept
separate from MealRepository (writes meals), so code that only searches foods
does not depend on meal-writing methods (Interface Segregation).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from app.domain.glucose import GlucoseReading

# FR-ML-02: allowed portion, as a multiple of the food's serving. Also a DB CHECK constraint.
MIN_PORTION = 0.5
MAX_PORTION = 3.0
MAX_ITEMS_PER_MEAL = 20
# FR-ML-05: an after-meal reading is linked to a meal if taken within this time after it.
LINK_WINDOW_MINUTES = 120


class MealType(StrEnum):
    """Kind of meal (FR-ML-02)."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


def _round1(value: float) -> float:
    return round(value, 1)


@dataclass(frozen=True)
class Food:
    """A food from the nutrition table, with values for one serving."""

    id: int
    name: str
    serving_description: str
    carbs_g: float
    calories_kcal: float


@dataclass(frozen=True)
class MealItem:
    """One food and its portion (number of servings) in a meal."""

    food: Food
    portion: float

    @property
    def carbs_g(self) -> float:
        """Carbohydrates of this item (FR-ML-03)."""
        return _round1(self.food.carbs_g * self.portion)

    @property
    def calories_kcal(self) -> float:
        """Calories of this item (FR-ML-03)."""
        return _round1(self.food.calories_kcal * self.portion)


@dataclass(frozen=True)
class Meal:
    """A logged meal. Totals are computed from the items, never stored (NFR-01)."""

    id: int
    patient_id: int
    meal_type: MealType
    eaten_at: datetime
    items: tuple[MealItem, ...] = field(default_factory=tuple)

    @property
    def total_carbs_g(self) -> float:
        """Sum of item carbohydrates (FR-ML-03)."""
        return _round1(sum(item.food.carbs_g * item.portion for item in self.items))

    @property
    def total_calories_kcal(self) -> float:
        """Sum of item calories (FR-ML-03)."""
        return _round1(sum(item.food.calories_kcal * item.portion for item in self.items))


@dataclass(frozen=True)
class DailyTotal:
    """Carbohydrates and calories eaten on one day (FR-ML-04)."""

    day: date
    carbs_g: float
    calories_kcal: float
    meal_count: int


@dataclass(frozen=True)
class MealImpact:
    """A meal with the after-meal reading linked to it, if any (FR-ML-05)."""

    meal: Meal
    reading: GlucoseReading | None
    is_high: bool


class FoodRepository(ABC):
    """Read-only access to the nutrition table."""

    @abstractmethod
    def search(self, text: str, limit: int) -> list[Food]:
        """Foods whose name contains the text (case-insensitive), sorted by name."""

    @abstractmethod
    def get(self, food_id: int) -> Food | None:
        """One food or None."""


class MealRepository(ABC):
    """Storage of meals."""

    @abstractmethod
    def add(self, patient_id: int, meal_type: MealType, eaten_at: datetime,
            items: list[MealItem]) -> Meal:
        """Store a meal and its items; return it with its id."""

    @abstractmethod
    def find_by_patient(self, patient_id: int, start: datetime | None = None,
                        end: datetime | None = None) -> list[Meal]:
        """The patient's meals in [start, end], newest first."""
