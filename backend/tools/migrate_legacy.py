"""Copy a verified single-owner v1 archive into an empty v2 account."""

import argparse
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import (
    Campaign,
    Contact,
    Delivery,
    Event,
    GmailAccount,
    Link,
    Message,
    Resume,
    Template,
    User,
)
from app.services.email_html import safe_url


def stamp(value):
    dt = datetime.fromisoformat(value)
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def migrate(source: Path, owner: str, resume: Path | None, apply: bool):
    with (
        closing(
            sqlite3.connect(source.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
        ) as old,
        Session(engine) as db,
    ):
        old.row_factory = sqlite3.Row
        old.execute("BEGIN")
        user = db.scalar(select(User).where(User.email == owner.strip().lower()))
        if not user:
            raise ValueError("Register the intended owner in v2 first.")
        uid = user.id
        for model in (
            Contact,
            Campaign,
            Delivery,
            Event,
            Link,
            Message,
            Resume,
            Template,
            GmailAccount,
        ):
            if (
                db.scalar(select(model.user_id).where(model.user_id == uid).limit(1))
                is not None
            ):
                raise ValueError("The destination workspace must be empty.")

        def setting(key):
            row = old.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row[0] if row else ""

        def add(model, **fields):
            row = model(user_id=uid, **fields)
            db.add(row)
            db.flush()
            return row.id

        filename = setting("resume_original")
        rid = None
        if resume:
            content = resume.read_bytes()
            if len(content) > 8 * 1024 * 1024 or not content.startswith(b"%PDF-"):
                raise ValueError("Provide the original PDF, up to 8 MB.")
            rid = add(
                Resume,
                name=filename or resume.name,
                filename=Path(filename or resume.name).name,
                content=content,
                size=len(content),
                is_default=True,
            )
        contacts = {}
        addresses = {}
        for row in old.execute("SELECT * FROM contacts"):
            addresses[row["id"]] = row["email"].strip().lower()
            contacts[row["id"]] = add(
                Contact,
                **{k: row[k] for k in ("name", "company", "role", "status", "source")},
                email=row["email"].strip().lower(),
            )
        campaigns = {}
        for row in old.execute("SELECT * FROM campaigns"):
            if row["attach_resume"] and filename and not rid:
                raise ValueError("Supply --resume with the legacy active PDF.")
            campaigns[row["id"]] = add(
                Campaign,
                **{
                    k: row[k]
                    for k in (
                        "name",
                        "subject",
                        "body",
                        "tracking_open",
                        "tracking_click",
                    )
                },
                created_at=stamp(row["created_at"]),
                resume_id=rid if row["attach_resume"] else None,
            )
        mailbox = setting("gmail_email").lower()
        deliveries = {}
        for row in old.execute("SELECT * FROM deliveries"):
            original_campaign = db.get(Campaign, campaigns[row["campaign_id"]])
            deliveries[row["id"]] = add(
                Delivery,
                campaign_id=campaigns[row["campaign_id"]],
                contact_id=contacts[row["contact_id"]],
                mailbox=mailbox,
                recipient=addresses[row["contact_id"]],
                sent_at=stamp(row["sent_at"]),
                tracking_open=original_campaign.tracking_open,
                tracking_click=original_campaign.tracking_click,
                **{
                    k: row[k]
                    for k in (
                        "gmail_message_id",
                        "gmail_thread_id",
                        "token",
                        "status",
                        "error",
                    )
                },
            )
        for row in old.execute("SELECT * FROM messages"):
            add(
                Message,
                delivery_id=deliveries[row["delivery_id"]],
                mailbox=mailbox,
                received_at=stamp(row["received_at"]),
                internet_id="",
                **{
                    k: row[k] or ""
                    for k in (
                        "gmail_message_id",
                        "gmail_thread_id",
                        "sender",
                        "recipient",
                        "subject",
                        "body",
                        "direction",
                    )
                },
            )
        for row in old.execute("SELECT * FROM tracking_events"):
            delivery = db.get(Delivery, deliveries[row["delivery_id"]])
            kind = {"open": "open_signal", "click": "link_click"}.get(
                row["type"], row["type"]
            )
            timestamp = stamp(row["occurred_at"])
            add(
                Event,
                delivery_id=deliveries[row["delivery_id"]],
                kind=kind,
                occurred=timestamp,
                tracking_identifier=delivery.token if kind == "open_signal" else None,
            )
            if kind in {"open_signal", "link_click"}:
                signal = "open" if kind == "open_signal" else "click"
                first = getattr(delivery, f"first_{signal}_at")
                last = getattr(delivery, f"last_{signal}_at")
                setattr(
                    delivery, f"first_{signal}_at", min(first or timestamp, timestamp)
                )
                setattr(
                    delivery, f"last_{signal}_at", max(last or timestamp, timestamp)
                )
                setattr(
                    delivery,
                    f"{signal}_requests",
                    getattr(delivery, f"{signal}_requests") + 1,
                )
        for row in old.execute("SELECT * FROM tracked_links"):
            if not safe_url(row["target"]):
                raise ValueError("Legacy link contains an unsupported address.")
            add(
                Link,
                delivery_id=deliveries[row["delivery_id"]],
                token=row["token"],
                target=row["target"],
            )
        if apply:
            db.commit()
        return {
            "contacts": len(contacts),
            "campaigns": len(campaigns),
            "deliveries": len(deliveries),
            "committed": apply,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(migrate(**vars(args)))
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        parser.exit(
            1, f"Migration stopped. Destination transaction rolled back. {exc}\n"
        )
    except Exception:
        parser.exit(
            1,
            "Migration stopped. Verify source integrity and duplicate history. Destination transaction rolled back.\n",
        )
