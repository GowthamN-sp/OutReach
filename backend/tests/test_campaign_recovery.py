from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_workspace import account, campaign, connect, contact

from app.db import engine, now
from app.integrations import google
from app.models import Campaign, Delivery, Event, Message
from app.services import inbox


def test_draft_recovery_and_ownership(clients):
    a, b = clients
    cid = campaign(a)
    assert b.delete(f"/api/campaigns/{cid}").status_code == 404
    assert a.delete(f"/api/campaigns/{cid}").status_code == 200
    assert a.get("/api/campaigns?view=active").json() == []
    assert a.get("/api/campaigns").json() == []
    assert a.get("/api/campaigns?view=deleted").json()[0]["id"] == cid
    with Session(engine) as db:
        assert db.get(Campaign, cid).deleted_at is not None
    assert b.post(f"/api/campaigns/{cid}/restore").status_code == 404
    assert a.post(f"/api/campaigns/{cid}/restore").status_code == 200
    assert a.get("/api/campaigns?view=active").json()[0]["id"] == cid
    assert a.get("/api/campaigns?view=deleted").json() == []


@pytest.mark.parametrize("status", ["Preparing", "Unconfirmed", "Failed", "Sent"])
def test_any_delivery_history_prevents_deletion(clients, status):
    a, _ = clients
    cid, person = campaign(a), contact(a)
    with Session(engine) as db:
        db.add(
            Delivery(
                user_id=account(a),
                campaign_id=cid,
                contact_id=person,
                status=status,
                mailbox="sender@example.org",
                recipient="person@example.org",
                token="test-token",
            )
        )
        db.commit()
    assert a.delete(f"/api/campaigns/{cid}").status_code == 409
    assert a.get("/api/campaigns?view=active").json()[0]["delivery_count"] == 1
    assert a.post(f"/api/campaigns/{cid}/archive").status_code == 200
    assert a.get("/api/campaigns?view=archived").json()[0]["id"] == cid


def test_archive_preserves_tracking_replies_and_reports(clients, monkeypatch):
    a, b = clients
    connect(a, monkeypatch)
    monkeypatch.setattr(
        google, "call", AsyncMock(return_value={"id": "message", "threadId": "thread"})
    )
    cid, person = campaign(a), contact(a)
    request = {"campaign_id": cid, "contact_ids": [person], "confirm": True}
    assert a.post("/api/send", json=request).json()["sent"] == 1
    with Session(engine) as db:
        delivery = db.scalar(select(Delivery).where(Delivery.campaign_id == cid))
        did = delivery.id
        db.add(Event(user_id=account(a), delivery_id=did, kind="open_signal"))
        db.add(
            Message(
                user_id=account(a),
                delivery_id=did,
                gmail_message_id="reply",
                gmail_thread_id="thread",
                mailbox="sender@example.org",
                sender="person@example.org",
                recipient="sender@example.org",
                subject="Reply",
                body="Keep this reply",
                received_at=now(),
                direction="inbound",
                internet_id="<reply@example.org>",
            )
        )
        db.commit()
    before = a.get("/api/analytics").json()
    assert b.post(f"/api/campaigns/{cid}/archive").status_code == 404
    assert a.post(f"/api/campaigns/{cid}/archive").status_code == 200
    assert a.get("/api/campaigns?view=active").json() == []
    assert a.get(f"/api/sent/{did}/events").json()[0]["kind"] == "open_signal"
    assert a.get(f"/api/sent/{did}/replies").json()[0]["body"] == "Keep this reply"
    assert a.get(f"/api/campaigns/{cid}/deliveries").json()[0]["id"] == did
    after = a.get("/api/analytics").json()
    for key in ("sent", "replies", "open_signals", "accepted_total"):
        assert before[key] == after[key]
    assert a.post("/api/send", json=request).status_code == 409
    assert a.post(f"/api/campaigns/{cid}/restore").status_code == 200
    assert a.get("/api/campaigns?view=active").json()[0]["id"] == cid


def test_delete_during_token_exchange_blocks_send(clients, monkeypatch):
    a, _ = clients
    connect(a, monkeypatch)
    cid, person = campaign(a), contact(a)

    async def exchange(*args):
        assert a.delete(f"/api/campaigns/{cid}").status_code == 200
        return "mock-access"

    monkeypatch.setattr(google, "access", exchange)
    delivery_call = AsyncMock()
    monkeypatch.setattr(google, "call", delivery_call)
    response = a.post(
        "/api/send", json={"campaign_id": cid, "contact_ids": [person], "confirm": True}
    )
    assert response.status_code == 409
    delivery_call.assert_not_awaited()
    with Session(engine) as db:
        assert db.scalar(select(func.count(Delivery.id))) == 0


