"""SQL food and meal repositories, and the nutrition table seed."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.domain.meals import MealItem, MealType
from app.infrastructure.db.init_db import DEFAULT_PATIENT_ID, init_database
from app.infrastructure.db.meal_repository import SqlFoodRepository, SqlMealRepository
from app.infrastructure.db.nutrition_seed import FOODS, seed_foods
from app.infrastructure.db.session import create_db_engine, create_session_factory

PID = DEFAULT_PATIENT_ID
T0 = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)


@pytest.fixture(name="engine")
def fixture_engine():
    engine = create_db_engine("sqlite://")
    init_database(engine)
    yield engine
    engine.dispose()


@pytest.fixture(name="foods")
def fixture_foods(engine):
    return SqlFoodRepository(create_session_factory(engine))


@pytest.fixture(name="meals")
def fixture_meals(engine):
    return SqlMealRepository(create_session_factory(engine))


# --- Seed ---------------------------------------------------------------------------------

def test_database_starts_with_the_whole_nutrition_table(foods):
    assert len(foods.search("", 100)) == len(FOODS)


def test_seeding_again_adds_nothing(engine):
    with Session(engine) as session:
        assert seed_foods(session) == 0


def test_seed_values_are_never_negative():
    assert all(carbs >= 0 and kcal >= 0 for _, _, carbs, kcal in FOODS)


# --- FoodRepository -------------------------------------------------------------------------

def test_search_is_case_insensitive_and_sorted(foods):
    assert [f.name for f in foods.search("RICE", 10)] == [
        "Brown rice, cooked", "Rice, white, cooked"]


def test_search_respects_the_limit(foods):
    assert len(foods.search("a", 3)) == 3


def test_percent_sign_is_not_a_wildcard(foods):
    assert not foods.search("%", 10)


def test_get_food_and_unknown_food(foods):
    rice = foods.search("Rice, white", 1)[0]
    assert foods.get(rice.id) == rice
    assert foods.get(9999) is None


# --- MealRepository -------------------------------------------------------------------------

def test_add_meal_round_trip_with_items_and_totals(foods, meals):
    rice, roti = foods.search("Rice, white", 1)[0], foods.search("Roti", 1)[0]
    added = meals.add(PID, MealType.DINNER, T0, [MealItem(rice, 1.5), MealItem(roti, 2.0)])
    stored = meals.find_by_patient(PID)[0]
    assert stored == added
    assert stored.eaten_at == T0
    assert stored.total_carbs_g == 45.0 * 1.5 + 18.0 * 2


def test_find_by_patient_newest_first_and_by_range(foods, meals):
    rice = foods.search("Rice, white", 1)[0]
    ids = [meals.add(PID, MealType.LUNCH, T0 + timedelta(hours=i), [MealItem(rice, 1)]).id
           for i in range(3)]
    assert [m.id for m in meals.find_by_patient(PID)] == ids[::-1]
    window = meals.find_by_patient(PID, start=T0 + timedelta(hours=1),
                                   end=T0 + timedelta(hours=1))
    assert [m.id for m in window] == [ids[1]]


def test_time_in_another_zone_is_stored_as_utc(foods, meals):
    rice = foods.search("Rice, white", 1)[0]
    pakistan = timezone(timedelta(hours=5))
    meals.add(PID, MealType.LUNCH, T0.astimezone(pakistan), [MealItem(rice, 1)])
    assert meals.find_by_patient(PID)[0].eaten_at == T0


def test_no_meals_for_another_patient(meals):
    assert not meals.find_by_patient(42)


def test_time_without_zone_is_taken_as_utc(foods, meals):
    rice = foods.search("Rice, white", 1)[0]
    meals.add(PID, MealType.LUNCH, T0.replace(tzinfo=None), [MealItem(rice, 1)])
    assert meals.find_by_patient(PID)[0].eaten_at == T0
