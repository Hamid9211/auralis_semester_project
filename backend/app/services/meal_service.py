"""Business rules of module M3 (Meal and Nutrition Logging, FR-ML-01 to FR-ML-05).

Glucose readings are read only through GlucoseService (low coupling, as planned
in Milestone 1); MealService never touches the glucose table.
"""

from collections.abc import Sequence
from datetime import datetime

from app.core.exceptions import InvalidMealError
from app.core.logging_config import get_logger
from app.domain.meals import (
    MAX_ITEMS_PER_MEAL,
    MAX_PORTION,
    MIN_PORTION,
    Food,
    FoodRepository,
    Meal,
    MealItem,
    MealRepository,
    MealType,
)
from app.services.glucose_service import GlucoseService, as_utc

logger = get_logger("meals.service")

SEARCH_LIMIT = 10
MAX_SEARCH_LENGTH = 50


class MealService:
    """Searches foods and logs meals."""

    def __init__(self, meals: MealRepository, foods: FoodRepository,
                 glucose: GlucoseService) -> None:
        self._meals = meals
        self._foods = foods
        self._glucose = glucose

    # --- FR-ML-01 ------------------------------------------------------------------

    def search_foods(self, text: str) -> list[Food]:
        """Up to 10 foods whose name contains the text."""
        query = (text or "").strip()
        if not query:
            raise InvalidMealError("Type at least one character to search.")
        if len(query) > MAX_SEARCH_LENGTH:
            raise InvalidMealError(f"Search text is longer than {MAX_SEARCH_LENGTH} characters.")
        return self._foods.search(query, SEARCH_LIMIT)

    # --- FR-ML-02 / FR-ML-03 ---------------------------------------------------------

    def log_meal(self, patient_id: int, meal_type: MealType, eaten_at: datetime,
                 items: Sequence[tuple[int, float]]) -> Meal:
        """Validate and store a meal given as (food_id, portion) pairs."""
        if not items:
            raise InvalidMealError("A meal needs at least one food.")
        if len(items) > MAX_ITEMS_PER_MEAL:
            raise InvalidMealError(f"A meal can have at most {MAX_ITEMS_PER_MEAL} foods.")
        eaten_at = as_utc(eaten_at)
        if eaten_at > self._glucose.now():
            raise InvalidMealError("A meal cannot be dated in the future.")
        meal_items = [self._item(food_id, portion) for food_id, portion in items]
        meal = self._meals.add(patient_id, MealType(meal_type), eaten_at, meal_items)
        logger.info("Meal %s stored (%d items, %.1f g carbs)", meal.id, len(meal.items),
                    meal.total_carbs_g)
        return meal

    def list_meals(self, patient_id: int, start: datetime | None = None,
                   end: datetime | None = None) -> list[Meal]:
        """Meals in [start, end], newest first."""
        return self._meals.find_by_patient(patient_id,
                                           as_utc(start) if start else None,
                                           as_utc(end) if end else None)

    def _item(self, food_id: int, portion: float) -> MealItem:
        if not MIN_PORTION <= portion <= MAX_PORTION:
            raise InvalidMealError(
                f"Portion must be between {MIN_PORTION:g} and {MAX_PORTION:g} servings.")
        food = self._foods.get(food_id)
        if food is None:
            raise InvalidMealError(f"Food {food_id} is not in the nutrition table.")
        return MealItem(food=food, portion=portion)
