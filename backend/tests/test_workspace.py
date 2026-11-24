from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.db import engine, now
from app.integrations import google
from app.main import app
from app.models import Delivery, GmailAccount, Link, LoginSession, User
from app.security import digest


def account(client):
    return client.get("/api/session").json()["user"]["id"]


def valid_pdf():
    from pypdfium2 import PdfDocument

    document = PdfDocument.new()
    document.new_page(100, 100)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def campaign(client, **extra):
    response = client.post(
        "/api/campaigns",
        json={
            "name": "Intro",
            "subject": "Hello {{name}}",
            "body": "Visit https://example.org",
            "tracking_click": True,
            "tracking_open": True,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def contact(client, email="person@example.org"):
    return client.post("/api/contacts", json={"email": email, "name": "Pat"}).json()[
        "id"
    ]


def connect(client, monkeypatch):
    uid = account(client)
    with Session(engine) as db:
        db.add(GmailAccount(user_id=uid, email="sender@example.org", refresh="mocked"))
        db.commit()
    monkeypatch.setattr(google, "access", AsyncMock(return_value="mock-access"))


def test_accounts_and_sessions(clients):
    a, b = clients
    guest = TestClient(app)
    assert guest.get("/api/contacts").status_code == 401
    assert (
        guest.post(
            "/api/login", json={"email": "alice@example.org", "password": "wrong"}
        ).status_code
        == 401
    )
    assert (
        guest.post(
            "/api/signup",
            json={
                "name": "Alice",
                "email": "ALICE@example.org",
                "password": "a long test password",
            },
        ).status_code
        == 409
    )
    assert (
        guest.post(
            "/api/signup", json={"name": "X", "email": "bad", "password": "short"}
        ).status_code
        == 422
    )
    assert (
        a.post(
            "/api/contacts",
            json={"email": "x@example.org"},
            headers={"X-CSRF-Token": "wrong"},
        ).status_code
        == 403
    )
    assert (
        a.put(
            "/api/profile", json={"name": "Alice Ng", "email": "alice@example.org"}
        ).json()["name"]
        == "Alice Ng"
    )
    assert (
        a.post(
            "/api/logout", headers={"Origin": "https://untrusted.example.org"}
        ).status_code
        == 403
    )
    login = guest.post(
        "/api/login",
        json={
            "email": "alice@example.org",
            "password": "a long test password",
            "remember": True,
        },
    )
    assert (
        login.status_code == 200
        and "HttpOnly" in login.headers["set-cookie"]
        and "Max-Age" in login.headers["set-cookie"]
    )
    changed = a.put(
        "/api/password",
        json={"current": "a long test password", "password": "an even longer password"},
    )
    assert changed.status_code == 200
    assert guest.get("/api/session").status_code == 401
    a.headers["X-CSRF-Token"] = changed.json()["csrf"]
    assert (
        a.post("/api/logout").status_code == 200
        and a.get("/api/session").status_code == 401
    )
    with Session(engine) as db:
        assert db.scalar(select(User.password_hash)).startswith("$argon2id$")
        session = db.get(LoginSession, digest(b.cookies["od_session"]))
        session.expires = now() - timedelta(seconds=1)
        db.commit()
    assert b.get("/api/session").status_code == 401


def test_login_limits_and_closed_signup(monkeypatch):
    client = TestClient(app)
    data = {"email": "nobody@example.org", "password": "incorrect"}
    for _ in range(12):
        assert client.post("/api/login", json=data).status_code == 401
    assert client.post("/api/login", json=data).status_code == 429
    monkeypatch.setattr(config, "SIGNUP", False)
    assert (
        client.post(
            "/api/signup",
            json={
                "name": "A",
                "email": data["email"],
                "password": "long enough password",
            },
        ).status_code
        == 403
    )


def test_contacts_and_imports(clients):
    a, b = clients
    cid = contact(a)
    contact(b)
    assert (
        a.post("/api/contacts", json={"email": "PERSON@example.org"}).status_code == 409
    )
    assert (
        b.put(f"/api/contacts/{cid}", json={"email": "x@example.org"}).status_code
        == 404
    )
    assert b.delete(f"/api/contacts/{cid}").status_code == 404
    assert b.get("/api/sent", params={"contact_id": cid}).status_code == 404
    assert (
        a.put(
            f"/api/contacts/{cid}",
            json={"email": "renamed@example.org", "role": "Hiring"},
        ).status_code
        == 200
    )
    csv = b"name,email,company\nPat,other@example.org,Acme\nPat,other@example.org,Acme"
    rows = a.post("/api/import/preview", files={"file": ("list.csv", csv)}).json()[
        "contacts"
    ]
    assert len(rows) == 2
    assert "Duplicate within file" in rows[1]["issues"]
    rows = rows[:1]
    rows[0]["name"] = "Corrected"
    assert a.post("/api/import/commit", json={"contacts": rows}).json()["added"] == 1
    assert a.post("/api/import/commit", json={"contacts": rows}).json()["skipped"] == 1
    wb = Workbook()
    wb.active.append(["email"])
    wb.active.append(["sheet@example.org"])
    f = BytesIO()
    wb.save(f)
    assert (
        a.post(
            "/api/import/preview", files={"file": ("list.xlsx", f.getvalue())}
        ).json()["total"]
        == 1
    )
    assert (
        a.post(
            "/api/import/preview", files={"file": ("bad.pdf", b"invalid")}
        ).status_code
        == 400
    )
    assert len(a.get("/api/contacts?search=Corrected&limit=1").json()) == 1
    assert a.delete(f"/api/contacts/{cid}").status_code == 200


def test_private_resumes_templates_campaigns(clients):
    a, b = clients
    assert (
        a.post("/api/resumes", files={"file": ("x.pdf", b"%PDF-invalid")}).status_code
        == 400
    )
    pdf = valid_pdf()

    def upload():
        r = a.post(
            "/api/resumes",
            data={"name": "Developer"},
            files={"file": ("../one.pdf", pdf)},
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    first, second = upload(), upload()
    assert a.put(f"/api/resumes/{second}/default").json()["is_default"]
    assert a.get(f"/api/resumes/{first}/file?download=true").content == pdf
    assert b.get(f"/api/resumes/{first}/file").status_code == 404
    assert b.put(f"/api/resumes/{first}/default").status_code == 404
    assert b.delete(f"/api/resumes/{first}").status_code == 404
    assert b.get("/api/resumes").json() == []
    assert (
        b.post(
            "/api/campaigns",
            json={"name": "x", "subject": "x", "body": "x", "resume_id": first},
        ).status_code
        == 404
    )
    cid = campaign(a, resume_id=first)
    assert a.delete(f"/api/resumes/{first}").status_code == 409
    assert a.delete(f"/api/resumes/{second}").status_code == 200
    assert a.get("/api/resumes").json()[0]["is_default"]
    assert b.get(f"/api/campaigns/{cid}/deliveries").status_code == 404
    assert b.get("/api/campaigns").json() == []
    a.post("/api/templates", json={"name": "Intro", "subject": "Hi", "body": "Hello"})
    assert b.get("/api/templates").json() == []


def test_send_sync_tracking_reply_and_isolation(clients, monkeypatch):
    a, b = clients
    cid = campaign(a)
    person = contact(a)
    data = {"campaign_id": cid, "contact_ids": [person], "confirm": True}
    assert a.post("/api/send", json=data).status_code == 409
    assert b.post("/api/send", json=data).status_code == 404
    connect(a, monkeypatch)
    assert a.post("/api/send", json={**data, "confirm": False}).status_code == 400
    assert (
        a.post(
            "/api/send", json={**data, "contact_ids": [person, contact(b)]}
        ).status_code
        == 404
    )
    accepted = AsyncMock(return_value={"id": "abc", "threadId": "tid"})
    monkeypatch.setattr(google, "call", accepted)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: a.post("/api/send", json=data), range(2)))
    assert sorted(r.json()["sent"] for r in results) == [0, 1]
    assert accepted.await_count == 1
    with Session(engine) as db:
        token = db.scalar(select(Delivery.token))
        link = db.scalar(select(Link.token))
    public = TestClient(app)
    assert public.get(f"/api/o/{token}.gif").status_code == 200
    assert (
        public.get(f"/api/t/{link}", follow_redirects=False).headers["location"]
        == "https://example.org"
    )
    thread = {
        "messages": [
            {
                "id": "reply",
                "internalDate": "1000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "person@example.org"},
                        {"name": "Subject", "value": "Hi"},
                        {"name": "Message-ID", "value": "<test@example.org>"},
                    ],
                    "mimeType": "text/plain",
                    "body": {"data": "SGk="},
                },
            }
        ]
    }
    monkeypatch.setattr(google, "call", AsyncMock(return_value=thread))
    assert a.post("/api/inbox/sync").json()["added"] == 1
    assert a.post("/api/inbox/sync").json()["added"] == 0
    stats = a.get("/api/analytics").json()
    assert [stats[k] for k in ("sent", "replies", "open_signals", "click_signals")] == [
        1,
        1,
        1,
        1,
    ]
    assert stats["campaigns"][0]["reply_count"] == 1
    assert b.get("/api/analytics").json()["sent"] == 0
    assert b.get("/api/inbox").json() == []
    mid = a.get("/api/inbox").json()[0]["id"]
    reply = {"body": "Thanks", "request_id": "62511334-24c1-4fb3-96f4-78bd8a222f11"}
    assert b.post(f"/api/inbox/{mid}/reply", json=reply).status_code == 404
    monkeypatch.setattr(google, "call", accepted)
    assert a.post(f"/api/inbox/{mid}/reply", json=reply).status_code == 200
    assert a.post(f"/api/inbox/{mid}/reply", json=reply).status_code == 409
    assert accepted.await_args.kwargs["json"]["threadId"] == "tid"
    sent_reply = a.get("/api/sent-replies?search=person").json()[0]
    assert sent_reply["body"] == "Thanks" and sent_reply["status"] == "Sent"
    assert not sent_reply["tracking_open"] and not sent_reply["tracking_click"]
    assert a.get(f"/api/sent-replies/{sent_reply['id']}").json()["body"] == "Thanks"
    assert b.get(f"/api/sent-replies/{sent_reply['id']}").status_code == 404
    assert b.get("/api/sent-replies").json() == []
    assert a.get("/api/analytics").json()["accepted_total"] == 2


