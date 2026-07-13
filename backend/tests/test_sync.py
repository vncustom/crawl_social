from datetime import UTC, date, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.graph.client import GraphAPIError
from app.models import Base, JobStatus, JobType, MetricAvailability, MetricStatus, Page, Post, PostSnapshot, SyncJob
from app.sync.service import SyncService
from app.worker import enqueue_daily_jobs


class FakeGraph:
    def iter_posts(self, page_id, since, until):
        yield {
            "id": "post-1",
            "created_time": "2026-07-01T12:00:00+0000",
            "message": "Hello",
            "permalink_url": "https://facebook.com/post-1",
            "reactions": {"summary": {"total_count": 7}},
            "comments": {"summary": {"total_count": 2}},
            "shares": {"count": 1},
        }

    def iter_insights(self, page_id, metrics, since, until):
        raise GraphAPIError("invalid_request", 100, "Metric unavailable")

    def iter_videos(self, page_id, since, until):
        return iter(())

    def iter_comments(self, post_id):
        return iter(())


def build_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def add_job(db, page, status=JobStatus.running):
    job = SyncJob(page_id=page.id, job_type=JobType.manual, status=status, start_date=date(2026, 7, 1), end_date=date(2026, 7, 2))
    db.add(job)
    db.commit()
    return job


def test_repeat_sync_upserts_post_and_adds_snapshot():
    with build_db() as db:
        page = Page(external_page_id="1125132200689307", display_name="HTV")
        db.add(page)
        db.commit()
        first = add_job(db, page)
        SyncService(db, FakeGraph()).run(first.id)
        second = add_job(db, page)
        SyncService(db, FakeGraph()).run(second.id)

        assert db.scalar(select(func.count(Post.id))) == 1
        assert db.scalar(select(func.count(PostSnapshot.id))) == 2
        assert db.get(SyncJob, second.id).status == JobStatus.completed


def test_bad_insight_does_not_discard_posts():
    with build_db() as db:
        page = Page(external_page_id="1125132200689307", display_name="HTV")
        db.add(page)
        db.commit()
        job = add_job(db, page)

        SyncService(db, FakeGraph()).run(job.id)

        assert db.scalar(select(func.count(Post.id))) == 1
        statuses = db.scalars(select(MetricAvailability.status)).all()
        assert statuses
        assert set(statuses) == {MetricStatus.unavailable}


def test_daily_scheduler_enqueues_yesterday_through_today():
    with build_db() as db:
        page = Page(external_page_id="1125132200689307", display_name="HTV")
        db.add(page)
        db.commit()

        jobs = enqueue_daily_jobs(db, datetime(2026, 7, 13, 1, 0, tzinfo=UTC))

        assert len(jobs) == 1
        assert jobs[0].job_type == JobType.daily
        assert jobs[0].start_date == date(2026, 7, 12)
        assert jobs[0].end_date == date(2026, 7, 13)
