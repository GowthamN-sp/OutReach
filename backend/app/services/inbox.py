import base64
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import parseaddr

import httpx
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from ..db import lock_user, now, owned
from ..integrations import google
from ..models import Contact, Delivery, GmailAccount, Message, ReplyAttempt
from .sending import quota


def decoded_body(payload):
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        try:
            return base64.urlsafe_b64decode(payload["body"]["data"] + "===").decode(
                errors="replace"
            )[:15000]
        except ValueError:
            return ""
    return next(
        (text for part in payload.get("parts", []) if (text := decoded_body(part))), ""
    )


async def sync(db, uid):
    account = db.get(GmailAccount, uid)
    access = await google.access(account)
    deliveries = db.scalars(
        select(Delivery)
        .where(
            Delivery.user_id == uid,
            Delivery.mailbox == account.email,
            Delivery.status == "Sent",
        )
        .order_by(Delivery.id.desc())
    ).all()
    added = 0
    threads = {}
    for d in deliveries:
        threads.setdefault(d.gmail_thread_id, d)
    for tid, delivery in list(threads.items())[:120]:
        thread = await google.call(
            access, "GET", "threads/" + tid, params={"format": "full"}
        )
        contact = owned(db, Contact, uid, delivery.contact_id)
        lock_user(db, uid)
        for msg in thread.get("messages", []):
            payload = msg.get("payload", {})
            headers = {
                h["name"].lower(): h["value"] for h in payload.get("headers", [])
            }
            sender = headers.get("from", "")
            inbound = parseaddr(sender)[1].lower() == delivery.recipient
            direction = (
                "inbound"
                if inbound
                else "outbound"
                if parseaddr(sender)[1].lower() == account.email
                else "other"
            )
            try:
                with db.begin_nested():
                    db.add(
                        Message(
                            user_id=uid,
                            delivery_id=delivery.id,
                            gmail_message_id=msg["id"],
                            gmail_thread_id=tid,
                            mailbox=account.email,
                            sender=sender,
                            recipient=headers.get("to", ""),
                            subject=headers.get("subject", ""),
                            body=decoded_body(payload),
                            received_at=datetime.fromtimestamp(
                                int(msg["internalDate"]) / 1000, UTC
                            ).replace(tzinfo=None),
                            direction=direction,
                            internet_id=headers.get("message-id", ""),
                        )
                    )
                    db.flush()
                added += 1
                if inbound:
                    contact.status = "Replied"
            except IntegrityError:
                if headers.get("message-id"):
                    db.execute(
                        update(Message)
                        .where(
                            Message.user_id == uid,
                            Message.mailbox == account.email,
                            Message.gmail_message_id == msg["id"],
                            Message.internet_id == "",
                        )
                        .values(internet_id=headers["message-id"])
                    )
        db.commit()
    return {"threads_checked": min(120, len(threads)), "added": added}


async def reply(db, uid, mid, data):
    original = owned(db, Message, uid, mid)
    account = db.get(GmailAccount, uid)
    access = await google.access(account)
    if original.mailbox != account.email:
        raise HTTPException(409, "Reconnect the mailbox that owns this conversation")
    delivery = owned(db, Delivery, uid, original.delivery_id)
    msg = EmailMessage()
    msg["From"] = account.email
    msg["To"] = delivery.recipient
    msg["Subject"] = original.subject
    if not original.internet_id:
        raise HTTPException(
            409,
            "Sync this conversation to retrieve its reply headers, or open it in Gmail.",
        )
    msg["In-Reply-To"] = original.internet_id
    msg["References"] = original.internet_id
    from .email_html import render

    plain, markup = render(data.body)
    msg.set_content(plain, charset="utf-8")
    msg.add_alternative(markup, subtype="html", charset="utf-8")
    lock_user(db, uid)
    attempt = db.scalar(
        select(ReplyAttempt).where(
            ReplyAttempt.user_id == uid, ReplyAttempt.key == str(data.request_id)
        )
    )
    if attempt and attempt.status != "Failed":
        raise HTTPException(
            409,
            "This reply has already been submitted. Sync the thread to check its status.",
        )
    quota(db, uid, 1)
    if not attempt:
        attempt = ReplyAttempt(user_id=uid, key=str(data.request_id))
        db.add(attempt)
    attempt.status = "Preparing"
    attempt.delivery_id = delivery.id
    attempt.subject = original.subject
    attempt.body = data.body
    attempt.sent_at = now()
    db.commit()
    try:
        result = await google.call(
            access,
            "POST",
            "messages/send",
            json={
                "raw": base64.urlsafe_b64encode(msg.as_bytes()).decode(),
                "threadId": original.gmail_thread_id,
            },
        )
        if not result.get("id"):
            raise HTTPException(502, "Missing Gmail confirmation")
    except google.Rejected:
        attempt.status = "Failed"
        db.commit()
        raise
    except (httpx.HTTPError, HTTPException):
        attempt.status = "Unconfirmed"
        db.commit()
        raise HTTPException(502, "Check Gmail Sent before retrying this reply")
    attempt.status = "Sent"
    attempt.gmail_message_id = result["id"]
    attempt.sent_at = now()
    db.commit()
    return {"id": result["id"]}
