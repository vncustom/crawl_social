from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, JobStatus, JobType, Page
from app.sync.jobs import ActiveJobConflict, claim_next_job, enqueue_job, request_cancellation


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def page(db):
    value = Page(external_page_id="1125132200689307", display_name="HTV")
    db.add(value)
    db.commit()
    return value


def test_enqueue_rejects_second_active_job(db, page):
    first = enqueue_job(db, page.id, JobType.manual, date(2026, 7, 1), date(2026, 7, 2), None)

    with pytest.raises(ActiveJobConflict) as caught:
        enqueue_job(db, page.id, JobType.backfill, date(2026, 6, 1), date(2026, 7, 2), None)

    assert caught.value.existing_job_id == first.id


def test_claim_and_cancel_job(db, page):
    queued = enqueue_job(db, page.id, JobType.manual, date(2026, 7, 1), date(2026, 7, 2), None)

    claimed = claim_next_job(db, "worker-1")
    assert claimed.id == queued.id
    assert claimed.status == JobStatus.running
    assert claimed.worker_id == "worker-1"

    cancelled = request_cancellation(db, claimed.id)
    assert cancelled.status == JobStatus.cancelling
