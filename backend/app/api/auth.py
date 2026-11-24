from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from .. import config
from ..models import LoginSession, User
from ..schemas import (
    Login,
    PasswordChange,
    Profile,
    Register,
    SessionView,
    TrackingPreferences,
    UserView,
)
from ..security import DB, Current, dummy, hasher, matches, sign_in, throttle
from ..services.tracking import require_tracking_url

router = APIRouter()


@router.put("/settings/tracking", response_model=TrackingPreferences)
def tracking_preferences(data: TrackingPreferences, auth: Current, db: DB):
    require_tracking_url(data.tracking_open, data.tracking_click)
    user = db.get(User, auth.user_id)
    user.tracking_open = data.tracking_open
    user.tracking_click = data.tracking_click
    db.commit()
    return data


def save_user(db, user):
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That email address is unavailable")


@router.post("/signup", response_model=SessionView, status_code=201)
def signup(data: Register, request: Request, response: Response, db: DB):
    if not config.SIGNUP:
        raise HTTPException(403, "Registration is closed")
    throttle(db, "signup:" + request.client.host, 8)
    user = User(
        name=data.name, email=data.email, password_hash=hasher.hash(data.password)
    )
    save_user(db, user)
    return sign_in(db, user, response, False)


@router.post("/login", response_model=SessionView)
def login(data: Login, request: Request, response: Response, db: DB):
    throttle(db, "login:" + request.client.host, 40)
    throttle(db, "account:" + data.email, 12)
    user = db.scalar(select(User).where(User.email == data.email))
    if not matches(user.password_hash if user else dummy, data.password) or not user:
        raise HTTPException(401, "Incorrect email or password")
    return sign_in(db, user, response, data.remember)


@router.get("/session", response_model=SessionView)
def session(auth: Current, db: DB):
    return {"user": db.get(User, auth.user_id), "csrf": auth.csrf}


@router.post("/logout")
def logout(auth: Current, db: DB, response: Response):
    db.delete(auth)
    db.commit()
    response.delete_cookie(
        "od_session", path="/", secure=config.SECURE, httponly=True, samesite="lax"
    )
    return {"ok": True}


@router.put("/profile", response_model=UserView)
def profile(data: Profile, auth: Current, db: DB):
    user = db.get(User, auth.user_id)
    user.name, user.email = data.name, data.email
    save_user(db, user)
    db.commit()
    return user


@router.put("/password", response_model=SessionView)
def password(data: PasswordChange, auth: Current, db: DB, response: Response):
    throttle(db, "password:" + str(auth.user_id), 12)
    user = db.get(User, auth.user_id)
    if not matches(user.password_hash, data.current):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hasher.hash(data.password)
    db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    return sign_in(db, user, response, False)
