"""Tracking integration tests use only a disposable database and mocked Gmail."""

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from email import policy
from email.parser import BytesParser
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from test_workspace import account, campaign, connect, contact, valid_pdf

from app import config
from app.db import engine, now
from app.integrations import google
from app.main import app
from app.models import Campaign, Delivery, Event, Link, Message
from app.services.email_html import public_origin, render, safe_url


@pytest.fixture
def sent_message(clients, monkeypatch):
    a, b = clients
    connect(a, monkeypatch)
    gmail = AsyncMock(return_value={"id": "accepted", "threadId": "thread"})
    monkeypatch.setattr(google, "call", gmail)

    def send(**options):
        cid = campaign(a, **options)
        person = contact(a, f"person{cid}@example.org")
        result = a.post(
            "/api/send",
            json={"campaign_id": cid, "contact_ids": [person], "confirm": True},
        )
        assert result.status_code == 200, result.text
        with Session(engine) as db:
            d = db.scalar(select(Delivery).where(Delivery.campaign_id == cid))
            links = db.scalars(select(Link).where(Link.delivery_id == d.id)).all()
            db.expunge_all()
        raw = gmail.await_args.kwargs["json"]["raw"]
        mime = BytesParser(policy=policy.default).parsebytes(
            base64.urlsafe_b64decode(raw)
        )
        return d, links, mime

    return a, b, send


@pytest.mark.parametrize(
    "opens,clicks", [(False, False), (True, False), (False, True), (True, True)]
)
def test_independent_tracking_and_mime(sent_message, opens, clicks):
    a, b, send = sent_message
    d, links, mime = send(
        tracking_open=opens,
        tracking_click=clicks,
        body='Hello {{name}} — café\nhttps://github.com/example?x=1&y=two%20words.\n<a href="https://linkedin.com/in/example">Profile</a>',
    )
    assert mime.get_content_type() == "multipart/alternative"
    assert mime.get_body(preferencelist=("plain",)).get_content_charset() == "utf-8"
    plain = mime.get_body(preferencelist=("plain",)).get_content()
    html = mime.get_body(preferencelist=("html",)).get_content()
    assert "café" in plain and "<a " not in plain and "linkedin.com/in/example" in plain
    assert html.count("<a ") == 2
    assert ("/track/open/" in html) == opens
    assert ("/track/click/" in html) == clicks
    assert len(links) == (2 if clicks else 0)
    assert d.tracking_open == opens and d.tracking_click == clicks
    assert d.first_open_at is None and d.first_click_at is None
    assert a.get("/api/analytics").json()["open_signals"] == 0
    assert b.get(f"/api/sent/{d.id}").status_code == 404
    if not opens:
        TestClient(app).get(f"/api/track/open/{d.token}")
        assert a.get("/api/analytics").json()["open_rate"] is None
    if not clicks:
        assert 'href="https://github.com/example?x=1&amp;y=two%20words"' in html


def test_pixel_first_last_repeated_concurrent_and_privacy(sent_message):
    a, b, send = sent_message
    d, _, _ = send()
    guest = TestClient(app)
    path = f"/api/track/open/{d.token}"
    response = guest.get(
        path, headers={"User-Agent": "scanner", "X-Forwarded-For": "1.2.3.4"}
    )
    assert response.headers["content-type"] == "image/gif"
    assert (
        response.content[:6] == b"GIF89a"
        and response.content[6:10] == b"\x01\x00\x01\x00"
    )
    assert response.content[-1:] == b";"
    assert (
        "no-store" in response.headers["cache-control"]
        and "no-cache" in response.headers["cache-control"]
    )
    assert response.headers["pragma"] == "no-cache"
    first = a.get(f"/api/sent/{d.id}").json()["first_open_at"]
    with ThreadPoolExecutor(4) as pool:
        assert all(
            r.status_code == 200 for r in pool.map(lambda _: guest.get(path), range(8))
        )
    detail = a.get(f"/api/sent/{d.id}").json()
    assert detail["first_open_at"] == first
    assert detail["last_open_at"] >= first and detail["open_requests"] == 9
    assert a.get("/api/analytics").json()["open_signals"] == 1
    events = a.get(f"/api/sent/{d.id}/events?limit=2").json()
    assert len(events) == 2 and events[0]["kind"] == "open_signal"
    assert set(events[0]) == {"id", "kind", "occurred"}
    assert "token" not in detail and "tracking_identifier" not in detail
    assert b.get(f"/api/sent/{d.id}/events").status_code == 404
    assert b.get("/api/analytics").json()["open_signals"] == 0
    with Session(engine) as db:
        event = db.scalar(select(Event))
        assert event.tracking_identifier == d.token
        assert not hasattr(event, "user_agent") and not hasattr(event, "ip_address")