def test_oauth_bound_to_session(clients, monkeypatch):
    a, b = clients
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "mock-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "mock")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    state = parse_qs(urlparse(a.post("/api/auth/google/start").json()["url"]).query)[
        "state"
    ][0]
    path = "/api/auth/google/callback?code=mock&state=" + state
    assert b.get(path, follow_redirects=False).status_code == 400
    monkeypatch.setattr(
        google,
        "exchange",
        AsyncMock(
            return_value={
                "access_token": "test",
                "refresh_token": "test-refresh",
                "scope": google.SCOPES,
            }
        ),
    )
    monkeypatch.setattr(
        google, "call", AsyncMock(return_value={"emailAddress": "alice@example.org"})
    )
    assert a.get(path, follow_redirects=False).status_code == 307
    assert a.get(path, follow_redirects=False).status_code == 400
    with Session(engine) as db:
        assert db.get(GmailAccount, account(a)).refresh != "test-refresh"
    assert not b.get("/api/bootstrap").json()["gmail_connected"]
    assert a.post("/api/auth/google/disconnect").status_code == 200


def test_uncertain_acceptance_and_rate_limits(clients, monkeypatch):
    import httpx

    a, _ = clients
    connect(a, monkeypatch)
    cid = campaign(a)
    first = contact(a, "first@example.org")
    second = contact(a, "second@example.org")

    def submit(ids):
        return a.post(
            "/api/send", json={"campaign_id": cid, "contact_ids": ids, "confirm": True}
        )

    monkeypatch.setattr(config, "LIMIT", 1)
    fake = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
    monkeypatch.setattr(google, "call", fake)
    assert submit([first, second]).status_code == 429
    assert fake.await_count == 0
    assert submit([first]).json()["results"][0]["status"] == "Unconfirmed"
    assert submit([first]).json()["results"][0]["status"] == "Skipped"
    assert submit([second]).status_code == 429
    assert fake.await_count == 1


def test_definite_rejection_can_be_retried(clients, monkeypatch):
    a, _ = clients
    connect(a, monkeypatch)
    data = {"campaign_id": campaign(a), "contact_ids": [contact(a)], "confirm": True}
    fake = AsyncMock(
        side_effect=[
            google.Rejected(502, "Rejected"),
            {"id": "accepted", "threadId": "thread"},
        ]
    )
    monkeypatch.setattr(google, "call", fake)
    assert a.post("/api/send", json=data).json()["results"][0]["status"] == "Failed"
    assert a.post("/api/send", json=data).json()["sent"] == 1
    assert a.post("/api/send", json=data).json()["sent"] == 0
