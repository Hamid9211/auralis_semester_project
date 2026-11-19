"""SQLAlchemy implementation of ReadingRepository (module M1).

Times are stored in UTC without a zone (SQLite has no zone type) and returned
as UTC-aware datetimes.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.glucose import GlucoseReading, ReadingContext, ReadingRepository
from app.infrastructure.db.models import GlucoseReadingRow

# pylint: disable=unsubscriptable-object
# False positive on sessionmaker[Session]; see the note in session.py.


def _to_db_time(moment: datetime) -> datetime:
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc)
    return moment.replace(tzinfo=None)


def _from_db_time(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc)


def _to_domain(row: GlucoseReadingRow) -> GlucoseReading:
    return GlucoseReading(id=row.id, patient_id=row.patient_id, value_mg_dl=row.value_mg_dl,
                          measured_at=_from_db_time(row.measured_at),
                          context=ReadingContext(row.context))


class SqlReadingRepository(ReadingRepository):
    """Stores readings in the glucose_readings table; one short session per call."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, patient_id: int, value_mg_dl: float, measured_at: datetime,
            context: ReadingContext) -> GlucoseReading:
        """Insert a reading."""
        with self._session_factory() as session:
            row = GlucoseReadingRow(patient_id=patient_id, value_mg_dl=value_mg_dl,
                                    measured_at=_to_db_time(measured_at),
                                    context=ReadingContext(context).value)
            session.add(row)
            session.commit()
            return _to_domain(row)

    def get(self, reading_id: int) -> GlucoseReading | None:
        """One reading or None."""
        with self._session_factory() as session:
            row = session.get(GlucoseReadingRow, reading_id)
            return _to_domain(row) if row else None

    def find_by_patient(self, patient_id: int, start: datetime | None = None,
                        end: datetime | None = None) -> list[GlucoseReading]:
        """Readings in [start, end], newest first."""
        query = select(GlucoseReadingRow).where(GlucoseReadingRow.patient_id == patient_id)
        if start is not None:
            query = query.where(GlucoseReadingRow.measured_at >= _to_db_time(start))
        if end is not None:
            query = query.where(GlucoseReadingRow.measured_at <= _to_db_time(end))
        query = query.order_by(GlucoseReadingRow.measured_at.desc(), GlucoseReadingRow.id.desc())
        with self._session_factory() as session:
            return [_to_domain(row) for row in session.scalars(query)]

    def delete(self, reading_id: int) -> bool:
        """Delete a reading; False if it did not exist."""
        with self._session_factory() as session:
            row = session.get(GlucoseReadingRow, reading_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
