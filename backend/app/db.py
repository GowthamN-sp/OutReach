from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import DeclarativeBase, Session

from . import config


class Base(DeclarativeBase):
    pass


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


engine = create_engine(
    config.DATABASE, connect_args={"check_same_thread": False, "timeout": 20}
)


@event.listens_for(engine, "connect")
def pragmas(connection, record):
    connection.execute("PRAGMA foreign_keys=ON")


def database() -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def owned(db: Session, model, user_id: int, record_id: int):
    row = db.scalar(
        select(model).where(model.user_id == user_id, model.id == record_id)
    )
    if row is None:
        raise HTTPException(404, "Record not found")
    return row


def lock_user(db: Session, uid: int) -> None:
    from .models import User

    db.execute(update(User).where(User.id == uid).values(send_lock=User.send_lock + 1))
