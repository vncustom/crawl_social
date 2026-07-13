from datetime import UTC, datetime

from collections.abc import Generator

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE, csrf_matches, hash_secret
from app.config import get_settings
from app.db import get_session
from app.graph.client import GraphClient
from app.models import AdminSession, AdminUser


def get_admin_session(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_session),
) -> AdminSession:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập.")
    value = db.scalar(select(AdminSession).where(AdminSession.token_hash == hash_secret(session_token)))
    if value is None or value.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập không hợp lệ.")
    expires_at = value.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập đã hết hạn.")
    return value


def get_current_admin(
    admin_session: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_session),
) -> AdminUser:
    admin = db.get(AdminUser, admin_session.admin_user_id)
    if admin is None or not admin.enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không hoạt động.")
    return admin


def require_csrf(
    x_csrf_token: str | None = Header(default=None),
    admin_session: AdminSession = Depends(get_admin_session),
) -> AdminSession:
    if not x_csrf_token or not csrf_matches(x_csrf_token, admin_session.csrf_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token không hợp lệ.")
    return admin_session


def get_graph_client() -> Generator[GraphClient, None, None]:
    settings = get_settings()
    client = GraphClient(settings.fb_page_access_token, settings.fb_graph_version)
    try:
        yield client
    finally:
        client.close()
