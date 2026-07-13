from datetime import UTC, datetime

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE, hash_secret
from app.db import get_session
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
