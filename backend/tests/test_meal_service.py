"""FR-ML-01 and FR-ML-02: food search and meal validation (EP + BVA on portion)."""

from datetime import timedelta

import pytest
from glucose_fakes import NOW, InMemoryReadingRepository, fixed_clock
from meal_fakes import InMemoryFoodRepository, InMemoryMealRepository

from app.core.exceptions import InvalidMealError, InvalidReadingError
from app.domain.meals import MAX_ITEMS_PER_MEAL, MealType
from app.services.glucose_service import GlucoseService
from app.services.meal_service import SEARCH_LIMIT, MealService

PID = 1
LUNCH = MealType.LUNCH
HOUR = timedelta(hours=1)


@pytest.fixture(name="foods")
def fixture_foods() -> InMemoryFoodRepository:
    return InMemoryFoodRepository()


@pytest.fixture(name="service")
def fixture_service(foods) -> MealService:
    glucose = GlucoseService(InMemoryReadingRepository(), clock=fixed_clock)
    return MealService(InMemoryMealRepository(), foods, glucose)


# --- FR-ML-01: search ------------------------------------------------------------------

def test_search_finds_partial_matches_in_name_order(service):
    assert [f.name for f in service.search_foods("rice")] == [
        "Brown rice, cooked", "Rice, white, cooked"]


def test_search_ignores_case_and_surrounding_spaces(service):
    assert [f.id for f in service.search_foods("  ROTI ")] == [2]


def test_search_without_match_gives_empty_list(service):
    assert not service.search_foods("pizza")


def test_search_asks_the_repository_for_at_most_10_results(service, foods):
    service.search_foods("r")
    assert foods.searches[-1] == ("r", SEARCH_LIMIT)


@pytest.mark.parametrize("text", ["", "   ", None])
def test_empty_search_is_rejected(service, text):
    with pytest.raises(InvalidMealError, match="at least one character"):
        service.search_foods(text)


def test_search_of_51_characters_is_rejected(service):
    with pytest.raises(InvalidMealError, match="longer than 50"):
        service.search_foods("a" * 51)


def test_search_of_50_characters_is_allowed(service):
    assert not service.search_foods("a" * 50)


# --- FR-ML-02: portion, boundary value analysis ---------------------------------------------

@pytest.mark.parametrize("portion", [0.5, 1.0, 3.0])
def test_portions_inside_the_range_are_accepted(service, portion):
    meal = service.log_meal(PID, LUNCH, NOW - HOUR, [(1, portion)])
    assert meal.items[0].portion == portion


@pytest.mark.parametrize("portion", [0.4, 0.49, 3.01, 3.1, 0, -1])
def test_portions_outside_the_range_are_rejected(service, portion):
    with pytest.raises(InvalidMealError, match="between 0.5 and 3"):
        service.log_meal(PID, LUNCH, NOW - HOUR, [(1, portion)])


# --- FR-ML-02: other inputs ---------------------------------------------------------------------

def test_valid_meal_is_stored_with_items_and_totals(service):
    meal = service.log_meal(PID, LUNCH, NOW - HOUR, [(1, 1.0), (3, 0.5)])
    assert meal.meal_type is LUNCH
    assert [i.food.id for i in meal.items] == [1, 3]
    assert meal.total_carbs_g == 65.0
    assert service.list_meals(PID)[0].id == meal.id


def test_meal_without_foods_is_rejected(service):
    with pytest.raises(InvalidMealError, match="at least one food"):
        service.log_meal(PID, LUNCH, NOW - HOUR, [])


def test_meal_with_20_foods_is_accepted_and_21_rejected(service):
    assert len(service.log_meal(PID, LUNCH, NOW, [(1, 1.0)] * MAX_ITEMS_PER_MEAL).items) == 20
    with pytest.raises(InvalidMealError, match="at most 20"):
        service.log_meal(PID, LUNCH, NOW, [(1, 1.0)] * (MAX_ITEMS_PER_MEAL + 1))


def test_unknown_food_is_rejected_and_nothing_is_stored(service):
    with pytest.raises(InvalidMealError, match="Food 99"):
        service.log_meal(PID, LUNCH, NOW - HOUR, [(1, 1.0), (99, 1.0)])
    assert not service.list_meals(PID)


def test_meal_in_the_future_is_rejected(service):
    with pytest.raises(InvalidMealError, match="future"):
        service.log_meal(PID, LUNCH, NOW + timedelta(minutes=1), [(1, 1.0)])


def test_meal_type_given_as_text_is_converted(service):
    assert service.log_meal(PID, "snack", NOW, [(2, 1.0)]).meal_type is MealType.SNACK


def test_invalid_meal_error_is_a_kind_of_invalid_reading_error():
    # So it maps to HTTP 422 through the existing error table, without editing it.
    assert issubclass(InvalidMealError, InvalidReadingError)


def test_list_meals_filters_by_range(service):
    old = service.log_meal(PID, LUNCH, NOW - 5 * HOUR, [(1, 1.0)])
    service.log_meal(PID, LUNCH, NOW - HOUR, [(1, 1.0)])
    found = service.list_meals(PID, start=NOW - 6 * HOUR, end=NOW - 4 * HOUR)
    assert [m.id for m in found] == [old.id]
