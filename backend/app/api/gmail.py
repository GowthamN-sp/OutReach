import secrets
from datetime import timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import update

from .. import config
from ..db import now
from ..integrations import google
from ..models import GmailAccount, LoginSession
from ..security import DB, Current, digest

router = APIRouter(prefix="/auth/google")


@router.post("/start")
def start(auth: Current, db: DB):
    state = secrets.token_urlsafe(32)
    url = google.authorization_url(state)
    auth.oauth_state = digest(state)
    auth.oauth_expires = now() + timedelta(minutes=10)
    db.commit()
    return {"url": url}


@router.get("/callback")
async def callback(
    auth: Current, db: DB, state: str = "", code: str = "", error: str = ""
):
    changed = db.execute(
        update(LoginSession)
        .where(
            LoginSession.digest == auth.digest,
            LoginSession.oauth_state == digest(state),
            LoginSession.oauth_expires > now(),
        )
        .values(oauth_state=None, oauth_expires=None)
        .execution_options(synchronize_session=False)
    )
    if not changed.rowcount:
        raise HTTPException(400, "Invalid or expired Google authorization request")
    db.commit()
    if error or not code:
        return RedirectResponse(config.FRONT + "/settings?oauth=denied")
    token = await google.exchange(
        code=code, redirect_uri=config.REDIRECT, grant_type="authorization_code"
    )
    if not token.get("refresh_token") or not set(google.SCOPES.split()).issubset(
        token.get("scope", "").split()
    ):
        raise HTTPException(400, "Grant Gmail send and read access, then reconnect")
    profile = await google.call(token["access_token"], "GET", "profile")
    _, _, cipher = google.credentials()
    db.merge(
        GmailAccount(
            user_id=auth.user_id,
            email=profile["emailAddress"].lower(),
            refresh=cipher.encrypt(token["refresh_token"].encode()).decode(),
        )
    )
    db.commit()
    return RedirectResponse(config.FRONT + "/settings?oauth=connected")


@router.post("/disconnect")
def disconnect(auth: Current, db: DB):
    account = db.get(GmailAccount, auth.user_id)
    if account:
        db.delete(account)
    auth.oauth_state = None
    db.commit()
    return {"ok": True}