def test_invalid_tokens_and_failed_send_no_signals(sent_message):
    a, _, send = sent_message
    d, links, _ = send()
    guest = TestClient(app)
    for token in ("bad", "x" * 43, "x" * 129):
        assert guest.get(f"/api/track/open/{token}").status_code == 200
        assert guest.get(f"/api/track/click/{token}").status_code == 404
    with Session(engine) as db:
        db.get(Delivery, d.id).status = "Failed"
        db.commit()
    guest.get(f"/api/track/open/{d.token}")
    assert guest.get(f"/api/track/click/{links[0].token}").status_code == 404
    assert a.get(f"/api/sent/{d.id}/events").json() == []


def test_click_stored_destination_encoding_and_isolation(sent_message):
    a, b, send = sent_message
    target = "https://example.org/path?q=one%20two&next=%2Fjobs%3Fx%3D1#section"
    d, links, _ = send(body=target)
    guest = TestClient(app)
    r = guest.get(
        f"/api/track/click/{links[0].token}?url=https://evil.example.org",
        follow_redirects=False,
    )
    assert r.status_code == 302 and r.headers["location"] == target
    assert r.headers["referrer-policy"] == "no-referrer"
    guest.get(f"/api/t/{links[0].token}", follow_redirects=False)
    assert a.get(f"/api/sent/{d.id}").json()["click_requests"] == 2
    assert a.get("/api/analytics").json()["click_signals"] == 1
    with Session(engine) as db:
        event = db.scalar(select(Event))
        assert (
            event.link_id == links[0].id and event.tracking_identifier == links[0].token
        )
        db.get(Link, links[0].id).target = "javascript:alert(1)"
        db.commit()
    assert guest.get(f"/api/track/click/{links[0].token}").status_code == 404
    with Session(engine) as db:
        link = db.get(Link, links[0].id)
        link.target = target
        link.user_id = account(b)
        db.commit()
    assert guest.get(f"/api/track/click/{links[0].token}").status_code == 404


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,test",
        "//example.org",
        "https:///missing",
        "https://user:pass@example.org",
        "https://example.org:99999",
        "https://example.org/%0d%0aLocation:evil",
        "https://example.org\\@evil.org",
        "https://exa mple.org",
        "https://example.org/%zz",
        "https://[broken",
        "https://bad_host.org",
    ],
)
def test_unsafe_and_malformed_urls(url):
    assert safe_url(url) is None


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://public.org",
        "https://localhost",
        "https://127.0.0.1",
        "https://[::1]",
        "https://10.1.2.3",
        "https://host.local",
        "https://public.org/path",
        "https://public.org?x=1",
        "https://user@public.org",
    ],
)
def test_invalid_public_origins(url):
    assert not public_origin(url)


