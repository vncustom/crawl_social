from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin, require_csrf
from app.models import AdminUser, SyncJob
from app.routers.pages import job_dict
from app.sync.jobs import request_cancellation


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs(_: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    return [job_dict(job) for job in db.scalars(select(SyncJob).order_by(SyncJob.id.desc()))]


@router.get("/{job_id}")
def get_job(job_id: int, _: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    job = db.get(SyncJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy job.")
    return job_dict(job)


@router.post("/{job_id}/cancel")
def cancel_job(job_id: int, _: object = Depends(require_csrf), admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_session)):
    try:
        return job_dict(request_cancellation(db, job_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
