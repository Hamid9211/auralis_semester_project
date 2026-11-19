"""The database schema enforces the key business rules (defence in depth)."""

from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.db.init_db import DEFAULT_PATIENT_ID, init_database
from app.infrastructure.db.models import (
    FoodRow,
    GlucoseReadingRow,
    LabReportRow,
    MealItemRow,
    MealRow,
    PatientRow,
)
from app.infrastructure.db.session import create_db_engine

EXPECTED_TABLES = {"patients", "glucose_readings", "foods", "meals", "meal_items",
                   "lab_reports", "lab_values"}
NOW = datetime(2026, 11, 5, 8, 0)


@pytest.fixture(name="engine")
def fixture_engine():
    engine = create_db_engine("sqlite://")
    init_database(engine)
    yield engine
    engine.dispose()


@pytest.fixture(name="session")
def fixture_session(engine):
    with Session(engine) as session:
        yield session


def _reading(value: float, context: str = "fasting") -> GlucoseReadingRow:
    return GlucoseReadingRow(patient_id=DEFAULT_PATIENT_ID, value_mg_dl=value,
                             measured_at=NOW, context=context)


def _report(file_hash: str = "a" * 64) -> LabReportRow:
    return LabReportRow(patient_id=DEFAULT_PATIENT_ID, filename="r.pdf",
                        file_hash=file_hash, status="pending")


def test_all_tables_are_created(engine):
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_default_patient_is_seeded_once(engine, session):
    init_database(engine)  # second call must not duplicate the patient
    assert session.query(PatientRow).count() == 1
    assert session.get(PatientRow, DEFAULT_PATIENT_ID) is not None


@pytest.mark.parametrize("value", [20, 600])
def test_glucose_boundaries_are_accepted(session, value):
    session.add(_reading(value))
    session.commit()


@pytest.mark.parametrize("value", [19.9, 600.1])
def test_glucose_outside_range_is_rejected(session, value):
    session.add(_reading(value))
    with pytest.raises(IntegrityError):
        session.commit()


def test_unknown_reading_context_is_rejected(session):
    session.add(_reading(100, context="lunchtime"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_same_file_cannot_be_stored_twice_for_a_patient(session):
    session.add(_report())
    session.commit()
    session.add(_report())
    with pytest.raises(IntegrityError):
        session.commit()


def test_unknown_report_status_is_rejected(session):
    report = _report()
    report.status = "archived"
    session.add(report)
    with pytest.raises(IntegrityError):
        session.commit()


def test_foreign_keys_are_enforced(session):
    session.add(GlucoseReadingRow(patient_id=999, value_mg_dl=100, measured_at=NOW,
                                  context="fasting"))
    with pytest.raises(IntegrityError):
        session.commit()


def _meal_with_portion(session: Session, portion: float) -> MealRow:
    food = FoodRow(name="Rice", serving_description="1 cup", carbs_g=45, calories_kcal=205)
    session.add(food)
    session.flush()
    meal = MealRow(patient_id=DEFAULT_PATIENT_ID, meal_type="lunch", eaten_at=NOW)
    meal.items.append(MealItemRow(food_id=food.id, portion=portion))
    session.add(meal)
    return meal


@pytest.mark.parametrize("portion", [0.4, 3.1])
def test_portion_outside_range_is_rejected(session, portion):
    _meal_with_portion(session, portion)
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_a_meal_deletes_its_items(session):
    meal = _meal_with_portion(session, 1.0)
    session.commit()
    session.delete(meal)
    session.commit()
    assert session.query(MealItemRow).count() == 0