def test_renderer_multiple_anchors_punctuation_and_unsafe_html():
    destinations = []

    def rewrite(url):
        destinations.append(url)
        return "https://tracking.example.org/api/track/click/token"

    text = (
        "Visit (https://example.org/a_(b)), https://example.org/?a=1&b=2.\n"
        '<a href="https://github.com/me?a=1&amp;b=2" onclick="evil()">GitHub</a> '
        '<a href="javascript:evil()">unsafe</a><script>alert(1)</script>'
        '<a rel="unsubscribe" href="https://example.org/preferences">Unsubscribe</a>'
        '<a data-no-track href="https://example.org/legal">Legal</a> '
        "https://example.org/unsubscribe?x=1"
    )
    plain, markup = render(text, rewrite)
    assert destinations == [
        "https://example.org/a_(b)",
        "https://example.org/?a=1&b=2",
        "https://github.com/me?a=1&b=2",
    ]
    assert markup.count("<a ") == 6 and "</a>)," in markup and "</a>." in markup
    assert (
        "<script>" not in markup
        and "onclick=" not in markup
        and "javascript:" not in markup
    )
    assert (
        '<a href="https://example.org/legal" data-no-track="true">Legal</a>' in markup
    )
    assert "<br>" in markup and "GitHub (https://github.com/me?a=1&b=2)" in plain
    _, again = render(markup, rewrite)
    assert len(destinations) == 3 and again.count("<a ") == 6


def test_resume_preserved_and_personalization_escaped(sent_message):
    a, _, send = sent_message
    pdf = valid_pdf()
    rid = a.post(
        "/api/resumes", files={"file": ("resume-é.pdf", pdf)}, data={"name": "CV"}
    ).json()["id"]
    d, _, mime = send(
        resume_id=rid, body="Hi {{name}}\n<b>Hello</b> https://example.org"
    )
    assert mime.get_content_type() == "multipart/mixed"
    assert next(mime.iter_parts()).get_content_type() == "multipart/alternative"
    attachment = next(mime.iter_attachments())
    assert (
        attachment.get_filename() == "resume-é.pdf"
        and attachment.get_payload(decode=True) == pdf
    )
    assert (
        a.get(f"/api/sent/{d.id}").json()["body"]
        == "Hi Pat\n<b>Hello</b> https://example.org"
    )


def test_settings_send_revalidation_and_snapshots(sent_message, monkeypatch):
    a, b, send = sent_message
    assert not a.get("/api/bootstrap").json()["tracking_open"]
    assert (
        a.put("/api/settings/tracking", json={"tracking_open": True}).status_code == 200
    )
    assert a.get("/api/bootstrap").json()["tracking_open"]
    assert not b.get("/api/bootstrap").json()["tracking_open"]
    d, links, _ = send()
    with Session(engine) as db:
        c = db.get(Campaign, d.campaign_id)
        c.tracking_open = False
        c.tracking_click = False
        c.body = "Changed later"
        db.commit()
    a.put(
        "/api/settings/tracking", json={"tracking_open": False, "tracking_click": False}
    )
    assert TestClient(app).get(f"/api/o/{d.token}.gif").status_code == 200
    assert a.get(f"/api/sent/{d.id}").json()["open_requests"] == 1
    assert a.get(f"/api/sent/{d.id}").json()["body"] != "Changed later"
    cid = campaign(a)
    person = contact(a, "next@example.org")
    monkeypatch.setattr(config, "PUBLIC", "https://localhost")
    google.call.reset_mock()
    assert (
        a.post(
            "/api/send",
            json={"campaign_id": cid, "contact_ids": [person], "confirm": True},
        ).status_code
        == 400
    )
    google.call.assert_not_awaited()
    assert not a.get("/api/bootstrap").json()["tracking_ready"]
    assert (
        a.put("/api/settings/tracking", json={"tracking_click": True}).status_code
        == 400
    )
    assert a.put("/api/settings/tracking", json={}).status_code == 200


