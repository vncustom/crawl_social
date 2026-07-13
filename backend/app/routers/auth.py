from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE, create_session, csrf_matches, verify_password
from app.db import get_session
from app.dependencies import get_admin_session, get_current_admin
from app.models import AdminSession, AdminUser, AuditEvent
from app.schemas import AuthResponse, CurrentAdminResponse, LoginRequest


router = APIRouter(prefix="/api/auth", tags=["authentication"])
INVALID_LOGIN = "Tên đăng nhập hoặc mật khẩu không đúng."
THROTTLED_LOGIN = "Quá nhiều lần đăng nhập thất bại. Hãy thử lại sau."


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_session)) -> AuthResponse:
    username = payload.username.strip()
    client_ip = request.client.host if request.client else "unknown"
    attempt_key = f"{username}|{client_ip}"
    cutoff = datetime.now(UTC) - timedelta(minutes=15)
    failures = db.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.action == "login_failed",
            AuditEvent.target_id == attempt_key,
            AuditEvent.created_at >= cutoff,
        )
    )
    if (failures or 0) >= 5:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=THROTTLED_LOGIN)
    admin = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if admin is None or not admin.enabled or not verify_password(payload.password, admin.password_hash):
        db.add(AuditEvent(action="login_failed", target_type="admin_user_ip", target_id=attempt_key))
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_LOGIN)
    credentials = create_session(db, admin, response)
    admin.last_login_at = datetime.now(UTC)
    db.add(AuditEvent(actor_user_id=admin.id, action="login_succeeded", target_type="admin_user", target_id=str(admin.id)))
    db.commit()
    return AuthResponse(username=admin.username, role=admin.role, csrf_token=credentials.csrf_token)


@router.get("/me", response_model=CurrentAdminResponse)
def me(admin: AdminUser = Depends(get_current_admin)) -> CurrentAdminResponse:
    return CurrentAdminResponse(username=admin.username, role=admin.role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    x_csrf_token: str | None = Header(default=None),
    admin_session: AdminSession = Depends(get_admin_session),
    db: Session = Depends(get_session),
) -> Response:
    if not x_csrf_token or not csrf_matches(x_csrf_token, admin_session.csrf_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token không hợp lệ.")
    admin_session.revoked_at = datetime.now(UTC)
    db.add(AuditEvent(actor_user_id=admin_session.admin_user_id, action="logout", target_type="admin_session", target_id=str(admin_session.id)))
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
