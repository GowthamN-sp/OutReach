"""Run against disposable SQLite data and two loopback servers. No Gmail calls."""

import os
import sqlite3
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright
from workflow_checks import verify_workflows

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / "frontend"
BACK = ROOT / "backend"


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def server(stack, args, cwd, env, url):
    process = subprocess.Popen(
        args, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    def stop():
        process.terminate()
        process.wait(timeout=15)

    stack.callback(stop)
    for _ in range(150):
        if process.poll() is not None:
            raise RuntimeError("Server exited: " + str(args))
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("Server did not start: " + url)


def run():
    with ExitStack() as stack:
        tmp = Path(
            stack.enter_context(tempfile.TemporaryDirectory(ignore_cleanup_errors=True))
        )
        api_port, ui_port = port(), port()
        base = f"http://127.0.0.1:{ui_port}"
        api = f"http://127.0.0.1:{api_port}"
        env = dict(
            os.environ,
            V2_DATABASE_PATH=str(tmp / "workspace.db"),
            APP_ENV="test",
            COOKIE_SECURE="false",
            ALLOW_SIGNUP="true",
            FRONTEND_URL=base,
            API_PROXY_TARGET=api,
            GOOGLE_CLIENT_ID="",
            GOOGLE_CLIENT_SECRET="",
            ENCRYPTION_KEY="",
            PUBLIC_BASE_URL="https://tracking.example.org",
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACK,
            env=env,
            check=True,
        )
        server(
            stack,
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--port",
                str(api_port),
                "--no-access-log",
            ],
            BACK,
            env,
            api + "/api/health",
        )
        server(
            stack,
            [
                os.environ.get("NODE_BINARY") or shutil.which("node") or "node",
                "node_modules/vite/bin/vite.js",
                "--host",
                "127.0.0.1",
                "--port",
                str(ui_port),
                "--strictPort",
            ],
            FRONT,
            env,
            base,
        )
        pw = stack.enter_context(sync_playwright())
        browser = pw.chromium.launch(
            channel=os.getenv("BROWSER_CHANNEL", "chrome"), headless=True
        )
        stack.callback(browser.close)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.set_default_timeout(12000)
        page.set_default_navigation_timeout(45000)
        # Keep verification independent of remote font availability.
        page.route("https://fonts.googleapis.com/**", lambda route: route.abort())
        page.route("https://fonts.gstatic.com/**", lambda route: route.abort())
        issues = []
        page.on("pageerror", lambda e: issues.append(str(e)))

        def audit(label):
            page.wait_for_load_state("networkidle")
            failures = page.evaluate((FRONT / "tests/contrast.js").read_text())
            assert not failures, (label, failures[:8])
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), ("overflow", label)
            folder = os.getenv("OD_SCREENSHOTS")
            if folder and label in {
                "dashboard-dark-1440",
                "dashboard-light-1440",
                "signup-light",
                "signup-dark",
                "dashboard-light-390",
                "contacts-dialog-light",
                "compose-dark",
                "analytics-dark-1440",
                "sent-dark-390",
                "email-detail-dark",
                "recipient-review-dark",
                "import-review-dark",
            }:
                Path(folder).mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(Path(folder) / (label + ".png")), animations="disabled"
                )

        def theme(value):
            if page.locator("html").get_attribute("data-theme") != value:
                toggle = page.get_by_role("button", name="Dark mode", exact=True)
                toggle.focus()
                page.keyboard.press("Space")
            expect(page.locator("html")).to_have_attribute("data-theme", value)

        page.goto(base + "/contacts")
        expect(page).to_have_url(base + "/login")
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        page.get_by_role("link", name="Create an account").click()
        audit("signup-dark")
        theme("light")
        audit("signup-light")
        page.reload()
        expect(page.locator("html")).to_have_attribute("data-theme", "light")
        page.get_by_label("Full name").fill("Alex Morgan")
        email = "qa-" + uuid4().hex + "@example.org"
        page.get_by_label("Email address").fill(email)
        page.locator("[name=password]").fill("a dedicated test password")
        page.locator("[name=confirm]").fill("wrong")
        page.get_by_role("button", name="Create account").click()
        expect(page.get_by_role("alert")).to_contain_text("must match")
        audit("validation-light")
        page.locator("[name=confirm]").fill("a dedicated test password")
        page.get_by_role("button", name="Create account").click()
        expect(page).to_have_url(base + "/dashboard")
        page.goto(base + "/contacts")
        page.get_by_role("button", name="Add contact", exact=True).click()
        audit("contacts-dialog-light")
        modal = page.get_by_role("dialog")
        modal.get_by_label("Name", exact=True).fill("Jordan Lee")
        modal.get_by_label("Email address").fill("jordan@example.org")
        modal.get_by_role("button", name="Save contact").click()
        expect(page.get_by_text("Jordan Lee")).to_be_visible()
        page.goto(base + "/campaigns")
        page.get_by_role("button", name="Create campaign", exact=True).click()
        page.get_by_label("Campaign name").fill("Design recruiting")
        page.get_by_label("Subject line").fill("Hello {{name}}")
        page.get_by_label("Message body").fill("Thanks for your time, {{name}}.")
        page.get_by_role("button", name="Save campaign").click()
        expect(
            page.get_by_role("button", name="Design recruiting", exact=False)
        ).to_be_visible()
        # Exercise populated tables and conversation styles without contacting Google.
        with sqlite3.connect(tmp / "workspace.db") as db:
            uid = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()[
                0
            ]
            cid = db.execute(
                "SELECT id FROM campaigns WHERE user_id=?", (uid,)
            ).fetchone()[0]
            contact = db.execute(
                "SELECT id FROM contacts WHERE user_id=?", (uid,)
            ).fetchone()[0]
            recipient = "jordan@example.org"
            mailbox = "alex@example.org"
            delivery = db.execute(
                "INSERT INTO deliveries (user_id,campaign_id,contact_id,gmail_message_id,gmail_thread_id,mailbox,recipient,sent_at,status,token) VALUES (?,?,?,?,?,?,?,CURRENT_TIMESTAMP,?,?)",
                (
                    uid,
                    cid,
                    contact,
                    "test-message",
                    "thread",
                    mailbox,
                    recipient,
                    "Sent",
                    "test-only-open-token-1234567890",
                ),
            ).lastrowid
            for direction, sender, to, body in (
                ("outbound", mailbox, recipient, "Hi Jordan"),
                ("inbound", recipient, mailbox, "Thanks for reaching out."),
            ):
                db.execute(
                    "INSERT INTO messages (user_id,delivery_id,gmail_message_id,gmail_thread_id,mailbox,sender,recipient,subject,body,received_at,direction,internet_id) VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,?,?)",
                    (
                        uid,
                        delivery,
                        direction,
                        "thread",
                        mailbox,
                        sender,
                        to,
                        "Design recruiting",
                        body,
                        direction,
                        "<sample@example.org>",
                    ),
                )
            db.execute("UPDATE deliveries SET tracking_open=1,tracking_click=1,subject='Hello Jordan',body='Thanks for your time, Jordan.' WHERE id=?", (delivery,))
            db.execute("INSERT INTO tracked_links(user_id,delivery_id,token,target) VALUES(?,?,?,?)", (uid, delivery, 'test-only-click-token-1234567890', 'https://example.org'))
        assert page.request.get(base + "/api/track/open/test-only-open-token-1234567890").status == 200
        assert page.request.get(base + "/api/track/click/test-only-click-token-1234567890", max_redirects=0).status == 302
        page.goto(base + "/sent")
        theme("dark")
        page.get_by_label("Search", exact=True).fill("Hello Jordan")
        page.get_by_role("button", name="Jordan Lee", exact=True).click()
        expect(page.get_by_role("dialog")).to_contain_text("Thanks for your time, Jordan.")
        expect(page.get_by_role("dialog")).to_contain_text("Open signal")
        expect(page.get_by_role("dialog")).to_contain_text("Click signal")
        expect(page.get_by_role("dialog")).to_contain_text("Thanks for reaching out.")
        audit("email-detail-dark")
        page.get_by_role("button", name="Close dialog").click()
        page.get_by_label("Search", exact=True).fill("No such subject")
        expect(page.get_by_text("No matching messages", exact=True)).to_be_visible()
        page.get_by_role("button", name="Replies sent", exact=True).click()
        expect(page.get_by_role("heading", name="Replies sent through OutreachDesk")).to_be_visible()
        expect(page.get_by_text("No matching messages", exact=True)).to_be_visible()
        page.goto(base + "/settings")
        page.get_by_label("Open tracking", exact=True).check()
        page.get_by_label("Click tracking", exact=True).check()
        page.get_by_role("button", name="Save tracking defaults").click()
        expect(page.get_by_text("Tracking defaults saved for new campaigns", exact=True)).to_be_visible()
        page.reload()
        expect(page.get_by_label("Open tracking", exact=True)).to_be_checked()
        page.route("**/api/analytics", lambda route: route.fulfill(status=503, content_type="application/json", body='{"detail":"Test analytics unavailable"}'))
        page.goto(base + "/analytics")
        expect(page.get_by_role("alert")).to_contain_text("Test analytics unavailable")
        page.unroute("**/api/analytics")
        page.get_by_role("button", name="Retry", exact=True).click()
        expect(page.get_by_text("Open-signal rate", exact=True)).to_be_visible()
        for width in (() if os.getenv("OD_FOCUSED") else (1440, 820, 390)):
            page.set_viewport_size({"width": width, "height": 900})
            for value in ("dark", "light"):
                theme(value)
                for route in (
                    "dashboard",
                    "contacts",
                    "campaigns",
                    "inbox",
                    "resume",
                    "sent",
                    "analytics",
                    "settings",
                ):
                    page.goto(base + "/" + route)
                    expect(page.locator("h1")).to_be_visible()
                    audit(f"{route}-{value}-{width}")
                if width == 390:
                    page.get_by_role("button", name="Open navigation").click()
                    page.get_by_role("button", name="Contacts", exact=True).click()
                    expect(page).to_have_url(base + "/contacts")
        page.set_viewport_size({"width": 1440, "height": 960})
        theme("dark")
        page.goto(base + "/campaigns")
        page.get_by_role("button", name="Create campaign", exact=True).click()
        expect(page.get_by_label("Open tracking", exact=True)).to_be_checked()
        expect(page.get_by_label("Click tracking", exact=True)).to_be_checked()
        audit("compose-dark")
        page.get_by_role("button", name="Close dialog").click()
        verify_workflows(page, base, tmp / "workspace.db", uid, cid, delivery, audit)
        page.get_by_role("button", name="Log out").click()
        expect(page).to_have_url(base + "/login")
        page.locator("[name=email]").fill(email)
        page.locator("[name=password]").fill("a dedicated test password")
        page.get_by_role("button", name="Sign in", exact=True).click()
        expect(page).to_have_url(base + "/dashboard")
        page.reload()
        expect(
            page.get_by_role("heading", name="Good to see you, Alex")
        ).to_be_visible()
        assert not issues, issues
        print(
            "Passed account, navigation, keyboard theme and refresh checks. " + (
                "Focused workflow run; viewport matrix skipped."
                if os.getenv("OD_FOCUSED") else
                "Audited 8 workspace pages in 2 themes at 3 widths, plus authentication and dialogs."
            )
        )


if __name__ == "__main__":
    run()
