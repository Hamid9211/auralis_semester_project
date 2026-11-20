"""Nutrition table seed data (risk R5).

Values are per serving, rounded, from USDA FoodData Central
(https://fdc.nal.usda.gov) or, for mixed dishes, typical published recipes.
They are for patient education, not clinical use.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import FoodRow

# (name, serving, carbohydrates g, calories kcal)
FOODS: tuple[tuple[str, str, float, float], ...] = (
    ("Apple", "1 medium (182 g)", 25.0, 95.0),
    ("Banana", "1 medium (118 g)", 27.0, 105.0),
    ("Bread, white", "1 slice (25 g)", 13.0, 67.0),
    ("Brown rice, cooked", "1 cup (195 g)", 45.0, 216.0),
    ("Chicken breast, cooked", "100 g", 0.0, 165.0),
    ("Chickpeas (chana), cooked", "1 cup (164 g)", 45.0, 269.0),
    ("Daal (lentils), cooked", "1 cup (198 g)", 40.0, 230.0),
    ("Dates", "1 date (24 g)", 18.0, 66.0),
    ("Egg, boiled", "1 large (50 g)", 0.6, 78.0),
    ("Milk, whole", "1 cup (244 ml)", 12.0, 149.0),
    ("Oats, cooked", "1 cup (234 g)", 27.0, 166.0),
    ("Orange", "1 medium (131 g)", 15.0, 62.0),
    ("Paratha, plain", "1 medium (80 g)", 36.0, 260.0),
    ("Potato, boiled", "1 medium (173 g)", 37.0, 161.0),
    ("Rice, white, cooked", "1 cup (158 g)", 45.0, 205.0),
    ("Roti (chapati)", "1 medium (40 g)", 18.0, 120.0),
    ("Samosa", "1 piece (100 g)", 24.0, 260.0),
    ("Tea with milk and 1 tsp sugar", "1 cup (240 ml)", 8.0, 45.0),
    ("Yogurt (dahi), plain", "1 cup (245 g)", 11.0, 149.0),
)


def seed_foods(session: Session) -> int:
    """Insert foods that are not in the table yet; return how many were added."""
    existing = set(session.scalars(select(FoodRow.name)))
    added = 0
    for name, serving, carbs, calories in FOODS:
        if name not in existing:
            session.add(FoodRow(name=name, serving_description=serving, carbs_g=carbs,
                                calories_kcal=calories))
            added += 1
    session.commit()
    return added
