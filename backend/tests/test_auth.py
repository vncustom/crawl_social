from sqlalchemy import create_engine
from contextlib import contextmanager
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.dependencies import get_session
from app.main import create_app
from app.models import AdminUser, Base


@contextmanager
def build_client():
    from fastapi.testclient import TestClient

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as session:
        session.add(
            AdminUser(
                username="admin",
                password_hash=hash_password("correct horse battery staple"),
            )
        )
        session.commit()

    app = create_app()

    def override_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        engine.dispose()


def test_login_sets_http_only_cookie_and_returns_csrf():
    with build_client() as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "correct horse battery staple"},
        )

        assert response.status_code == 200
        assert response.json()["username"] == "admin"
        assert response.json()["csrf_token"]
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie


def test_wrong_password_returns_generic_error():
    with build_client() as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong password"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Tên đăng nhập hoặc mật khẩu không đúng."


def test_logout_requires_csrf_and_revokes_session():
    with build_client() as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "correct horse battery staple"},
        )
        csrf_token = login.json()["csrf_token"]

        assert client.post("/api/auth/logout").status_code == 403
        logout = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert logout.status_code == 204
        assert client.get("/api/auth/me").status_code == 401


def test_login_is_throttled_after_five_failures():
    with build_client() as client:
        for _ in range(5):
            response = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "wrong password"},
            )
            assert response.status_code == 401

        blocked = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong password"},
        )

        assert blocked.status_code == 429
        assert blocked.json()["detail"] == "Quá nhiều lần đăng nhập thất bại. Hãy thử lại sau."
