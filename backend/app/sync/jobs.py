from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JobStatus, JobType, SyncJob


ACTIVE_STATUSES = {
    JobStatus.queued,
    JobStatus.running,
    JobStatus.retrying,
    JobStatus.cancelling,
}


class ActiveJobConflict(RuntimeError):
    def __init__(self, existing_job_id: int):
        self.existing_job_id = existing_job_id
        super().__init__(f"Page đã có job đang hoạt động: {existing_job_id}")


def enqueue_job(
    db: Session,
    page_id: int,
    job_type: JobType,
    start_date: date,
    end_date: date,
    actor_id: int | None,
) -> SyncJob:
    if start_date > end_date:
        raise ValueError("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
    active = db.scalar(
        select(SyncJob).where(
            SyncJob.page_id == page_id,
            SyncJob.status.in_(ACTIVE_STATUSES),
        )
    )
    if active:
        raise ActiveJobConflict(active.id)
    job = SyncJob(
        page_id=page_id,
        job_type=job_type,
        status=JobStatus.queued,
        start_date=start_date,
        end_date=end_date,
        actor_user_id=actor_id,
    )
    db.add(job)
    db.commit()
    return job


def claim_next_job(db: Session, worker_id: str, lease_minutes: int = 5) -> SyncJob | None:
    job = db.scalar(
        select(SyncJob)
        .where(SyncJob.status == JobStatus.queued)
        .order_by(SyncJob.created_at, SyncJob.id)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    job.status = JobStatus.running
    job.worker_id = worker_id
    job.lease_expires_at = datetime.now(UTC) + timedelta(minutes=lease_minutes)
    db.commit()
    return job


def request_cancellation(db: Session, job_id: int) -> SyncJob:
    job = db.get(SyncJob, job_id)
    if job is None:
        raise LookupError("Không tìm thấy job.")
    if job.status in {JobStatus.queued, JobStatus.running, JobStatus.retrying}:
        job.status = JobStatus.cancelling
        db.commit()
    return job
