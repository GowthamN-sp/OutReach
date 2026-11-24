from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, now


class Record:
    id: Mapped[int] = mapped_column(primary_key=True)


class Personal(Record):
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)


class User(Record, Base):
    __tablename__ = "users"
    name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    send_lock: Mapped[int] = mapped_column(default=0)
    tracking_open: Mapped[bool] = mapped_column(default=False, server_default="0")
    tracking_click: Mapped[bool] = mapped_column(default=False, server_default="0")


class LoginSession(Base):
    __tablename__ = "sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    csrf: Mapped[str]
    expires: Mapped[datetime]
    oauth_state: Mapped[str | None]
    oauth_expires: Mapped[datetime | None]


class Attempt(Record, Base):
    __tablename__ = "auth_attempts"
    bucket: Mapped[str] = mapped_column(index=True)
    occurred: Mapped[datetime] = mapped_column(default=now, index=True)


class GmailAccount(Base):
    __tablename__ = "gmail_accounts"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    email: Mapped[str]
    refresh: Mapped[str]


class Contact(Personal, Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("user_id", "email"),)
    email: Mapped[str]
    name: Mapped[str]
    company: Mapped[str]
    role: Mapped[str]
    status: Mapped[str]
    source: Mapped[str]


class Resume(Personal, Base):
    __tablename__ = "resumes"
    name: Mapped[str]
    filename: Mapped[str]
    content: Mapped[bytes] = mapped_column(deferred=True)
    size: Mapped[int]
    is_default: Mapped[bool] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=now)
    __table_args__ = (
        Index(
            "one_default_resume",
            "user_id",
            unique=True,
            sqlite_where=is_default.is_(True),
            postgresql_where=is_default.is_(True),
        ),
    )


class Template(Personal, Base):
    __tablename__ = "templates"
    name: Mapped[str]
    subject: Mapped[str]
    body: Mapped[str] = mapped_column(Text)


class Campaign(Personal, Base):
    __tablename__ = "campaigns"
    name: Mapped[str]
    subject: Mapped[str]
    body: Mapped[str] = mapped_column(Text)
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id"))
    tracking_open: Mapped[bool]
    tracking_click: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(default=now)


class Delivery(Personal, Base):
    __tablename__ = "deliveries"
    __table_args__ = (UniqueConstraint("campaign_id", "contact_id"),)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)
    gmail_message_id: Mapped[str | None]
    gmail_thread_id: Mapped[str | None] = mapped_column(index=True)
    mailbox: Mapped[str]
    recipient: Mapped[str]
    sent_at: Mapped[datetime] = mapped_column(default=now)
    status: Mapped[str]
    token: Mapped[str] = mapped_column(unique=True)
    error: Mapped[str | None]
    tracking_open: Mapped[bool] = mapped_column(default=False, server_default="0")
    tracking_click: Mapped[bool] = mapped_column(default=False, server_default="0")
    subject: Mapped[str | None]
    body: Mapped[str | None] = mapped_column(Text)
    first_open_at: Mapped[datetime | None]
    last_open_at: Mapped[datetime | None]
    open_requests: Mapped[int] = mapped_column(default=0, server_default="0")
    first_click_at: Mapped[datetime | None]
    last_click_at: Mapped[datetime | None]
    click_requests: Mapped[int] = mapped_column(default=0, server_default="0")


class Event(Personal, Base):
    __tablename__ = "tracking_events"
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id"), index=True)
    kind: Mapped[str]
    occurred: Mapped[datetime] = mapped_column(default=now)
    tracking_identifier: Mapped[str | None]
    link_id: Mapped[int | None] = mapped_column(ForeignKey("tracked_links.id"))
    __table_args__ = (
        Index("ix_events_delivery_time", "delivery_id", "occurred", "id"),
    )


class Link(Personal, Base):
    __tablename__ = "tracked_links"
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id"), index=True)
    token: Mapped[str] = mapped_column(unique=True)
    target: Mapped[str]


class Message(Personal, Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("user_id", "mailbox", "gmail_message_id"),)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id"), index=True)
    gmail_message_id: Mapped[str]
    gmail_thread_id: Mapped[str]
    mailbox: Mapped[str]
    sender: Mapped[str]
    recipient: Mapped[str]
    subject: Mapped[str]
    body: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime]
    direction: Mapped[str]
    internet_id: Mapped[str]


class ReplyAttempt(Personal, Base):
    __tablename__ = "reply_attempts"
    __table_args__ = (UniqueConstraint("user_id", "key"),)
    key: Mapped[str]
    status: Mapped[str]
    sent_at: Mapped[datetime] = mapped_column(default=now)
    delivery_id: Mapped[int | None] = mapped_column(ForeignKey("deliveries.id"), index=True)
    subject: Mapped[str | None]
    body: Mapped[str | None] = mapped_column(Text)
    gmail_message_id: Mapped[str | None]
