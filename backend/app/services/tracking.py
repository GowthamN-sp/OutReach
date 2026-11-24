"""Configuration and transactional signal recording (no client metadata)."""

from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from .. import config
from ..db import now
from ..models import Delivery, Event
from .email_html import public_origin


def require_tracking_url(open_enabled: bool, click_enabled: bool) -> None:
    if (open_enabled or click_enabled) and not public_origin(config.PUBLIC):
        raise HTTPException(
            400,
            "Tracking requires PUBLIC_BASE_URL to be a public HTTPS origin. Configure it and restart the backend.",
        )


def record_signal(
    db: Session,
    delivery: Delivery,
    kind: str,
    identifier: str,
    link_id: int | None = None,
) -> None:
    signal = "open" if kind == "open_signal" else "click"
    timestamp = now()
    first = getattr(Delivery, f"first_{signal}_at")
    last = getattr(Delivery, f"last_{signal}_at")
    count = getattr(Delivery, f"{signal}_requests")
    db.execute(
        update(Delivery)
        .where(Delivery.id == delivery.id)
        .values(
            {
                first: func.min(func.coalesce(first, timestamp), timestamp),
                last: func.max(func.coalesce(last, timestamp), timestamp),
                count: count + 1,
            }
        ),
        execution_options={"synchronize_session": False},
    )
    db.add(
        Event(
            user_id=delivery.user_id,
            delivery_id=delivery.id,
            kind=kind,
            occurred=timestamp,
            tracking_identifier=identifier,
            link_id=link_id,
        )
    )
    db.commit()
