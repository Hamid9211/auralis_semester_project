"""FR-ML-04 daily totals and FR-ML-05 meal-glucose linking (BVA 119, 120, 121 min)."""

from datetime import timedelta

import pytest
from glucose_fakes import NOW, InMemoryReadingRepository, fixed_clock
from meal_fakes import InMemoryFoodRepository, InMemoryMealRepository

from app.core.exceptions import InvalidMealError
from app.domain.glucose import ReadingContext
from app.domain.meals import MealType
from app.services.glucose_service import GlucoseService
from app.services.meal_service import MealService

PID = 1
AFTER = ReadingContext.AFTER_MEAL
MINUTE = timedelta(minutes=1)
DAY = timedelta(days=1)


class Setup:
    """A MealService with a GlucoseService on in-memory data."""

    def __init__(self):
        self.glucose = GlucoseService(InMemoryReadingRepository(), clock=fixed_clock)
        self.meals = MealService(InMemoryMealRepository(), InMemoryFoodRepository(),
                                 self.glucose)

    def meal(self, age, portion=1.0, food_id=1):
        return self.meals.log_meal(PID, MealType.LUNCH, NOW - age, [(food_id, portion)])

    def reading(self, at, value=150, context=AFTER):
        return self.glucose.log_reading(PID, value, at, context)


@pytest.fixture(name="s")
def fixture_setup() -> Setup:
    return Setup()


# --- FR-ML-04 ----------------------------------------------------------------------------

def test_daily_totals_cover_7_days_oldest_first_with_zero_days(s):
    totals = s.meals.daily_totals(PID)
    assert len(totals) == 7
    assert totals[-1].day == NOW.date()
    assert totals[0].day == NOW.date() - 6 * DAY
    assert all(t.carbs_g == 0 and t.meal_count == 0 for t in totals)


def test_meals_are_added_up_per_day(s):
    s.meal(timedelta(hours=1))                  # today, rice 45 g
    s.meal(timedelta(hours=2), portion=0.5)     # today, 22.5 g
    s.meal(DAY, food_id=2)                      # yesterday, roti 18 g
    totals = s.meals.daily_totals(PID)
    assert (totals[-1].carbs_g, totals[-1].calories_kcal, totals[-1].meal_count) == \
        (67.5, 307.5, 2)
    assert totals[-2].carbs_g == 18.0


def test_meal_older_than_the_period_is_not_counted(s):
    s.meal(7 * DAY)
    assert sum(t.meal_count for t in s.meals.daily_totals(PID)) == 0


@pytest.mark.parametrize("days", [0, 31, -1])
def test_period_outside_1_to_30_days_is_rejected(s, days):
    with pytest.raises(InvalidMealError, match="period"):
        s.meals.daily_totals(PID, days)


def test_period_of_1_and_30_days_is_allowed(s):
    assert len(s.meals.daily_totals(PID, 1)) == 1
    assert len(s.meals.daily_totals(PID, 30)) == 30


# --- FR-ML-05: link window, boundary value analysis ----------------------------------------

@pytest.mark.parametrize(("minutes", "linked"), [(1, True), (119, True), (120, True),
                                                 (121, False)])
def test_after_meal_reading_is_linked_up_to_120_minutes(s, minutes, linked):
    meal = s.meal(timedelta(hours=5))
    reading = s.reading(meal.eaten_at + minutes * MINUTE)
    impact = s.meals.meal_impact(PID)[0]
    assert (impact.reading == reading) is linked


def test_reading_at_the_same_time_as_the_meal_is_not_linked(s):
    meal = s.meal(timedelta(hours=5))
    s.reading(meal.eaten_at)
    assert s.meals.meal_impact(PID)[0].reading is None


def test_reading_before_the_meal_is_not_linked(s):
    meal = s.meal(timedelta(hours=5))
    s.reading(meal.eaten_at - 10 * MINUTE)
    assert s.meals.meal_impact(PID)[0].reading is None


def test_reading_in_another_context_is_not_linked(s):
    meal = s.meal(timedelta(hours=5))
    s.reading(meal.eaten_at + 30 * MINUTE, context=ReadingContext.BEDTIME)
    assert s.meals.meal_impact(PID)[0].reading is None


def test_earliest_reading_in_the_window_is_used(s):
    meal = s.meal(timedelta(hours=5))
    s.reading(meal.eaten_at + 90 * MINUTE)
    first = s.reading(meal.eaten_at + 30 * MINUTE)
    assert s.meals.meal_impact(PID)[0].reading == first


@pytest.mark.parametrize(("value", "high"), [(180, False), (181, True)])
def test_meal_followed_by_a_high_reading_is_flagged(s, value, high):
    meal = s.meal(timedelta(hours=5))
    s.reading(meal.eaten_at + 60 * MINUTE, value=value)
    assert s.meals.meal_impact(PID)[0].is_high is high


def test_meal_without_reading_is_not_flagged(s):
    s.meal(timedelta(hours=5))
    impact = s.meals.meal_impact(PID)[0]
    assert impact.reading is None and impact.is_high is False


def test_impact_only_includes_meals_of_the_period(s):
    s.meal(8 * DAY)
    recent = s.meal(DAY)
    assert [i.meal.id for i in s.meals.meal_impact(PID, 7)] == [recent.id]
