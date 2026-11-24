"""Owner-scoped reporting. Rates count unique accepted messages, not requests."""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import now
from ..models import Delivery, Event, Message, ReplyAttempt


def reply_count(uid: int):
    return (
        select(func.count(Message.id))
        .where(
            Message.user_id == uid,
            Message.delivery_id == Delivery.id,
            Message.direction == "inbound",
        )
        .correlate(Delivery)
        .scalar_subquery()
    )


def last_reply(uid: int):
    return (
        select(func.max(Message.received_at))
        .where(
            Message.user_id == uid,
            Message.delivery_id == Delivery.id,
            Message.direction == "inbound",
        )
        .correlate(Delivery)
        .scalar_subquery()
    )


def metrics(db: Session, uid: int, campaign_id: int | None = None) -> dict:
    conditions = [Delivery.user_id == uid, Delivery.status == "Sent"]
    if campaign_id is not None:
        conditions.append(Delivery.campaign_id == campaign_id)

    def count(*extra) -> int:
        return db.scalar(select(func.count(Delivery.id)).where(*conditions, *extra))

    sent = count()
    opened = count(Delivery.tracking_open, Delivery.first_open_at.is_not(None))
    clicked = count(Delivery.tracking_click, Delivery.first_click_at.is_not(None))
    open_tracked = count(Delivery.tracking_open)
    click_tracked = count(Delivery.tracking_click)
    replies = count(reply_count(uid) > 0)
    accepted_replies_query = select(func.count(ReplyAttempt.id)).where(
        ReplyAttempt.user_id == uid, ReplyAttempt.status == "Sent"
    )
    if campaign_id is not None:
        accepted_replies_query = accepted_replies_query.join(
            Delivery, Delivery.id == ReplyAttempt.delivery_id
        ).where(Delivery.user_id == uid, Delivery.campaign_id == campaign_id)
    accepted_replies = db.scalar(accepted_replies_query)

    def rate(numerator: int, denominator: int) -> float | None:
        return round(100 * numerator / denominator, 1) if denominator else None

    return {
        "sent": sent,
        "accepted_replies": accepted_replies,
        "accepted_total": sent + accepted_replies,
        "open_signals": opened,
        "click_signals": clicked,
        "open_tracked": open_tracked,
        "click_tracked": click_tracked,
        "open_rate": rate(opened, open_tracked),
        "click_rate": rate(clicked, click_tracked),
        "replies": replies,
        "reply_rate": rate(replies, sent),
        # No scheduler/status field exists: active means accepted outreach in 14 days.
        "active_campaigns": db.scalar(
            select(func.count(func.distinct(Delivery.campaign_id))).where(
                *conditions, Delivery.sent_at >= now() - timedelta(days=14)
            )
        ),
    }


def trends(db: Session, uid: int, campaign_id: int | None = None) -> list[dict]:
    today = now().date()
    start = today - timedelta(days=13)
    conditions = [Delivery.user_id == uid, Delivery.status == "Sent"]
    if campaign_id is not None:
        conditions.append(Delivery.campaign_id == campaign_id)
    day = func.date(Delivery.sent_at)
    sent = dict(
        db.execute(
            select(day, func.count())
            .where(*conditions, Delivery.sent_at >= start)
            .group_by(day)
        ).all()
    )
    event_day = func.date(Event.occurred)
    events = {
        (d, kind): count
        for d, kind, count in db.execute(
            select(event_day, Event.kind, func.count(func.distinct(Event.delivery_id)))
            .join(Delivery, Delivery.id == Event.delivery_id)
            .where(*conditions, Event.user_id == uid, Event.occurred >= start)
            .group_by(event_day, Event.kind)
        )
    }
    reply_day = func.date(Message.received_at)
    replies = dict(
        db.execute(
            select(reply_day, func.count(func.distinct(Message.delivery_id)))
            .join(Delivery, Delivery.id == Message.delivery_id)
            .where(
                *conditions,
                Message.user_id == uid,
                Message.direction == "inbound",
                Message.received_at >= start,
            )
            .group_by(reply_day)
        ).all()
    )
    return [
        {
            "day": str(d),
            "sent": sent.get(str(d), 0),
            "open_signals": events.get((str(d), "open_signal"), 0),
            "click_signals": events.get((str(d), "link_click"), 0),
            "replies": replies.get(str(d), 0),
        }
        for d in (start + timedelta(days=i) for i in range(14))
    ]
