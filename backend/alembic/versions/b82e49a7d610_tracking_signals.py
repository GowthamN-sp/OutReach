"""Preserve existing callbacks; add per-message snapshots and signal summaries."""

import sqlalchemy as sa

from alembic import op

revision = "b82e49a7d610"
down_revision = "a7dbf0963495"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE reply_attempts ADD COLUMN delivery_id INTEGER REFERENCES deliveries(id)"
    )
    op.create_index("ix_reply_attempts_delivery_id", "reply_attempts", ["delivery_id"])
    for name, kind in (
        ("subject", sa.String()),
        ("body", sa.Text()),
        ("gmail_message_id", sa.String()),
    ):
        op.add_column("reply_attempts", sa.Column(name, kind, nullable=True))
    for table in ("users", "deliveries"):
        for name in ("tracking_open", "tracking_click"):
            op.add_column(
                table, sa.Column(name, sa.Boolean(), nullable=False, server_default="0")
            )
    for name, kind in (("subject", sa.String()), ("body", sa.Text())):
        op.add_column("deliveries", sa.Column(name, kind, nullable=True))
    for signal in ("open", "click"):
        for prefix in ("first", "last"):
            op.add_column(
                "deliveries",
                sa.Column(f"{prefix}_{signal}_at", sa.DateTime(), nullable=True),
            )
        op.add_column(
            "deliveries",
            sa.Column(
                f"{signal}_requests", sa.Integer(), nullable=False, server_default="0"
            ),
        )
    op.add_column(
        "tracking_events", sa.Column("tracking_identifier", sa.String(), nullable=True)
    )
    # SQLite supports adding a nullable REFERENCES column without rebuilding data.
    op.execute(
        "ALTER TABLE tracking_events ADD COLUMN link_id INTEGER REFERENCES tracked_links(id)"
    )
    op.create_index(
        "ix_events_delivery_time", "tracking_events", ["delivery_id", "occurred", "id"]
    )
    op.create_index("ix_tracked_links_delivery_id", "tracked_links", ["delivery_id"])
    op.execute("UPDATE tracking_events SET kind='open_signal' WHERE kind='open'")
    op.execute("UPDATE tracking_events SET kind='link_click' WHERE kind='click'")
    for signal, kind in (("open", "open_signal"), ("click", "link_click")):
        op.execute(f"""UPDATE deliveries SET
            tracking_{signal} = COALESCE((SELECT tracking_{signal} FROM campaigns WHERE campaigns.id=deliveries.campaign_id), 0),
            first_{signal}_at = (SELECT MIN(occurred) FROM tracking_events WHERE delivery_id=deliveries.id AND kind='{kind}'),
            last_{signal}_at = (SELECT MAX(occurred) FROM tracking_events WHERE delivery_id=deliveries.id AND kind='{kind}'),
            {signal}_requests = (SELECT COUNT(*) FROM tracking_events WHERE delivery_id=deliveries.id AND kind='{kind}')""")
    op.execute("""UPDATE tracking_events SET tracking_identifier =
        (SELECT token FROM deliveries WHERE deliveries.id=delivery_id) WHERE kind='open_signal'""")
    # Legacy click events did not retain the link identity; do not invent one.
    # Triggers enforce tracking cleanup even for maintenance SQL, without
    # rebuilding heavily referenced SQLite tables or disabling foreign keys.
    for table, key in (("deliveries", "delivery_id"), ("users", "user_id")):
        op.execute(f"""CREATE TRIGGER tracking_cleanup_{table} BEFORE DELETE ON {table}
            BEGIN
                DELETE FROM tracking_events WHERE {key}=OLD.id;
                DELETE FROM tracked_links WHERE {key}=OLD.id;
            END""")


def downgrade() -> None:
    raise RuntimeError(
        "Tracking snapshots are retained. Restore a reviewed backup to downgrade."
    )
