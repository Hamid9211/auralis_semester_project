"""In-memory Food and Meal repositories for unit tests (substitutable for the SQL ones)."""

import itertools
from datetime import datetime

from app.domain.meals import Food, FoodRepository, Meal, MealItem, MealRepository, MealType

FOODS = [
    Food(1, "Rice, white, cooked", "1 cup (158 g)", 45.0, 205.0),
    Food(2, "Roti (chapati)", "1 medium (40 g)", 18.0, 120.0),
    Food(3, "Daal (lentils), cooked", "1 cup (198 g)", 40.0, 230.0),
    Food(4, "Brown rice, cooked", "1 cup (195 g)", 45.0, 216.0),
]


class InMemoryFoodRepository(FoodRepository):
    """A fixed nutrition table."""

    def __init__(self, foods=None) -> None:
        self._foods = {f.id: f for f in (foods or FOODS)}
        self.searches: list[tuple[str, int]] = []

    def search(self, text: str, limit: int) -> list[Food]:
        self.searches.append((text, limit))
        found = [f for f in self._foods.values() if text.lower() in f.name.lower()]
        return sorted(found, key=lambda f: f.name)[:limit]

    def get(self, food_id: int) -> Food | None:
        return self._foods.get(food_id)


class InMemoryMealRepository(MealRepository):
    """Stores meals in a dictionary."""

    def __init__(self) -> None:
        self._meals: dict[int, Meal] = {}
        self._ids = itertools.count(1)

    def add(self, patient_id: int, meal_type: MealType, eaten_at: datetime,
            items: list[MealItem]) -> Meal:
        meal = Meal(id=next(self._ids), patient_id=patient_id, meal_type=meal_type,
                    eaten_at=eaten_at, items=tuple(items))
        self._meals[meal.id] = meal
        return meal

    def find_by_patient(self, patient_id: int, start: datetime | None = None,
                        end: datetime | None = None) -> list[Meal]:
        found = [m for m in self._meals.values()
                 if m.patient_id == patient_id
                 and (start is None or m.eaten_at >= start)
                 and (end is None or m.eaten_at <= end)]
        return sorted(found, key=lambda m: (m.eaten_at, m.id), reverse=True)
