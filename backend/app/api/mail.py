from fastapi import APIRouter, Query
from sqlalchemy import select

from ..models import Contact, Delivery, Message
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
    return await inbox.sync(db, auth.user_id)


@router.post("/inbox/{mid}/reply")
async def reply(mid: int, data: Reply, auth: Current, db: DB):
    return await inbox.reply(db, auth.user_id, mid, data)
