from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.dependencies import get_current_admin, get_graph_client, require_csrf
from app.graph.client import GraphAPIError, GraphClient
from app.models import AdminUser, AuditEvent, JobType, Page
from app.schemas import BackfillRequest, PageCreate, PageUpdate
from app.sync.jobs import ActiveJobConflict, enqueue_job


router = APIRouter(prefix="/api/pages", tags=["pages"])


def job_dict(job):
    return {"id": job.id, "status": job.status, "start_date": job.start_date, "end_date": job.end_date, "job_type": job.job_type}


def page_dict(page: Page, initial_job=None):
    value = {"id": page.id, "page_id": page.external_page_id, "display_name": page.display_name, "category": page.category, "link": page.public_link, "enabled": page.enabled, "daily_sync_enabled": page.daily_sync_enabled, "latest_sync_at": page.latest_sync_at}
    if initial_job is not None:
        value["initial_job"] = job_dict(initial_job)
    return value


@router.get("")
def list_pages(_: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    return [page_dict(page) for page in db.scalars(select(Page).order_by(Page.display_name, Page.id))]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_page(payload: PageCreate, _: object = Depends(require_csrf), admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session), graph: GraphClient = Depends(get_graph_client)):
    if db.scalar(select(Page).where(Page.external_page_id == payload.page_id)):
        raise HTTPException(status_code=409, detail="Page ID đã tồn tại.")
    try:
        identity = graph.get_page_identity(payload.page_id)
    except GraphAPIError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    page = Page(external_page_id=payload.page_id, display_name=payload.display_name or identity.get("name") or payload.page_id, category=identity.get("category"), public_link=identity.get("link"), enabled=payload.enabled, daily_sync_enabled=payload.daily_sync_enabled)
    db.add(page)
    db.commit()
    today = datetime.now(ZoneInfo(get_settings().report_timezone)).date()
    start = payload.backfill_start or today - timedelta(days=89)
    end = payload.backfill_end or today
    job = enqueue_job(db, page.id, JobType.backfill, start, end, admin.id)
    db.add(AuditEvent(actor_user_id=admin.id, action="page_created", target_type="page", target_id=str(page.id)))
    db.commit()
    return page_dict(page, job)


@router.patch("/{page_id}")
def update_page(page_id: int, payload: PageUpdate, _: object = Depends(require_csrf), admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    page = db.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy Page.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(page, field, value)
    db.add(AuditEvent(actor_user_id=admin.id, action="page_updated", target_type="page", target_id=str(page.id)))
    db.commit()
    return page_dict(page)


def enqueue_page_job(page_id: int, job_type: JobType, start, end, admin: AdminUser, db: Session):
    page = db.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy Page.")
    try:
        job = enqueue_job(db, page.id, job_type, start, end, admin.id)
    except ActiveJobConflict as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc), "existing_job_id": exc.existing_job_id}) from exc
    return job_dict(job)


@router.post("/{page_id}/backfill")
def backfill(page_id: int, payload: BackfillRequest, _: object = Depends(require_csrf), admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    return enqueue_page_job(page_id, JobType.backfill, payload.start_date, payload.end_date, admin, db)


@router.post("/{page_id}/sync")
def sync_now(page_id: int, _: object = Depends(require_csrf), admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    today = datetime.now(ZoneInfo(get_settings().report_timezone)).date()
    return enqueue_page_job(page_id, JobType.manual, today, today, admin, db)
