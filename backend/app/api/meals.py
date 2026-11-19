"""HTTP endpoints of module M3 (Meal and Nutrition Logging)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.meal_schemas import DailyTotalOut, FoodOut, MealImpactOut, MealIn, MealOut
from app.infrastructure.db.init_db import DEFAULT_PATIENT_ID
from app.services.meal_service import MealService

router = APIRouter(tags=["meals"])


def get_meal_service(request: Request) -> MealService:
    """The MealService created with the application."""
    return request.app.state.meal_service


@router.get("/foods")
def search_foods(
    service: Annotated[MealService, Depends(get_meal_service)],
    q: Annotated[str, Query(description="Part of the food name")] = "",
) -> list[FoodOut]:
    """Autocomplete suggestions from the nutrition table (FR-ML-01)."""
    return [FoodOut.from_domain(f) for f in service.search_foods(q)]


@router.post("/meals", status_code=status.HTTP_201_CREATED)
def log_meal(
    body: MealIn,
    service: Annotated[MealService, Depends(get_meal_service)],
) -> MealOut:
    """Record a meal with its foods and portions (FR-ML-02, FR-ML-03)."""
    meal = service.log_meal(DEFAULT_PATIENT_ID, body.meal_type, body.eaten_at,
                            [(item.food_id, item.portion) for item in body.items])
    return MealOut.from_domain(meal)


@router.get("/meals")
def list_meals(
    service: Annotated[MealService, Depends(get_meal_service)],
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> list[MealOut]:
    """Meals newest first, optionally between start and end."""
    return [MealOut.from_domain(m) for m in service.list_meals(DEFAULT_PATIENT_ID, start, end)]


@router.get("/meals/daily-totals")
def daily_totals(
    service: Annotated[MealService, Depends(get_meal_service)],
    days: Annotated[int, Query()] = 7,
) -> list[DailyTotalOut]:
    """Carbs and calories per day, oldest first (FR-ML-04)."""
    return [DailyTotalOut.from_domain(t) for t in service.daily_totals(DEFAULT_PATIENT_ID, days)]


@router.get("/meals/impact")
def meal_impact(
    service: Annotated[MealService, Depends(get_meal_service)],
    days: Annotated[int, Query()] = 7,
) -> list[MealImpactOut]:
    """Meals with their after-meal reading and a High flag (FR-ML-05)."""
    return [MealImpactOut.from_domain(i) for i in service.meal_impact(DEFAULT_PATIENT_ID, days)]
