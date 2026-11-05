import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, Header, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import User, UserSession, WorkflowToken

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(24))
COOKIE = "marketpilot_session"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_guard(request: Request):
    if request.method in {"GET", "HEAD", "OPTIONS"} or request.url.path.startswith(
        "/api/v1/webhooks/"
    ):
        return
    origin = request.headers.get("origin")
    allowed = {str(o).rstrip("/") for o in request.app.state.settings.cors_origins}
    if request.headers.get("x-marketpilot-csrf") != "1" or (
        origin is not None and origin not in allowed
    ):
        raise HTTPException(403, "Request origin or CSRF header is invalid")


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    record = db.get(UserSession, digest(token)) if token else None
    if record is None:
        raise HTTPException(401, "Please sign in")
    expires = record.expires_at.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        db.delete(record)
        db.commit()
        raise HTTPException(401, "Session expired. Please sign in again")
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Please sign in")
    return user


def issue_session(db: Session, user: User, request: Request, response):
    token = secrets.token_urlsafe(48)
    settings = request.app.state.settings
    db.execute(
        delete(UserSession).where(UserSession.expires_at < datetime.now(timezone.utc))
    )
    db.add(
        UserSession(
            token_hash=digest(token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=settings.session_hours),
        )
    )
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_hours * 3600,
        path="/",
    )


def workflow_user(
    request: Request,
    x_workflow_key: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    record = (
        db.scalar(
            select(WorkflowToken).where(
                WorkflowToken.token_hash == digest(x_workflow_key)
            )
        )
        if x_workflow_key
        else None
    )
    user = db.get(User, record.user_id) if record else None
    if user is None or not user.is_active:
        raise HTTPException(401, "Invalid workflow credential")
    return user
