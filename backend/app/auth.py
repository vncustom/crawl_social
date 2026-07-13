import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Response
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AdminSession, AdminUser


PASSWORD_HASH = PasswordHash.recommended()
SESSION_COOKIE = "fb_report_session"
SESSION_LIFETIME = timedelta(hours=12)


def hash_password(password: str) -> str:
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, digest: str) -> bool:
    return PASSWORD_HASH.verify(password, digest)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SessionCredentials:
    session_token: str
    csrf_token: str


def create_session(db: Session, admin: AdminUser, response: Response) -> SessionCredentials:
    settings = get_settings()
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    db.add(
        AdminSession(
            admin_user_id=admin.id,
            token_hash=hash_secret(session_token),
            csrf_hash=hash_secret(csrf_token),
            expires_at=datetime.now(UTC) + SESSION_LIFETIME,
        )
    )
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return SessionCredentials(session_token=session_token, csrf_token=csrf_token)


def csrf_matches(raw_token: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(raw_token), stored_hash)
