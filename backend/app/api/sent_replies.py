"""Sent reply snapshots complement campaign deliveries without enabling tracking."""

from fastapi import APIRouter, Query
from sqlalchemy import and_, or_, select

from ..db import owned
from ..models import Campaign, Contact, Delivery, ReplyAttempt
from ..security import DB, Current

router = APIRouter()


def rows(
    db,
    uid: int,
    limit: int,
    offset: int = 0,
    search: str = "",
    status: str = "",
    campaign_id: int | None = None,
    rid: int | None = None,
) -> list[dict]:
    stmt = (
        select(
            ReplyAttempt,
            Delivery.recipient,
            Contact.name,
            Contact.company,
            Campaign.name,
            Campaign.id,
        )
        .outerjoin(
            Delivery,
            and_(Delivery.id == ReplyAttempt.delivery_id, Delivery.user_id == uid),
        )
        .outerjoin(
            Contact, and_(Contact.id == Delivery.contact_id, Contact.user_id == uid)
        )
        .outerjoin(
            Campaign, and_(Campaign.id == Delivery.campaign_id, Campaign.user_id == uid)
        )
        .where(ReplyAttempt.user_id == uid)
    )
    if rid is not None:
        stmt = stmt.where(ReplyAttempt.id == rid)
    if search:
        stmt = stmt.where(
            or_(
                *(
                    column.icontains(search, autoescape=True)
                    for column in (
                        ReplyAttempt.subject,
                        Delivery.recipient,
                        Contact.name,
                        Contact.company,
                    )
                )
            )
        )
    if status:
        stmt = stmt.where(ReplyAttempt.status == status)
    if campaign_id is not None:
        owned(db, Campaign, uid, campaign_id)
        stmt = stmt.where(Campaign.id == campaign_id)
    result = []
    for reply, email, name, company, campaign, cid in db.execute(
        stmt.order_by(ReplyAttempt.id.desc()).offset(offset).limit(limit)
    ):
        result.append(
            {
                "id": reply.id,
                "email": email or "Historical recipient unavailable",
                "name": name,
                "company": company,
                "campaign": campaign or "Historical reply",
                "campaign_id": cid,
                "subject": reply.subject,
                "body": reply.body,
                "body_available": reply.body is not None,
                "sent_at": reply.sent_at,
                "last_activity": reply.sent_at,
                "status": reply.status,
                "error": None,
                "tracking_open": False,
                "tracking_click": False,
                "first_open_at": None,
                "last_open_at": None,
                "first_click_at": None,
                "last_click_at": None,
                "open_requests": 0,
                "click_requests": 0,
                "replies": 0,
            }
        )
    return result


@router.get("/sent-replies")
def sent_replies(
    auth: Current,
    db: DB,
    search: str = Query("", max_length=250),
    status: str = "",
    campaign_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    return rows(db, auth.user_id, limit, offset, search, status, campaign_id)


@router.get("/sent-replies/{rid}")
def detail(rid: int, auth: Current, db: DB):
    owned(db, ReplyAttempt, auth.user_id, rid)
    return rows(db, auth.user_id, 1, rid=rid)[0]
