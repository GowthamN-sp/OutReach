import base64
import html
import re
import secrets
from datetime import timedelta
from email.message import EmailMessage

import httpx
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import config
from ..db import lock_user, now, owned
from ..integrations import google
from ..models import Campaign, Contact, Delivery, GmailAccount, Link, Resume
from .email_html import render
from .tracking import require_tracking_url


def substitute(text: str, contact: Contact, escape: bool = False) -> str:
    fields = {
        "name": contact.name or "there",
        "company": contact.company or "your organization",
        "role": contact.role or "a suitable role",
    }
    return re.sub(
        r"{{(name|company|role)}}",
        lambda m: html.escape(fields[m[1]], quote=True) if escape else fields[m[1]],
        text,
    )


def message(
    db: Session,
    delivery: Delivery,
    campaign: Campaign,
    contact: Contact,
    resume: Resume | None,
) -> str:
    require_tracking_url(campaign.tracking_open, campaign.tracking_click)
    body = substitute(campaign.body, contact, escape=True)
    delivery.body = substitute(campaign.body, contact)
    delivery.subject = substitute(campaign.subject, contact)
    delivery.tracking_open = campaign.tracking_open
    delivery.tracking_click = campaign.tracking_click

    def link(target: str) -> str:
        token = secrets.token_urlsafe(28)
        db.add(
            Link(
                user_id=delivery.user_id,
                delivery_id=delivery.id,
                token=token,
                target=target,
            )
        )
        return f"{config.PUBLIC}/api/track/click/{token}"

    plain, markup = render(body, link if campaign.tracking_click else None)
    if campaign.tracking_open:
        markup += f'<img alt="" width="1" height="1" src="{config.PUBLIC}/api/track/open/{delivery.token}">'
    msg = EmailMessage()
    msg["From"] = delivery.mailbox
    msg["To"] = contact.email
    msg["Subject"] = delivery.subject
    msg.set_content(plain, charset="utf-8")
    msg.add_alternative(markup, subtype="html", charset="utf-8")
    if resume:
        msg.add_attachment(
            resume.content,
            maintype="application",
            subtype="pdf",
            filename=resume.filename,
        )
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def quota(db, uid, quantity):
    from ..models import ReplyAttempt

    cutoff = now() - timedelta(days=1)
    used = sum(
        db.scalar(
            select(func.count())
            .select_from(model)
            .where(
                model.user_id == uid, model.sent_at >= cutoff, model.status != "Failed"
            )
        )
        for model in (Delivery, ReplyAttempt)
    )
    if used + quantity > config.LIMIT:
        raise HTTPException(429, "This batch would exceed your 24-hour sending limit")


async def send(db, uid, request):
    if not request.confirm:
        raise HTTPException(400, "Review and confirm the recipients before sending")
    campaign = owned(db, Campaign, uid, request.campaign_id)
    require_tracking_url(campaign.tracking_open, campaign.tracking_click)
    contacts = [
        owned(db, Contact, uid, cid) for cid in dict.fromkeys(request.contact_ids)
    ]
    resume = owned(db, Resume, uid, campaign.resume_id) if campaign.resume_id else None
    account = db.get(GmailAccount, uid)
    token = await google.access(account)
    lock_user(db, uid)
    pending = []
    results = []
    for contact in contacts:
        delivery = db.scalar(
            select(Delivery).where(
                Delivery.user_id == uid,
                Delivery.campaign_id == campaign.id,
                Delivery.contact_id == contact.id,
            )
        )
        if delivery and delivery.status != "Failed":
            results.append(
                {
                    "contact_id": contact.id,
                    "status": "Skipped",
                    "error": "Already sent or awaiting reconciliation",
                }
            )
            continue
        if not delivery:
            delivery = Delivery(
                user_id=uid,
                campaign_id=campaign.id,
                contact_id=contact.id,
                token=secrets.token_urlsafe(32),
            )
            db.add(delivery)
        else:
            db.execute(
                delete(Link).where(Link.delivery_id == delivery.id, Link.user_id == uid)
            )
            delivery.token = secrets.token_urlsafe(32)
        delivery.status = "Preparing"
        delivery.mailbox = account.email
        delivery.recipient = contact.email
        delivery.sent_at = now()
        delivery.error = None
        pending.append((delivery, contact))
    # Reservations already count toward the rolling limit in this transaction.
    quota(db, uid, 0)
    db.flush()
    prepared = [(d, c, message(db, d, campaign, c, resume)) for d, c in pending]
    db.commit()
    for delivery, contact, raw in prepared:
        try:
            result = await google.call(
                token, "POST", "messages/send", json={"raw": raw}
            )
            if not result.get("id") or not result.get("threadId"):
                raise HTTPException(502, "Missing Gmail confirmation")
            delivery.gmail_message_id = result["id"]
            delivery.gmail_thread_id = result["threadId"]
            delivery.sent_at = now()
            delivery.status = "Sent"
            contact.status = "Contacted"
        except google.Rejected as exc:
            delivery.status = "Failed"
            delivery.error = exc.detail
        except (httpx.HTTPError, HTTPException):
            delivery.status = "Unconfirmed"
            delivery.error = (
                "Acceptance is unknown. Check Gmail Sent before taking further action."
            )
        db.commit()
        results.append(
            {
                "contact_id": contact.id,
                "status": delivery.status,
                "error": delivery.error,
            }
        )
    return {"results": results, "sent": sum(row["status"] == "Sent" for row in results)}
