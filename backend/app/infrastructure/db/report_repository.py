"""SQLAlchemy implementation of LabReportRepository.

Every method opens its own short-lived Session, so the repository can be
called safely from request handlers and from the background workers.
"""

# pylint: disable=unsubscriptable-object
# False positive on sessionmaker[Session]; see the note in session.py.

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.core.exceptions import DuplicateReportError, NotFoundError
from app.domain.lab_reports import LabReport, LabReportRepository, LabValue, ReportStatus
from app.infrastructure.db.models import LabReportRow, LabValueRow


def _as_utc(moment: datetime) -> datetime:
    # SQLite drops the time zone; all times are stored in UTC, so restore it.
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _to_domain(row: LabReportRow) -> LabReport:
    return LabReport(
        id=row.id,
        patient_id=row.patient_id,
        filename=row.filename,
        file_hash=row.file_hash,
        status=ReportStatus(row.status),
        uploaded_at=_as_utc(row.uploaded_at),
        explanation=row.explanation,
        explanation_source=row.explanation_source,
        error_message=row.error_message,
        values=tuple(
            LabValue(test_name=v.test_name, value=v.value, unit=v.unit, is_normal=v.is_normal)
            for v in row.values
        ),
    )


class SqlLabReportRepository(LabReportRepository):
    """Stores reports in the lab_reports and lab_values tables."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, patient_id: int, filename: str, file_hash: str) -> LabReport:
        """Insert a pending report; the UNIQUE constraint rejects duplicates."""
        with self._session_factory() as session:
            row = LabReportRow(patient_id=patient_id, filename=filename,
                               file_hash=file_hash, status=ReportStatus.PENDING.value)
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise DuplicateReportError("This report has already been uploaded.") from exc
            return _to_domain(self._load(session, row.id))

    def get(self, report_id: int) -> LabReport | None:
        """Return one report with its values, or None."""
        with self._session_factory() as session:
            row = self._load(session, report_id)
            return _to_domain(row) if row else None

    def find_by_hash(self, patient_id: int, file_hash: str) -> LabReport | None:
        """Return the patient's report for this file, if any."""
        with self._session_factory() as session:
            row = session.scalars(
                select(LabReportRow)
                .options(selectinload(LabReportRow.values))
                .where(LabReportRow.patient_id == patient_id,
                       LabReportRow.file_hash == file_hash)
            ).first()
            return _to_domain(row) if row else None

    def find_by_patient(self, patient_id: int) -> list[LabReport]:
        """Return the patient's reports, newest first."""
        with self._session_factory() as session:
            rows = session.scalars(
                select(LabReportRow)
                .options(selectinload(LabReportRow.values))
                .where(LabReportRow.patient_id == patient_id)
                .order_by(LabReportRow.uploaded_at.desc(), LabReportRow.id.desc())
            ).all()
            return [_to_domain(row) for row in rows]

    def update_status(self, report_id: int, status: ReportStatus,
                      error_message: str | None = None) -> None:
        """Change a report's status (and error message when it failed)."""
        with self._session_factory() as session:
            row = self._require(session, report_id)
            row.status = status.value
            row.error_message = error_message
            session.commit()

    def save_results(self, report_id: int, values: list[LabValue], explanation: str,
                     explanation_source: str) -> None:
        """Replace the report's values, store the explanation and mark it done."""
        with self._session_factory() as session:
            row = self._require(session, report_id)
            row.values = [
                LabValueRow(test_name=v.test_name, value=v.value, unit=v.unit,
                            is_normal=v.is_normal)
                for v in values
            ]
            row.explanation = explanation
            row.explanation_source = explanation_source
            row.error_message = None
            row.status = ReportStatus.DONE.value
            session.commit()

    def fail_unfinished(self, message: str) -> int:
        """Mark reports left pending or processing (e.g. by a restart) as failed."""
        unfinished = (ReportStatus.PENDING.value, ReportStatus.PROCESSING.value)
        with self._session_factory() as session:
            result = session.execute(
                update(LabReportRow)
                .where(LabReportRow.status.in_(unfinished))
                .values(status=ReportStatus.FAILED.value, error_message=message)
            )
            session.commit()
            return result.rowcount

    def delete(self, report_id: int) -> None:
        """Remove a report; its values are removed by the delete-orphan cascade."""
        with self._session_factory() as session:
            session.delete(self._require(session, report_id))
            session.commit()

    def replace_failed(self, report_id: int, patient_id: int, filename: str,
                       file_hash: str) -> LabReport:
        """Delete the failed report and insert the new one in a single transaction."""
        with self._session_factory() as session:
            session.delete(self._require(session, report_id))
            # Flush the delete first so the new row can reuse the (patient, hash) slot.
            session.flush()
            row = LabReportRow(patient_id=patient_id, filename=filename,
                               file_hash=file_hash, status=ReportStatus.PENDING.value)
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise DuplicateReportError("This report has already been uploaded.") from exc
            return _to_domain(self._load(session, row.id))

    @staticmethod
    def _load(session: Session, report_id: int) -> LabReportRow | None:
        return session.scalars(
            select(LabReportRow)
            .options(selectinload(LabReportRow.values))
            .where(LabReportRow.id == report_id)
        ).first()

    @staticmethod
    def _require(session: Session, report_id: int) -> LabReportRow:
        row = session.get(LabReportRow, report_id)
        if row is None:
            raise NotFoundError(f"Lab report {report_id} does not exist.")
        return row
