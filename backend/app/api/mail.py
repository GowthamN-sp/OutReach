from datetime import timedelta

import httpx
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..db import lock_user, now
from ..models import Contact, Delivery, InboxSync, Message
from ..schemas import Reply
from ..security import DB, Current
from ..services import inbox

router = APIRouter()


@router.get("/inbox")
def messages(
    auth: Current,
    db: DB,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    stmt = (
        select(Message, Contact.name, Contact.company)
        .join(Delivery, Delivery.id == Message.delivery_id)
        .join(Contact, Contact.id == Delivery.contact_id)
        .where(
            Message.user_id == auth.user_id,
            Delivery.user_id == auth.user_id,
            Contact.user_id == auth.user_id,
        )
        .order_by(Message.received_at.desc(), Message.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        {
            **{
                k: getattr(m, k)
                for k in (
                    "id",
                    "gmail_thread_id",
                    "mailbox",
                    "sender",
                    "recipient",
                    "subject",
                    "body",
                    "received_at",
                    "direction",
                )
            },
            "contact_name": name,
            "company": company,
        }
        for m, name, company in db.execute(stmt)
    ]


@router.post("/inbox/sync")
async def sync(auth: Current, db: DB):
    lock_user(db, auth.user_id)
    status = db.get(InboxSync, auth.user_id)
    if (
        status
        and status.status == "running"
        and status.occurred > now() - timedelta(minutes=10)
    ):
        raise HTTPException(409, "A Gmail sync is already in progress. Retry shortly.")
    if status is None:
        status = InboxSync(user_id=auth.user_id)
        db.add(status)
    status.status, status.detail, status.occurred = (
        "running",
        "Gmail sync started",
        now(),
    )
    db.commit()
    try:
        result = await inbox.sync(db, auth.user_id)
    except Exception as exc:
        db.rollback()
        status = db.get(InboxSync, auth.user_id)
        status.status = "failed"
        status.detail = (
            str(exc.detail)
            if isinstance(exc, HTTPException)
            else (
                "Google could not be reached. Retry sync."
                if isinstance(exc, httpx.HTTPError)
                else "Sync could not be completed. Retry sync."
            )
        )
        status.occurred = now()
        db.commit()
        raise
    status.status = "success"
    status.detail = (
        f"{result['threads_checked']} threads checked; {result['added']} new messages"
    )
    status.occurred = now()
    db.commit()
    return result


@router.get("/inbox/sync-status")
def sync_status(auth: Current, db: DB):
    status = db.get(InboxSync, auth.user_id)
    return (
        {"status": status.status, "detail": status.detail, "occurred": status.occurred}
        if status
        else None
    )


@router.post("/inbox/{mid}/reply")
async def reply(mid: int, data: Reply, auth: Current, db: DB):
    return await inbox.reply(db, auth.user_id, mid, data)