def test_analytics_denominators_search_paging_replies_and_cleanup(sent_message):
    a, b, send = sent_message
    tracked, links, _ = send(subject="Find this subject")
    send(tracking_open=False, tracking_click=False)
    send()
    guest = TestClient(app)
    guest.get(f"/api/track/open/{tracked.token}")
    guest.get(f"/api/track/click/{links[0].token}", follow_redirects=False)
    with Session(engine) as db:
        for i in range(2):
            db.add(
                Message(
                    user_id=tracked.user_id,
                    delivery_id=tracked.id,
                    gmail_message_id=f"reply{i}",
                    gmail_thread_id="thread",
                    mailbox=tracked.mailbox,
                    sender=tracked.recipient,
                    recipient=tracked.mailbox,
                    subject="Re: test",
                    body="Thanks",
                    received_at=now() + timedelta(seconds=i),
                    direction="inbound",
                    internet_id="",
                )
            )
        db.commit()
    stats = a.get("/api/analytics").json()
    assert (
        stats["sent"],
        stats["open_tracked"],
        stats["click_tracked"],
        stats["replies"],
    ) == (3, 2, 2, 1)
    assert (
        stats["open_rate"] == stats["click_rate"] == 50.0
        and stats["reply_rate"] == 33.3
    )
    assert stats["active_campaigns"] == 3
    assert sum(day["open_signals"] for day in stats["days"]) == 1
    assert (
        a.get(f"/api/analytics?campaign_id={tracked.campaign_id}").json()["sent"] == 1
    )
    assert b.get(f"/api/analytics?campaign_id={tracked.campaign_id}").status_code == 404
    assert len(a.get("/api/sent?search=Find%20this&status=Sent").json()) == 1
    assert len(a.get("/api/sent?signal=untracked").json()) == 1
    assert len(a.get("/api/sent?limit=1&offset=1").json()) == 1
    assert len(a.get(f"/api/sent/{tracked.id}/replies").json()) == 2
    assert b.get(f"/api/sent/{tracked.id}/replies").status_code == 404
    # Retention-trigger cleanup works for database maintenance deletions.
    with Session(engine) as db:
        db.execute(delete(Message).where(Message.delivery_id == tracked.id))
        db.delete(db.get(Delivery, tracked.id))
        db.commit()
        assert (
            db.scalar(
                select(func.count(Event.id)).where(Event.delivery_id == tracked.id)
            )
            == 0
        )
        assert (
            db.scalar(select(func.count(Link.id)).where(Link.delivery_id == tracked.id))
            == 0
        )
    assert guest.get(f"/api/track/click/{links[0].token}").status_code == 404


def test_safe_direct_anchors_and_substitution():
    from app.models import Contact
    from app.services.sending import substitute

    body = '<a href="mailto:person@example.org">Email</a> <a href="tel:+123456789">Call</a> {{name}}'
    person = Contact(
        name='<img src="https://evil.example.org/pixel">',
        company="A & B",
        role="Developer",
    )
    render(body, lambda _: pytest.fail("Direct anchors must not be tracked"))
    text = substitute(body, person, escape=True)
    plain, markup = render(text)
    assert (
        'href="mailto:person@example.org"' in markup
        and 'href="tel:+123456789"' in markup
    )
    assert "<img" not in markup and "&lt;img" in markup
    assert "<img" in plain


def test_protected_routes_remain_private():
    guest = TestClient(app)
    for path in (
        "/api/sent",
        "/api/analytics",
        "/api/bootstrap",
        "/api/contacts",
        "/api/resumes",
        "/api/inbox",
        "/api/campaigns",
    ):
        assert guest.get(path).status_code == 401
    assert (
        guest.put("/api/settings/tracking", json={"tracking_open": True}).status_code
        == 401
    )
    assert guest.post("/api/auth/google/start").status_code == 401


def test_query_names_that_resemble_html_entities():
    targets = []
    url = "https://example.org/?x=1&copy=2&not=3&reg=4"

    def rewrite(target):
        targets.append(target)
        return target

    plain, markup = render(url + '\n<a href="' + url + '">Link</a>', rewrite)
    assert targets == [url, url]
    assert url in plain and "&amp;copy=2&amp;not=3&amp;reg=4" in markup
