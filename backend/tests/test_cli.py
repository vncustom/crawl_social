from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.cli import seed_default_page
from app.models import Base, SyncJob


class FakeSettings:
    default_page_id = "1125132200689307"
    report_timezone = "Asia/Bangkok"


class FakeGraph:
    def __init__(self):
        self.calls: list[str] = []

    def get_page_identity(self, page_id: str):
        self.calls.append(page_id)
        return {
            "id": page_id,
            "name": "HTV3",
            "category": "TV channel",
            "link": "https://facebook.com/HTV3",
        }


def test_seed_default_page_is_idempotent_and_enqueues_90_days():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    graph = FakeGraph()

    with Session(engine, expire_on_commit=False) as db:
        page, created = seed_default_page(
            db,
            graph,
            FakeSettings(),
            today=date(2026, 7, 13),
        )
        same_page, created_again = seed_default_page(
            db,
            graph,
            FakeSettings(),
            today=date(2026, 7, 13),
        )

        job = db.scalar(select(SyncJob))
        assert created is True
        assert created_again is False
        assert same_page.id == page.id
        assert graph.calls == ["1125132200689307"]
        assert job.start_date == date(2026, 4, 15)
        assert job.end_date == date(2026, 7, 13)
    engine.dispose()
