"""Schema creation and seed data."""

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.infrastructure.db.models import Base, PatientRow
from app.infrastructure.db.nutrition_seed import seed_foods

# Auralis is patient-facing with no login in scope; all data belongs to one demo patient.
DEFAULT_PATIENT_ID = 1
DEFAULT_PATIENT_NAME = "Demo Patient"


def init_database(engine: Engine) -> None:
    """Create all tables, the default patient and the nutrition table if missing."""
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if session.get(PatientRow, DEFAULT_PATIENT_ID) is None:
            session.add(PatientRow(id=DEFAULT_PATIENT_ID, name=DEFAULT_PATIENT_NAME))
            session.commit()
        seed_foods(session)
