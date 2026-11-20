"""Request and response schemas of the foods and meals API (module M3)."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.api.glucose_schemas import ReadingOut
from app.domain.meals import (
    MAX_ITEMS_PER_MEAL,
    MAX_PORTION,
    MIN_PORTION,
    DailyTotal,
    Food,
    Meal,
    MealImpact,
    MealType,
)


class FoodOut(BaseModel):
    """A food from the nutrition table (values per serving)."""

    id: int
    name: str
    serving_description: str
    carbs_g: float
    calories_kcal: float

    @classmethod
    def from_domain(cls, food: Food) -> "FoodOut":
        """Build the response from a domain food."""
        return cls(id=food.id, name=food.name, serving_description=food.serving_description,
                   carbs_g=food.carbs_g, calories_kcal=food.calories_kcal)


class MealItemIn(BaseModel):
    """One food and its portion. Limits give per-field errors (NFR-05, NFR-06)."""

    food_id: int = Field(gt=0)
    portion: float = Field(ge=MIN_PORTION, le=MAX_PORTION)


class MealIn(BaseModel):
    """A new meal."""

    meal_type: MealType
    eaten_at: datetime
    items: list[MealItemIn] = Field(min_length=1, max_length=MAX_ITEMS_PER_MEAL)


class MealItemOut(BaseModel):
    """One item of a stored meal with its computed values."""

    food: FoodOut
    portion: float
    carbs_g: float
    calories_kcal: float


class MealOut(BaseModel):
    """A stored meal with totals (FR-ML-03)."""

    id: int
    meal_type: MealType
    eaten_at: datetime
    items: list[MealItemOut]
    total_carbs_g: float
    total_calories_kcal: float

    @classmethod
    def from_domain(cls, meal: Meal) -> "MealOut":
        """Build the response from a domain meal."""
        return cls(id=meal.id, meal_type=meal.meal_type, eaten_at=meal.eaten_at,
                   items=[MealItemOut(food=FoodOut.from_domain(i.food), portion=i.portion,
                                      carbs_g=i.carbs_g, calories_kcal=i.calories_kcal)
                          for i in meal.items],
                   total_carbs_g=meal.total_carbs_g,
                   total_calories_kcal=meal.total_calories_kcal)


class DailyTotalOut(BaseModel):
    """Totals for one day (FR-ML-04)."""

    day: date
    carbs_g: float
    calories_kcal: float
    meal_count: int

    @classmethod
    def from_domain(cls, total: DailyTotal) -> "DailyTotalOut":
        """Build the response from a domain daily total."""
        return cls(day=total.day, carbs_g=total.carbs_g, calories_kcal=total.calories_kcal,
                   meal_count=total.meal_count)


class MealImpactOut(BaseModel):
    """A meal with its linked after-meal reading (FR-ML-05)."""

    meal: MealOut
    reading: ReadingOut | None
    is_high: bool

    @classmethod
    def from_domain(cls, impact: MealImpact) -> "MealImpactOut":
        """Build the response from a domain meal impact."""
        reading = ReadingOut.from_domain(impact.reading) if impact.reading else None
        return cls(meal=MealOut.from_domain(impact.meal), reading=reading,
                   is_high=impact.is_high)
