from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_admin, get_session
from app.main import create_app
from app.models import AdminUser, Base, Page, Post


def test_report_api_returns_shared_kpis():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        page = Page(external_page_id="1125132200689307", display_name="HTV")
        db.add(page); db.flush()
        db.add(Post(page_id=page.id, external_post_id="p1", published_at=datetime(2026, 7, 1, 1, tzinfo=UTC), media_type="photo", reactions=3, comment_count=2, share_count=1))
        db.commit(); page_id = page.id
    app = create_app()

    def override_session():
        with factory() as db:
            yield db

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_admin] = lambda: AdminUser(id=1, username="admin", password_hash="x")
    with TestClient(app) as client:
        response = client.get(f"/api/reports/{page_id}?from=2026-07-01&to=2026-07-02")

    assert response.status_code == 200
    assert response.json()["summary"]["total_engagement"] == 6