def test_delete_after_send_reservation_is_rejected(clients, monkeypatch):
    a, _ = clients
    connect(a, monkeypatch)
    cid, person = campaign(a), contact(a)

    async def deliver(*args, **kwargs):
        assert a.delete(f"/api/campaigns/{cid}").status_code == 409
        return {"id": "message", "threadId": "thread"}

    monkeypatch.setattr(google, "call", deliver)
    assert (
        a.post(
            "/api/send",
            json={"campaign_id": cid, "contact_ids": [person], "confirm": True},
        ).json()["sent"]
        == 1
    )
    assert a.get("/api/campaigns?view=active").json()[0]["id"] == cid


def test_preview_and_missing_personalization(clients, monkeypatch):
    a, b = clients
    cid = campaign(
        a,
        subject="Hi {{name}} at {{company}}",
        body="Applying for {{role}}. My resume is attached.",
    )
    person = contact(a)
    request = {"campaign_id": cid, "contact_ids": [person]}
    response = a.post(f"/api/campaigns/{cid}/preview", json=request)
    assert response.status_code == 200
    row = response.json()["recipients"][0]
    assert row["missing"] == ["company", "role"]
    assert row["subject"] == "Hi Pat at your organization"
    assert response.json()["resume_filename"] is None
    assert b.post(f"/api/campaigns/{cid}/preview", json=request).status_code == 404
    assert a.post("/api/send", json={**request, "confirm": True}).status_code == 422
    assert (
        a.put(
            f"/api/contacts/{person}",
            json={
                "email": "person@example.org",
                "name": "Pat",
                "company": "Acme",
                "role": "Engineer",
            },
        ).status_code
        == 200
    )
    row = a.post(f"/api/campaigns/{cid}/preview", json=request).json()["recipients"][0]
    assert row["missing"] == []
    assert row["subject"] == "Hi Pat at Acme"
    assert row["body"] == "Applying for Engineer. My resume is attached."
    assert (
        a.put(
            "/api/settings/tracking",
            json={"tracking_open": True, "tracking_click": False},
        ).status_code
        == 200
    )
    boot = a.get("/api/bootstrap").json()
    assert boot["tracking_open"] and not boot["tracking_click"]


def test_import_preview_retains_invalid_and_duplicate_rows(clients):
    a, _ = clients
    contact(a)
    response = a.post(
        "/api/import/preview",
        files={
            "file": (
                "recruiters.csv",
                b"email,name,company,role\nperson@example.org,Pat,,\nnew@example.org,New,,\nnew@example.org,Again,,\ninvalid,Bad,,",
            )
        },
    )
    assert response.status_code == 200
    preview = response.json()
    assert preview["total"] == 4
    assert preview["contacts"][0]["issues"] == ["Already in Contacts"]
    assert preview["contacts"][2]["issues"] == ["Duplicate within file"]
    assert preview["contacts"][3]["issues"] == ["Invalid email address"]
    assert preview["contacts"][1]["missing"] == ["company", "role"]
    rows = [
        preview["contacts"][1],
        {"email": "corrected@example.org", "name": "Corrected"},
    ]
    assert (
        a.post(
            "/api/import/commit", json={"contacts": rows, "batch": preview["batch"]}
        ).json()["added"]
        == 2
    )
    contacts = a.get("/api/contacts").json()
    assert sum(row["source"] == preview["batch"] for row in contacts) == 2
    corrected = a.post(
        "/api/import/review",
        json={
            "contacts": [
                {"email": "bad..address@example.org", "name": "Invalid"},
                {"email": "good.address@example.org", "name": "Correct"},
            ]
        },
    ).json()
    assert corrected["contacts"][0]["issues"] == ["Invalid email address"]
    assert corrected["contacts"][1]["issues"] == []


def test_sync_status_is_persistent_separate_and_owner_scoped(clients, monkeypatch):
    a, b = clients
    connect(a, monkeypatch)
    assert a.get("/api/bootstrap").json()["gmail_connected"]
    assert a.get("/api/inbox/sync-status").json() is None
    monkeypatch.setattr(
        inbox, "sync", AsyncMock(side_effect=HTTPException(502, "Test sync failure"))
    )
    assert a.post("/api/inbox/sync").status_code == 502
    status = a.get("/api/inbox/sync-status").json()
    assert status["status"] == "failed"
    assert status["detail"] == "Test sync failure"
    assert a.get("/api/bootstrap").json()["gmail_connected"]
    assert b.get("/api/inbox/sync-status").json() is None
    monkeypatch.setattr(
        inbox, "sync", AsyncMock(return_value={"threads_checked": 3, "added": 2})
    )
    assert a.post("/api/inbox/sync").status_code == 200
    assert a.get("/api/inbox/sync-status").json()["status"] == "success"
    assert "3 threads checked" in a.get("/api/inbox/sync-status").json()["detail"]
