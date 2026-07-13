from datetime import UTC, date, datetime
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Page, PageDailyInsight, Post
from app.reporting.service import ReportingService


@contextmanager
def build_report():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    page = Page(external_page_id="1125132200689307", display_name="HTV")
    db.add(page)
    db.flush()
    db.add_all(
        [
            Post(page_id=page.id, external_post_id="p1", published_at=datetime(2026, 7, 1, 1, tzinfo=UTC), message="Top", media_type="photo", reactions=10, comment_count=2, share_count=3),
            Post(page_id=page.id, external_post_id="p2", published_at=datetime(2026, 7, 2, 2, tzinfo=UTC), message="Second", media_type="video", reactions=4, comment_count=1, share_count=0),
            PageDailyInsight(page_id=page.id, metric_date=date(2026, 6, 30), metric_name="followers_total", period="day", source_version="page_follows", value=100),
            PageDailyInsight(page_id=page.id, metric_date=date(2026, 7, 2), metric_name="followers_total", period="day", source_version="page_follows", value=110),
            PageDailyInsight(page_id=page.id, metric_date=date(2026, 7, 1), metric_name="page_views", period="day", source_version="page_views_total", value=None),
        ]
    )
    db.commit()
    try:
        yield db, page
    finally:
        db.close()
        engine.dispose()


def test_report_calculates_engagement_and_top_post():
    with build_report() as (db, page):
        report = ReportingService(db).build(page.id, date(2026, 7, 1), date(2026, 7, 2))

        assert report.summary.posts == 2
        assert report.summary.total_engagement == 20
        assert report.summary.average_engagement == 10
        assert report.top_posts[0].external_post_id == "p1"
        assert report.summary.current_followers == 110
        assert report.summary.follower_growth == 10


def test_missing_insight_remains_none():
    with build_report() as (db, page):
        report = ReportingService(db).build(page.id, date(2026, 7, 1), date(2026, 7, 2))

        july_first = next(row for row in report.daily_insights if row.metric_date == date(2026, 7, 1))
        assert july_first.page_views is None
