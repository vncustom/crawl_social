from datetime import UTC, date, datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.dependencies import get_current_admin
from app.models import AdminUser
from app.reporting.service import ReportDataset, ReportingService
from app.reporting.excel import build_workbook


router = APIRouter(prefix="/api/reports", tags=["reports"])


def report_dates(start: date | None, end: date | None) -> tuple[date, date]:
    today = datetime.now(ZoneInfo(get_settings().report_timezone)).date()
    resolved_end = end or today
    return start or resolved_end - relativedelta(months=1), resolved_end


@router.get("/{page_id}/excel")
def download_excel(
    page_id: int,
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> StreamingResponse:
    start, end = report_dates(start, end)
    try:
        dataset = ReportingService(db).build(page_id, start, end)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    workbook = build_workbook(dataset, datetime.now(UTC))
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = f"facebook-report_{dataset.external_page_id}_{start.isoformat()}_{end.isoformat()}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{page_id}", response_model=ReportDataset)
def get_report(
    page_id: int,
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> ReportDataset:
    start, end = report_dates(start, end)
    try:
        return ReportingService(db).build(page_id, start, end)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
