import os
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from .. import config

SCOPES = "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me/"


def credentials():
    client = os.getenv("GOOGLE_CLIENT_ID")
    secret = os.getenv("GOOGLE_CLIENT_SECRET")
    try:
        cipher = Fernet(os.environ["ENCRYPTION_KEY"])
        if not client or not secret:
            raise ValueError()
    except (KeyError, ValueError):
        raise HTTPException(
            503, "Configure Google OAuth credentials and the encryption key"
        )
    return client, secret, cipher


def authorization_url(state: str) -> str:
    client, _, _ = credentials()
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": client,
            "redirect_uri": config.REDIRECT,
            "scope": SCOPES,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )


async def exchange(**params):
    client, secret, _ = credentials()
    async with httpx.AsyncClient(timeout=20) as http:
        r = await http.post(
            TOKEN_URL, data={"client_id": client, "client_secret": secret, **params}
        )
    if not r.is_success or not r.json().get("access_token"):
        raise HTTPException(
            502, "Google authorization failed. Reconnect Gmail in Settings."
        )
    return r.json()


async def access(account):
    if not account:
        raise HTTPException(409, "Connect Gmail in Settings first")
    _, _, cipher = credentials()
    try:
        token = cipher.decrypt(account.refresh.encode()).decode()
    except InvalidToken:
        raise HTTPException(
            503, "Stored credential cannot be decrypted. Restore the encryption key."
        )
    return (await exchange(grant_type="refresh_token", refresh_token=token))[
        "access_token"
    ]


class Rejected(HTTPException):
    """Google explicitly rejected this request before accepting a message."""


async def call(token, method, path, **kwargs):
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.request(
            method, GMAIL + path, headers={"Authorization": "Bearer " + token}, **kwargs
        )
    if 400 <= r.status_code < 500:
        raise Rejected(
            502,
            f"Google rejected the request ({r.status_code}). Check permissions and quota.",
        )
    if not r.is_success:
        raise HTTPException(502, "Google is temporarily unavailable")
    return r.json()
