import time
import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.graph.client import GraphClient
from app.models import JobType, Page, SyncJob
from app.sync.jobs import ActiveJobConflict, claim_next_job, enqueue_job
from app.sync.service import SyncService


def enqueue_daily_jobs(db: Session, now: datetime) -> list[SyncJob]:
    jobs = []
    pages = db.scalars(
        select(Page).where(Page.enabled.is_(True), Page.daily_sync_enabled.is_(True))
    )
    for page in pages:
        today = now.astimezone(ZoneInfo(page.timezone)).date()
        existing = db.scalar(
            select(SyncJob.id).where(
                SyncJob.page_id == page.id,
                SyncJob.job_type == JobType.daily,
                SyncJob.end_date == today,
            )
        )
        if existing:
            continue
        try:
            jobs.append(
                enqueue_job(
                    db,
                    page.id,
                    JobType.daily,
                    today - timedelta(days=1),
                    today,
                    None,
                )
            )
        except ActiveJobConflict:
            continue
    return jobs


def daily_schedule_date(
    now: datetime,
    timezone_name: str,
    last_scheduled: date | None,
) -> date | None:
    local = now.astimezone(ZoneInfo(timezone_name))
    if local.time() < time(2) or last_scheduled == local.date():
        return None
    return local.date()


def run_once(worker_id: str) -> bool:
    settings = get_settings()
    with SessionLocal() as db:
        job = claim_next_job(db, worker_id)
        if job is None:
            return False
        graph = GraphClient(settings.fb_page_access_token, settings.fb_graph_version)
        try:
            SyncService(db, graph).run(job.id)
        finally:
            graph.close()
        return True


def run_worker(poll_seconds: float = 2.0) -> None:
    worker_id = f"worker-{uuid.uuid4()}"
    settings = get_settings()
    last_scheduled: date | None = None
    while True:
        now = datetime.now(UTC)
        scheduled_date = daily_schedule_date(
            now,
            settings.report_timezone,
            last_scheduled,
        )
        if scheduled_date:
            with SessionLocal() as db:
                enqueue_daily_jobs(db, now)
            last_scheduled = scheduled_date
        if not run_once(worker_id):
            time.sleep(poll_seconds)


if __name__ == "__main__":
    run_worker()
