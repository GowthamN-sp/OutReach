from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import Integer, func, select

from ..db import lock_user, now, owned
from ..models import Campaign, Contact, Delivery, Event, Message, Resume, Template
from ..schemas import CampaignIn, SendRequest, TemplateIn
from ..security import DB, Current
from ..services.reporting import last_reply
from ..services.sending import missing_fields, preview_message, send
from ..services.tracking import require_tracking_url

router = APIRouter()


def counts(uid):
    def total(model, *conditions):
        return (
            select(func.count())
            .select_from(model)
            .where(model.user_id == uid, model.delivery_id == Delivery.id, *conditions)
            .correlate(Delivery)
            .scalar_subquery()
        )

    return (
        total(Event, Event.kind == "open_signal"),
        total(Event, Event.kind == "link_click"),
        total(Message, Message.direction == "inbound"),
    )


def campaign_rows(db, uid, limit, offset=0, view="all"):
    opens, clicks, replies = counts(uid)
    metrics = (
        select(
            Delivery.campaign_id,
            func.count().label("sent_count"),
            func.sum(Delivery.tracking_open.cast(Integer)).label("open_tracked"),
            func.sum(Delivery.tracking_click.cast(Integer)).label("click_tracked"),
            func.max(
                func.max(
                    Delivery.sent_at,
                    func.coalesce(Delivery.last_open_at, Delivery.sent_at),
                    func.coalesce(Delivery.last_click_at, Delivery.sent_at),
                    func.coalesce(last_reply(uid), Delivery.sent_at),
                )
            ).label("latest_activity"),
            *(
                func.sum((counter > 0).cast(Integer)).label(name)
                for counter, name in zip(
                    (opens, clicks, replies),
                    ("open_count", "click_count", "reply_count"),
                )
            ),
        )
        .where(Delivery.user_id == uid, Delivery.status == "Sent")
        .group_by(Delivery.campaign_id)
        .subquery()
    )
    stmt = (
        select(
            Campaign,
            select(func.count(Delivery.id))
            .where(Delivery.campaign_id == Campaign.id, Delivery.user_id == uid)
            .correlate(Campaign)
            .scalar_subquery()
            .label("delivery_count"),
            metrics.c.sent_count,
            metrics.c.open_count,
            metrics.c.click_count,
            metrics.c.reply_count,
            metrics.c.open_tracked,
            metrics.c.click_tracked,
            metrics.c.latest_activity,
        )
        .outerjoin(metrics, metrics.c.campaign_id == Campaign.id)
        .where(Campaign.user_id == uid)
        .order_by(Campaign.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if view == "deleted":
        stmt = stmt.where(Campaign.deleted_at.is_not(None))
    else:
        stmt = stmt.where(Campaign.deleted_at.is_(None))
        if view == "active":
            stmt = stmt.where(Campaign.archived_at.is_(None))
        elif view == "archived":
            stmt = stmt.where(Campaign.archived_at.is_not(None))
    return [
        {
            **CampaignIn.model_validate(row[0], from_attributes=True).model_dump(),
            "id": row[0].id,
            "created_at": row[0].created_at,
            "archived_at": row[0].archived_at,
            "deleted_at": row[0].deleted_at,
            "attach_resume": bool(row[0].resume_id),
            **{
                k: v or 0
                for k, v in row._mapping.items()
                if k not in {"Campaign", "latest_activity"}
            },
            "latest_activity": row.latest_activity,
        }
        for row in db.execute(stmt)
    ]


@router.get("/campaigns")
def campaigns(
    auth: Current,
    db: DB,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    view: Literal["all", "active", "archived", "deleted"] = "all",
):
    return campaign_rows(db, auth.user_id, limit, offset, view)


@router.delete("/campaigns/{cid}")
def delete_draft(cid: int, auth: Current, db: DB):
    # Same write lock as send reservations. Re-read only after acquiring it.
    lock_user(db, auth.user_id)
    campaign = owned(db, Campaign, auth.user_id, cid)
    if (
        db.scalar(
            select(Delivery.id)
            .where(Delivery.campaign_id == cid, Delivery.user_id == auth.user_id)
            .limit(1)
        )
        is not None
    ):
        raise HTTPException(
            409, "This campaign has delivery history. Archive campaign instead."
        )
    campaign.deleted_at = campaign.deleted_at or now()
    db.commit()
    return {"ok": True}


@router.post("/campaigns/{cid}/archive")
def archive(cid: int, auth: Current, db: DB):
    lock_user(db, auth.user_id)
    campaign = owned(db, Campaign, auth.user_id, cid)
    if campaign.deleted_at:
        raise HTTPException(409, "Restore this deleted draft before archiving")
    campaign.archived_at = campaign.archived_at or now()
    db.commit()
    return {"ok": True}


@router.post("/campaigns/{cid}/restore")
def restore(cid: int, auth: Current, db: DB):
    lock_user(db, auth.user_id)
    campaign = owned(db, Campaign, auth.user_id, cid)
    campaign.deleted_at = campaign.archived_at = None
    db.commit()
    return {"ok": True}


@router.post("/campaigns/{cid}/preview")
def preview(cid: int, data: SendRequest, auth: Current, db: DB):
    if cid != data.campaign_id:
        raise HTTPException(400, "Campaign does not match preview")
    campaign = owned(db, Campaign, auth.user_id, cid)
    if campaign.deleted_at or campaign.archived_at:
        raise HTTPException(409, "Restore this campaign before reviewing recipients")
    resume = (
        owned(db, Resume, auth.user_id, campaign.resume_id)
        if campaign.resume_id
        else None
    )
    rows = []
    for contact_id in dict.fromkeys(data.contact_ids):
        contact = owned(db, Contact, auth.user_id, contact_id)
        delivery = db.scalar(
            select(Delivery).where(
                Delivery.campaign_id == cid,
                Delivery.contact_id == contact.id,
                Delivery.user_id == auth.user_id,
            )
        )
        rows.append(
            {
                "contact_id": contact.id,
                "email": contact.email,
                **preview_message(campaign, contact),
                "missing": missing_fields(campaign, contact),
                "already_sent": bool(delivery and delivery.status != "Failed"),
            }
        )
    return {"recipients": rows, "resume_filename": resume.filename if resume else None}


@router.post("/campaigns", status_code=201)
def create(data: CampaignIn, auth: Current, db: DB):
    require_tracking_url(data.tracking_open, data.tracking_click)
    if data.resume_id is not None:
        owned(db, Resume, auth.user_id, data.resume_id)
    row = Campaign(user_id=auth.user_id, **data.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.get("/campaigns/{cid}/deliveries")
def history(
    cid: int,
    auth: Current,
    db: DB,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    owned(db, Campaign, auth.user_id, cid)
    d = Delivery
    o, c, r = counts(auth.user_id)
    stmt = (
        select(
            d.id,
            d.contact_id,
            d.status,
            d.sent_at,
            d.error,
            d.tracking_open,
            d.tracking_click,
            d.first_open_at,
            d.first_click_at,
            d.recipient.label("email"),
            Contact.name,
            Contact.company,
            o.label("opens"),
            c.label("clicks"),
            r.label("replies"),
        )
        .join(Contact, Contact.id == d.contact_id)
        .where(
            d.user_id == auth.user_id,
            Contact.user_id == auth.user_id,
            d.campaign_id == cid,
        )
        .order_by(d.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [dict(row) for row in db.execute(stmt).mappings()]


@router.get("/templates")
def templates(auth: Current, db: DB):
    return db.scalars(
        select(Template).where(Template.user_id == auth.user_id).order_by(Template.name)
    ).all()


@router.post("/templates", status_code=201)
def template(data: TemplateIn, auth: Current, db: DB):
    row = Template(user_id=auth.user_id, **data.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.post("/send")
async def send_campaign(data: SendRequest, auth: Current, db: DB):
    return await send(db, auth.user_id, data)
