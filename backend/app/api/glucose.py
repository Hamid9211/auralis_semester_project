"""HTTP endpoints of modules M1 (glucose readings) and M2 (trends)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status

from app.api.glucose_schemas import ReadingIn, ReadingOut, TrendReportOut
from app.infrastructure.db.init_db import DEFAULT_PATIENT_ID
from app.services.glucose_service import GlucoseService
from app.services.trend_service import TrendService

router = APIRouter(tags=["glucose"])


def get_glucose_service(request: Request) -> GlucoseService:
    """The GlucoseService created with the application."""
    return request.app.state.glucose_service


def get_trend_service(request: Request) -> TrendService:
    """The TrendService created with the application."""
    return request.app.state.trend_service


@router.post("/glucose", status_code=status.HTTP_201_CREATED)
def log_reading(
    body: ReadingIn,
    service: Annotated[GlucoseService, Depends(get_glucose_service)],
) -> ReadingOut:
    """Record a reading (FR-GL-01, FR-GL-02)."""
    reading = service.log_reading(DEFAULT_PATIENT_ID, body.value_mg_dl, body.measured_at,
                                  body.context)
    return ReadingOut.from_domain(reading)


@router.get("/glucose")
def list_readings(
    service: Annotated[GlucoseService, Depends(get_glucose_service)],
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> list[ReadingOut]:
    """Readings newest first, optionally between start and end (FR-GL-03)."""
    readings = service.list_readings(DEFAULT_PATIENT_ID, start, end)
    return [ReadingOut.from_domain(r) for r in readings]


@router.delete("/glucose/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reading(
    reading_id: Annotated[int, Path(gt=0)],
    service: Annotated[GlucoseService, Depends(get_glucose_service)],
) -> Response:
    """Delete a reading (FR-GL-04)."""
    service.delete_reading(reading_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/trends")
def get_trends(
    service: Annotated[TrendService, Depends(get_trend_service)],
    days: Annotated[int, Query()] = 7,
) -> TrendReportOut:
    """Time in range, counts, findings and chart points for 7, 14 or 30 days (FR-TA)."""
    return TrendReportOut.from_domain(service.analyze(DEFAULT_PATIENT_ID, days))
