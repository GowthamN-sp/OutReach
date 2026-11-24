import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import config
from .db import database, now
from .models import Attempt, LoginSession, User

DB = Annotated[Session, Depends(database)]
hasher = PasswordHasher()
dummy = hasher.hash(secrets.token_urlsafe(32))


def matches(encoded: str, password: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except VerifyMismatchError:
        return False


def throttle(db: Session, bucket: str, maximum: int) -> None:
    cutoff = now() - timedelta(minutes=15)
    db.execute(delete(Attempt).where(Attempt.occurred < cutoff))
    count = db.scalar(
        select(func.count()).select_from(Attempt).where(Attempt.bucket == bucket)
    )
    if count >= maximum:
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    db.add(Attempt(bucket=bucket))
    db.commit()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def active_session(request: Request, db: DB) -> LoginSession:
    session = db.get(LoginSession, digest(request.cookies.get("od_session", "")))
    if not session or session.expires <= now():
        raise HTTPException(401, "Please sign in again")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not secrets.compare_digest(
        session.csrf, request.headers.get("X-CSRF-Token", "")
    ):
        raise HTTPException(403, "Please refresh this page before trying again")
    return session


Current = Annotated[LoginSession, Depends(active_session)]


def sign_in(db: Session, user: User, response: Response, remember: bool):
    raw = secrets.token_urlsafe(40)
    ttl = timedelta(days=14) if remember else timedelta(hours=12)
    session = LoginSession(
        digest=digest(raw),
        user_id=user.id,
        csrf=secrets.token_urlsafe(32),
        expires=now() + ttl,
    )
    db.execute(delete(LoginSession).where(LoginSession.expires <= now()))
    db.add(session)
    db.commit()
    response.set_cookie(
        "od_session",
        raw,
        httponly=True,
        secure=config.SECURE,
        samesite="lax",
        path="/",
        max_age=int(ttl.total_seconds()) if remember else None,
    )
    return {"csrf": session.csrf, "user": user}
