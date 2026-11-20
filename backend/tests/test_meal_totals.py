"""FR-ML-03 / NFR-01: meal totals equal the sum of item value x portion."""

from datetime import datetime, timezone

import pytest

from app.domain.meals import Food, Meal, MealItem, MealType

RICE = Food(1, "Rice, white, cooked", "1 cup (158 g)", 45.0, 205.0)
DAAL = Food(2, "Daal (lentils), cooked", "1 cup (198 g)", 40.0, 230.0)
EGG = Food(3, "Egg, boiled", "1 large", 0.6, 78.0)
EATEN = datetime(2026, 11, 19, 13, 0, tzinfo=timezone.utc)


def _meal(*items: MealItem) -> Meal:
    return Meal(id=1, patient_id=1, meal_type=MealType.LUNCH, eaten_at=EATEN, items=items)


@pytest.mark.parametrize(
    ("portion", "carbs", "calories"),
    [(0.5, 22.5, 102.5), (1.0, 45.0, 205.0), (1.5, 67.5, 307.5), (3.0, 135.0, 615.0)],
)
def test_item_values_scale_with_portion(portion, carbs, calories):
    item = MealItem(RICE, portion)
    assert item.carbs_g == carbs
    assert item.calories_kcal == calories


def test_meal_totals_are_the_sum_of_its_items():
    meal = _meal(MealItem(RICE, 1.0), MealItem(DAAL, 0.5), MealItem(EGG, 2.0))
    assert meal.total_carbs_g == pytest.approx(66.2)
    assert meal.total_calories_kcal == pytest.approx(476.0)


def test_totals_are_rounded_once_not_per_item():
    # 3 x 0.33 = 0.99 -> 1.0; rounding each item first would give 0.9.
    snack = Food(4, "Seeds", "1 tbsp", 0.33, 0.33)
    meal = _meal(MealItem(snack, 1.0), MealItem(snack, 1.0), MealItem(snack, 1.0))
    assert meal.total_carbs_g == 1.0


def test_meal_without_items_has_zero_totals():
    assert _meal().total_carbs_g == 0
    assert _meal().total_calories_kcal == 0


def test_meal_is_immutable():
    with pytest.raises(AttributeError):
        _meal().meal_type = MealType.DINNER  # type: ignore[misc]
