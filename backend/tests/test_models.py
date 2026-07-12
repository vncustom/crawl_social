from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Base, Page, PageDailyInsight, Video


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_default_page_values(db_session):
    page = Page(external_page_id="1125132200689307", display_name="Default Page")
    db_session.add(page)
    db_session.commit()

    assert page.enabled is True
    assert page.timezone == "Asia/Bangkok"


def test_daily_metric_is_unique(db_session):
    page = Page(external_page_id="1125132200689307", display_name="Default Page")
    db_session.add(page)
    db_session.flush()
    values = {
        "page_id": page.id,
        "metric_date": date(2026, 7, 12),
        "metric_name": "page_follows",
        "period": "day",
        "source_version": "v25.0",
    }
    db_session.add(PageDailyInsight(**values, value=10))
    db_session.commit()
    db_session.add(PageDailyInsight(**values, value=11))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_unavailable_video_metrics_remain_null(db_session):
    page = Page(external_page_id="1125132200689307", display_name="Default Page")
    db_session.add(page)
    db_session.flush()
    video = Video(page_id=page.id, external_video_id="video-1", views=None)
    db_session.add(video)
    db_session.commit()

    assert video.views is None
