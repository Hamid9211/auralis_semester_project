"""SQLAlchemy implementations of FoodRepository and MealRepository (module M3)."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.domain.meals import Food, FoodRepository, Meal, MealItem, MealRepository, MealType
from app.infrastructure.db.models import FoodRow, MealItemRow, MealRow

# pylint: disable=unsubscriptable-object
# False positive on sessionmaker[Session]; see the note in session.py.


def _to_db_time(moment: datetime) -> datetime:
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc)
    return moment.replace(tzinfo=None)


def _food(row: FoodRow) -> Food:
    return Food(id=row.id, name=row.name, serving_description=row.serving_description,
                carbs_g=row.carbs_g, calories_kcal=row.calories_kcal)


def _escape_like(text: str) -> str:
    # Treat % and _ typed by the user as normal characters, not wildcards.
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SqlFoodRepository(FoodRepository):
    """Read-only search of the foods table."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def search(self, text: str, limit: int) -> list[Food]:
        """Foods whose name contains the text, case-insensitive, sorted by name."""
        query = (select(FoodRow)
                 .where(FoodRow.name.ilike(f"%{_escape_like(text)}%", escape="\\"))
                 .order_by(FoodRow.name)
                 .limit(limit))
        with self._session_factory() as session:
            return [_food(row) for row in session.scalars(query)]

    def get(self, food_id: int) -> Food | None:
        """One food or None."""
        with self._session_factory() as session:
            row = session.get(FoodRow, food_id)
            return _food(row) if row else None


class SqlMealRepository(MealRepository):
    """Stores meals and their items."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, patient_id: int, meal_type: MealType, eaten_at: datetime,
            items: list[MealItem]) -> Meal:
        """Insert the meal and its items in one transaction."""
        with self._session_factory() as session:
            row = MealRow(patient_id=patient_id, meal_type=MealType(meal_type).value,
                          eaten_at=_to_db_time(eaten_at))
            row.items = [MealItemRow(food_id=item.food.id, portion=item.portion)
                         for item in items]
            session.add(row)
            session.commit()
            return self._to_domain(session, row)

    def find_by_patient(self, patient_id: int, start: datetime | None = None,
                        end: datetime | None = None) -> list[Meal]:
        """Meals in [start, end], newest first, with their items and foods."""
        query = (select(MealRow).options(selectinload(MealRow.items))
                 .where(MealRow.patient_id == patient_id))
        if start is not None:
            query = query.where(MealRow.eaten_at >= _to_db_time(start))
        if end is not None:
            query = query.where(MealRow.eaten_at <= _to_db_time(end))
        query = query.order_by(MealRow.eaten_at.desc(), MealRow.id.desc())
        with self._session_factory() as session:
            return [self._to_domain(session, row) for row in session.scalars(query)]

    @staticmethod
    def _to_domain(session: Session, row: MealRow) -> Meal:
        food_ids = {item.food_id for item in row.items}
        foods = {f.id: _food(f) for f in
                 session.scalars(select(FoodRow).where(FoodRow.id.in_(food_ids)))}
        items = tuple(MealItem(food=foods[item.food_id], portion=item.portion)
                      for item in sorted(row.items, key=lambda i: i.id))
        return Meal(id=row.id, patient_id=row.patient_id, meal_type=MealType(row.meal_type),
                    eaten_at=row.eaten_at.replace(tzinfo=timezone.utc), items=items)
