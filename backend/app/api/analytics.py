from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from .. import config
from ..db import owned
from ..models import (
    Campaign,
    Contact,
    Delivery,
    Event,
    GmailAccount,
    Message,
    Resume,
    User,
)
from ..security import DB, Current
from ..services.email_html import public_origin
from ..services.reporting import last_reply, metrics, reply_count, trends
from .campaigns import campaign_rows

router = APIRouter()


@router.get("/bootstrap")
def bootstrap(auth: Current, db: DB):
    account = db.get(GmailAccount, auth.user_id)
    user = db.get(User, auth.user_id)
    default = db.scalar(
        select(Resume.name).where(Resume.user_id == auth.user_id, Resume.is_default)
    )
    return {
        "gmail_connected": bool(account),
        "gmail_email": account.email if account else None,
        "resume": default,
        "tracking_ready": public_origin(config.PUBLIC),
        "tracking_open": user.tracking_open,
        "tracking_click": user.tracking_click,
        "daily_limit": config.LIMIT,
    }


def activity(
    db,
    uid,
    limit,
    offset=0,
    cid=None,
    campaign_id=None,
    search="",
    status="",
    signal="",
    delivery_id=None,
):
    stmt = (
        select(
            Delivery,
            Contact.name,
            Contact.company,
            Campaign.name.label("campaign"),
            reply_count(uid).label("replies"),
            last_reply(uid).label("last_reply_at"),
        )
        .join(Contact, Contact.id == Delivery.contact_id)
        .join(Campaign, Campaign.id == Delivery.campaign_id)
        .where(Delivery.user_id == uid, Contact.user_id == uid, Campaign.user_id == uid)
    )
    if cid is not None:
        owned(db, Contact, uid, cid)
        stmt = stmt.where(Contact.id == cid)
    if campaign_id is not None:
        owned(db, Campaign, uid, campaign_id)
        stmt = stmt.where(Campaign.id == campaign_id)
    if delivery_id is not None:
        stmt = stmt.where(Delivery.id == delivery_id)
    if search:
        stmt = stmt.where(
            or_(
                *(
                    column.icontains(search, autoescape=True)
                    for column in (
                        Contact.name,
                        Contact.company,
                        Delivery.recipient,
                        func.coalesce(Delivery.subject, Campaign.subject),
                    )
                )
            )
        )
    if status:
        stmt = stmt.where(Delivery.status == status)
    if signal == "open":
        stmt = stmt.where(Delivery.first_open_at.is_not(None))
    elif signal == "click":
        stmt = stmt.where(Delivery.first_click_at.is_not(None))
    elif signal == "reply":
        stmt = stmt.where(reply_count(uid) > 0)
    elif signal == "untracked":
        stmt = stmt.where(~Delivery.tracking_open, ~Delivery.tracking_click)
    rows = []
    for d, name, company, campaign, replies, replied_at in db.execute(
        stmt.order_by(Delivery.id.desc()).offset(offset).limit(limit)
    ):
        rows.append(
            {
                **{
                    key: getattr(d, key)
                    for key in (
                        "id",
                        "campaign_id",
                        "subject",
                        "sent_at",
                        "status",
                        "error",
                        "tracking_open",
                        "tracking_click",
                        "first_open_at",
                        "last_open_at",
                        "open_requests",
                        "first_click_at",
                        "last_click_at",
                        "click_requests",
                    )
                },
                "email": d.recipient,
                "name": name,
                "company": company,
                "campaign": campaign,
                "replies": replies,
                "last_activity": max(
                    t
                    for t in (d.sent_at, d.last_open_at, d.last_click_at, replied_at)
                    if t
                ),
            }
        )
    return rows


@router.get("/sent")
def sent(
    auth: Current,
    db: DB,
    contact_id: int | None = None,
    campaign_id: int | None = None,
    search: str = Query("", max_length=250),
    status: str = "",
    signal: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    return activity(
        db, auth.user_id, limit, offset, contact_id, campaign_id, search, status, signal
    )


@router.get("/sent/{did}")
def detail(did: int, auth: Current, db: DB):
    delivery = owned(db, Delivery, auth.user_id, did)
    return {
        **activity(db, auth.user_id, 1, delivery_id=did)[0],
        "body": delivery.body,
        "body_available": delivery.body is not None,
    }


@router.get("/sent/{did}/events")
def events(
    did: int,
    auth: Current,
    db: DB,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    owned(db, Delivery, auth.user_id, did)
    return [
        dict(row)
        for row in db.execute(
            select(Event.id, Event.kind, Event.occurred)
            .where(Event.delivery_id == did, Event.user_id == auth.user_id)
            .order_by(Event.occurred.desc(), Event.id.desc())
            .offset(offset)
            .limit(limit)
        ).mappings()
    ]


@router.get("/sent/{did}/replies")
def replies(
    did: int,
    auth: Current,
    db: DB,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    owned(db, Delivery, auth.user_id, did)
    return [
        dict(row)
        for row in db.execute(
            select(
                Message.id,
                Message.subject,
                Message.body,
                Message.received_at,
                Message.sender,
            )
            .where(
                Message.delivery_id == did,
                Message.user_id == auth.user_id,
                Message.direction == "inbound",
            )
            .order_by(Message.received_at.desc(), Message.id.desc())
            .offset(offset)
            .limit(limit)
        ).mappings()
    ]


@router.get("/analytics")
def analytics(auth: Current, db: DB, campaign_id: int | None = None):
    uid = auth.user_id
    if campaign_id is not None:
        owned(db, Campaign, uid, campaign_id)
    return {
        **metrics(db, uid, campaign_id),
        "contacts": db.scalar(
            select(func.count(Contact.id)).where(Contact.user_id == uid)
        ),
        "days": trends(db, uid, campaign_id),
        "recent": activity(db, uid, 8, campaign_id=campaign_id),
        "campaigns": campaign_rows(db, uid, 5),
    }
