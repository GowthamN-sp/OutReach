import base64
import re

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from ..models import Delivery, Link
from ..security import DB
from ..services.email_html import safe_url
from ..services.tracking import record_signal

router = APIRouter()
GIF = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
    "Referrer-Policy": "no-referrer",
}


def valid_token(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{16,128}", token))


@router.get("/track/open/{token}")
@router.get("/o/{token}.gif", include_in_schema=False)
def image(token: str, db: DB):
    delivery = (
        db.scalar(
            select(Delivery).where(
                Delivery.token == token,
                Delivery.status == "Sent",
                Delivery.tracking_open,
            )
        )
        if valid_token(token)
        else None
    )
    if delivery:
        record_signal(db, delivery, "open_signal", token)
    return Response(GIF, media_type="image/gif", headers=HEADERS)


@router.get("/track/click/{token}")
@router.get("/t/{token}", include_in_schema=False)
def click(token: str, db: DB):
    row = (
        db.execute(
            select(Link, Delivery)
            .join(Delivery)
            .where(
                Link.token == token,
                Link.user_id == Delivery.user_id,
                Delivery.status == "Sent",
                Delivery.tracking_click,
            )
        ).first()
        if valid_token(token)
        else None
    )
    if not row or not safe_url(row[0].target):
        raise HTTPException(404, "Link not found")
    link, delivery = row
    record_signal(db, delivery, "link_click", token, link.id)
    return RedirectResponse(link.target, status_code=302, headers=HEADERS)
