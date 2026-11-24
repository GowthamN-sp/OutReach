import sqlite3

from tools.migrate_legacy import migrate


def test_legacy_requires_explicit_owner_and_application(clients, tmp_path):
    a, b = clients
    source = tmp_path / "archive.sqlite"
    with sqlite3.connect(source) as db:
        db.executescript("""
        CREATE TABLE contacts(id INTEGER,name,email,company,role,status,source);
        INSERT INTO contacts VALUES (1,'Legacy','legacy@example.org','','','New','Import');
        CREATE TABLE campaigns(id INTEGER,attach_resume,name,subject,body,created_at,tracking_open,tracking_click);
        INSERT INTO campaigns VALUES(1,0,'Test','Hello','Hello','2025-01-01T00:00:00+00:00',0,0);
        CREATE TABLE deliveries(id INTEGER,campaign_id,contact_id,gmail_message_id,gmail_thread_id,sent_at,status,token,error);
        INSERT INTO deliveries VALUES(1,1,1,'id','thread','2025-01-01T00:00:00+00:00','Sent','opaque',NULL);
        CREATE TABLE settings(key,value);
        CREATE TABLE messages(id INTEGER);
        CREATE TABLE tracking_events(id INTEGER);
        CREATE TABLE tracked_links(id INTEGER);
        """)
    original = source.read_bytes()
    assert not migrate(source, "alice@example.org", None, False)["committed"]
    assert a.get("/api/contacts").json() == []
    assert migrate(source, "alice@example.org", None, True)["deliveries"] == 1
    assert a.get("/api/sent").json()[0]["email"] == "legacy@example.org"
    assert b.get("/api/contacts").json() == []
    assert source.read_bytes() == original


def test_tracking_upgrade_preserves_existing_rows(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    target = tmp_path / "upgrade.db"
    env = dict(os.environ, V2_DATABASE_PATH=str(target))
    backend = Path(__file__).resolve().parents[1]

    def upgrade(revision):
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", revision],
            cwd=backend,
            env=env,
            check=True,
            capture_output=True,
        )

    upgrade("a7dbf0963495")
    with sqlite3.connect(target) as db:
        db.executescript("""
        INSERT INTO users(id,name,email,password_hash,send_lock) VALUES(1,'Owner','owner@example.org','preserved-hash',0);
        INSERT INTO gmail_accounts(user_id,email,refresh) VALUES(1,'owner@example.org','preserved-encrypted-credential');
        INSERT INTO contacts(id,user_id,email,name,company,role,status,source) VALUES(1,1,'test@example.org','Pat','','','Contacted','Manual');
        INSERT INTO campaigns(id,user_id,name,subject,body,tracking_open,tracking_click,created_at) VALUES(1,1,'Test','Hello','Original',1,1,'2026-01-01');
        INSERT INTO deliveries(id,user_id,campaign_id,contact_id,mailbox,recipient,sent_at,status,token) VALUES(1,1,1,1,'owner@example.org','test@example.org','2026-01-01','Sent','existing-open-token');
        INSERT INTO tracked_links(id,user_id,delivery_id,token,target) VALUES(1,1,1,'existing-click-token','https://example.org');
        INSERT INTO tracking_events(id,user_id,delivery_id,kind,occurred) VALUES(1,1,1,'open','2026-01-02'),(2,1,1,'open','2026-01-03'),(3,1,1,'click','2026-01-04');
        """)
    upgrade("head")
    upgrade("head")
    with sqlite3.connect(target) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute(
            "SELECT password_hash,tracking_open,tracking_click FROM users"
        ).fetchone() == ("preserved-hash", 0, 0)
        assert (
            db.execute("SELECT refresh FROM gmail_accounts").fetchone()[0]
            == "preserved-encrypted-credential"
        )
        assert db.execute(
            "SELECT token,first_open_at,last_open_at,open_requests,click_requests,body FROM deliveries"
        ).fetchone() == ("existing-open-token", "2026-01-02", "2026-01-03", 2, 1, None)
        assert (
            db.execute("SELECT token FROM tracked_links").fetchone()[0]
            == "existing-click-token"
        )
        assert db.execute(
            "SELECT kind,tracking_identifier FROM tracking_events ORDER BY id"
        ).fetchall() == [
            ("open_signal", "existing-open-token"),
            ("open_signal", "existing-open-token"),
            ("link_click", None),
        ]
