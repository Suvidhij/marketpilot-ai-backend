from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import (
    COOKIE,
    DUMMY_HASH,
    current_user,
    digest,
    issue_session,
    passwords,
)
from app.models import AuthAttempt, User, UserSession
from app.schemas.entities import Login, PasswordChange, Profile, Register, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])


def throttle(db, subject, maximum=8, minutes=15):
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    db.execute(
        delete(AuthAttempt).where(
            AuthAttempt.created_at < datetime.now(timezone.utc) - timedelta(days=1)
        )
    )
    count = db.scalar(
        select(func.count())
        .select_from(AuthAttempt)
        .where(AuthAttempt.subject == digest(subject), AuthAttempt.created_at >= since)
    )
    if count >= maximum:
        raise HTTPException(
            429,
            "Too many attempts. Please try again later.",
            headers={"Retry-After": str(minutes * 60)},
        )
    db.add(AuthAttempt(subject=digest(subject)))
    db.commit()


@router.post("/register", response_model=UserOut, status_code=201)
def register(
    data: Register, request: Request, response: Response, db: Session = Depends(get_db)
):
    name = data.name.strip()
    if not name:
        raise HTTPException(422, "Name cannot be blank")
    throttle(
        db,
        "register:" + (request.client.host if request.client else "unknown"),
        maximum=30,
    )
    email = str(data.email).lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "An account with that email already exists")
    user = User(name=name, email=email, hashed_password=passwords.hash(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with that email already exists")
    issue_session(db, user, request, response)
    return user


@router.post("/login", response_model=UserOut)
def login(
    data: Login, request: Request, response: Response, db: Session = Depends(get_db)
):
    email = str(data.email).lower()
    throttle(db, "login:" + email)
    user = db.scalar(select(User).where(User.email == email))
    valid = passwords.verify(
        data.password, user.hashed_password if user else DUMMY_HASH
    )
    if not user or not valid or not user.is_active:
        raise HTTPException(401, "Email or password is incorrect")
    old = request.cookies.get(COOKIE)
    if old:
        db.execute(delete(UserSession).where(UserSession.token_hash == digest(old)))
    issue_session(db, user, request, response)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE)
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == digest(token)))
        db.commit()
    response.delete_cookie(
        COOKIE,
        path="/",
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def profile(
    data: Profile, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    user.name = data.name
    db.commit()
    db.refresh(user)
    return user


@router.post("/password", status_code=204)
def change_password(
    data: PasswordChange,
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    throttle(db, "password:" + str(user.id), maximum=5)
    if not passwords.verify(data.current_password, user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    user.hashed_password = passwords.hash(data.new_password)
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    issue_session(db, user, request, response)
