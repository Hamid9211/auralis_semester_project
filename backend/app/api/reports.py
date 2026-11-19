"""HTTP endpoints of module M4 (Medical Report Analyzer).

The router only translates HTTP into service calls; all rules live in ReportService.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, Request, UploadFile, status

from app.api.dependencies import get_settings
from app.api.report_schemas import LabReportOut
from app.core.config import Settings
from app.infrastructure.db.init_db import DEFAULT_PATIENT_ID
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["lab reports"])


def get_report_service(request: Request) -> ReportService:
    """The ReportService created at application start-up."""
    return request.app.state.report_service


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_report(
    file: Annotated[UploadFile, File(description="PDF lab report")],
    service: Annotated[ReportService, Depends(get_report_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LabReportOut:
    """Accept a PDF and return at once; processing continues in the background."""
    # Read one byte more than allowed so oversized files are detected
    # without reading the whole upload into memory.
    data = await file.read(settings.max_upload_bytes + 1)
    report = await service.upload(DEFAULT_PATIENT_ID, file.filename or "", data)
    return LabReportOut.from_domain(report)


@router.get("")
def list_reports(
    service: Annotated[ReportService, Depends(get_report_service)],
) -> list[LabReportOut]:
    """All reports of the patient with status and results, newest first."""
    return [LabReportOut.from_domain(r) for r in service.list_reports(DEFAULT_PATIENT_ID)]


@router.get("/{report_id}")
def get_report(
    report_id: Annotated[int, Path(gt=0)],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> LabReportOut:
    """One report; poll this until its status is done or failed."""
    return LabReportOut.from_domain(service.get_report(report_id))
