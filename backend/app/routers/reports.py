from datetime import date, datetime
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.dependencies import get_current_admin
from app.models import AdminUser
from app.reporting.service import ReportDataset, ReportingService


router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{page_id}", response_model=ReportDataset)
def get_report(
    page_id: int,
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> ReportDataset:
    today = datetime.now(ZoneInfo(get_settings().report_timezone)).date()
    end = end or today
    start = start or end - relativedelta(months=1)
    try:
        return ReportingService(db).build(page_id, start, end)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
