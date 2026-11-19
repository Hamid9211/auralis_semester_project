"""SQLAlchemy table definitions (persistent schema).

CHECK and UNIQUE constraints repeat the most important business rules at the
database level, so invalid data is rejected even if a service check is missed
(defence in depth). Services still validate first and raise domain errors.
"""

# pylint: disable=unsubscriptable-object
# False positive: Pylint cannot infer that SQLAlchemy's generic Mapped supports
# subscripting (Mapped[int]), which SQLAlchemy 2.x requires for typed columns.

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.glucose import MAX_GLUCOSE_MG_DL, MIN_GLUCOSE_MG_DL, ReadingContext

# Glucose rules come from the domain model, so the CHECK constraints and the
# service validation cannot drift apart.
READING_CONTEXTS = tuple(context.value for context in ReadingContext)
MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")
REPORT_STATUSES = ("pending", "processing", "done", "failed")
LAB_TESTS = ("hba1c", "fasting_glucose", "ldl_cholesterol", "creatinine")

MIN_PORTION = 0.5
MAX_PORTION = 3.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class Base(DeclarativeBase):
    """Declarative base for all tables."""


class PatientRow(Base):
    """A patient using the system."""

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class GlucoseReadingRow(Base):
    """One glucose measurement (module M1)."""

    __tablename__ = "glucose_readings"
    __table_args__ = (
        CheckConstraint(
            f"value_mg_dl BETWEEN {MIN_GLUCOSE_MG_DL} AND {MAX_GLUCOSE_MG_DL}",
            name="ck_glucose_value_range",
        ),
        CheckConstraint(_in_list("context", READING_CONTEXTS), name="ck_glucose_context"),
        Index("ix_glucose_patient_time", "patient_id", "measured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    value_mg_dl: Mapped[float] = mapped_column(Float)
    measured_at: Mapped[datetime] = mapped_column(DateTime)
    context: Mapped[str] = mapped_column(String(20))


class FoodRow(Base):
    """A food in the nutrition table, with values per serving (module M3)."""

    __tablename__ = "foods"
    __table_args__ = (
        CheckConstraint("carbs_g >= 0", name="ck_food_carbs_non_negative"),
        CheckConstraint("calories_kcal >= 0", name="ck_food_calories_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    serving_description: Mapped[str] = mapped_column(String(100))
    carbs_g: Mapped[float] = mapped_column(Float)
    calories_kcal: Mapped[float] = mapped_column(Float)


class MealRow(Base):
    """A logged meal (module M3)."""

    __tablename__ = "meals"
    __table_args__ = (
        CheckConstraint(_in_list("meal_type", MEAL_TYPES), name="ck_meal_type"),
        Index("ix_meal_patient_time", "patient_id", "eaten_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    meal_type: Mapped[str] = mapped_column(String(20))
    eaten_at: Mapped[datetime] = mapped_column(DateTime)

    items: Mapped[list["MealItemRow"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )


class MealItemRow(Base):
    """One food and portion within a meal (module M3)."""

    __tablename__ = "meal_items"
    __table_args__ = (
        CheckConstraint(
            f"portion BETWEEN {MIN_PORTION} AND {MAX_PORTION}", name="ck_meal_item_portion"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id", ondelete="CASCADE"))
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"))
    portion: Mapped[float] = mapped_column(Float)

    meal: Mapped[MealRow] = relationship(back_populates="items")


class LabReportRow(Base):
    """An uploaded lab report and its processing state (module M4)."""

    __tablename__ = "lab_reports"
    __table_args__ = (
        # Prevents the same file being stored or processed twice (thread-safety point 3).
        UniqueConstraint("patient_id", "file_hash", name="uq_report_patient_file"),
        CheckConstraint(_in_list("status", REPORT_STATUSES), name="ck_report_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    values: Mapped[list["LabValueRow"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class LabValueRow(Base):
    """One lab value detected in a report (module M4)."""

    __tablename__ = "lab_values"
    __table_args__ = (
        CheckConstraint(_in_list("test_name", LAB_TESTS), name="ck_lab_test_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("lab_reports.id", ondelete="CASCADE"))
    test_name: Mapped[str] = mapped_column(String(30))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    is_normal: Mapped[bool] = mapped_column(Boolean)

    report: Mapped[LabReportRow] = relationship(back_populates="values")
