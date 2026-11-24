from sqlalchemy import inspect

from alembic import context
from app import models  # noqa: F401
from app.db import Base, engine

with engine.begin() as connection:
    inspector = inspect(connection)
    if "contacts" in inspector.get_table_names() and "user_id" not in {
        column["name"] for column in inspector.get_columns("contacts")
    }:
        raise RuntimeError(
            "Legacy database detected. Set V2_DATABASE_PATH to a separate file."
        )
    context.configure(
        connection=connection, target_metadata=Base.metadata, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()
