"""Additional real-browser regressions, using only the harness's disposable DB."""

import io
import sqlite3

from openpyxl import Workbook
from playwright.sync_api import expect


def pdf_address():
    stream = b"BT /F1 12 Tf 50 750 Td (pdf.person@example.org) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    content = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(content))
        content += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(content)
    content += b"xref\n0 6\n0000000000 65535 f \n"
    content += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    return content + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()


def verify_workflows(page, base, database, uid, cid, delivery, audit):
    send_attempts = []

    def block_sends(route):
        send_attempts.append(route.request.url)
        route.abort()

    page.route("**/api/send", block_sends)
    page.set_viewport_size({"width": 1440, "height": 960})

    def go(name):
        # Navigate within React so successful cached results survive page changes.
        page.get_by_role("button", name=name, exact=True).click()

    # A failed initial request must not show an empty result; retry restores data.
    for route_name, endpoint, empty_copy in (
        ("Campaigns", "campaigns*", "Your first campaign awaits"),
        ("Contacts", "contacts*", "No contacts yet"),
        ("Inbox", "inbox?*", "No synced threads"),
        ("Sent emails", "sent?*", "No matching messages"),
        ("Overview", "analytics", "Your outreach journey starts here"),
        ("Analytics", "analytics", "No matching campaigns"),
    ):
        pattern = "**/api/" + endpoint
        page.route(pattern, lambda route: route.fulfill(status=503, content_type="text/plain", body="Service unavailable"))
        page.goto(base + "/dashboard" if route_name != "Overview" else base + "/contacts")
        go(route_name)
        expect(page.get_by_role("alert").filter(has_text="Could not load").first).to_be_visible()
        expect(page.get_by_text(empty_copy, exact=True)).not_to_be_visible()
        page.unroute(pattern)
        for button in page.get_by_role("button", name="Retry", exact=True).all():
            button.click()
        expect(page.get_by_role("alert").filter(has_text="Could not load")).to_have_count(0)
        page.wait_for_load_state("networkidle")

    page.goto(base + "/campaigns")
    expect(page.get_by_role("button", name="Design recruiting", exact=False)).to_be_visible()
    go("Contacts")
    page.route("**/api/campaigns?view=active*", lambda route: route.fulfill(status=503, json={"detail": "Temporary campaign outage"}))
    go("Campaigns")
    expect(page.get_by_role("alert")).to_contain_text("Temporary campaign outage")
    expect(page.get_by_role("button", name="Design recruiting", exact=False)).to_be_visible()
    expect(page.get_by_text("Your first campaign awaits")).not_to_be_visible()
    page.unroute("**/api/campaigns?view=active*")
    page.get_by_role("button", name="Retry", exact=True).click()
    expect(page.get_by_role("alert")).to_have_count(0)

    # Independent defaults survive reload and remain independently overridable.
    page.goto(base + "/settings")
    page.get_by_label("Open tracking", exact=True).check()
    page.get_by_label("Click tracking", exact=True).uncheck()
    page.get_by_role("button", name="Save tracking defaults").click()
    expect(page.get_by_text("Tracking defaults saved for new campaigns", exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_label("Open tracking", exact=True)).to_be_checked()
    expect(page.get_by_label("Click tracking", exact=True)).not_to_be_checked()

    page.goto(base + "/campaigns")
    page.get_by_role("button", name="Create campaign", exact=True).click()
    expect(page.get_by_label("Open tracking", exact=True)).to_be_checked()
    expect(page.get_by_label("Click tracking", exact=True)).not_to_be_checked()
    page.get_by_label("Click tracking", exact=True).check()
    page.get_by_label("Click tracking", exact=True).uncheck()
    page.get_by_label("Campaign name").fill("Recoverable draft")
    page.get_by_label("Subject line").fill("Hi {{name}} at {{company}}")
    page.get_by_label("Message body").fill("Applying for {{role}}. My resume is attached.")
    expect(page.get_by_role("dialog")).to_contain_text("no file is selected")
    page.get_by_role("button", name="Save campaign").click()
    card = page.locator(".campaign-card").filter(has=page.get_by_role("heading", name="Recoverable draft", exact=True))
    expect(card).to_be_visible()
    card.locator("summary").click()

    # Failed deletion keeps the card; successful deletion is recoverable after reload.
    page.route("**/api/campaigns/*", lambda route: route.fulfill(status=503, json={"detail": "Deletion temporarily unavailable"}) if route.request.method == "DELETE" else route.continue_())
    card.get_by_role("button", name="Delete draft", exact=True).click()
    expect(page.get_by_role("dialog")).to_contain_text('Delete draft "Recoverable draft"?')
    page.get_by_role("dialog").get_by_role("button", name="Delete draft", exact=True).click()
    expect(card).to_be_visible()
    expect(card.get_by_role("alert")).to_contain_text("Deletion temporarily unavailable")
    page.unroute("**/api/campaigns/*")
    card.get_by_role("button", name="Delete draft", exact=True).click()
    page.get_by_role("dialog").get_by_role("button", name="Delete draft", exact=True).click()
    expect(card).to_have_count(0)
    page.reload()
    page.get_by_role("button", name="Deleted drafts", exact=True).click()
    expect(card).to_be_visible()
    card.locator("summary").click()
    card.get_by_role("button", name="Restore", exact=True).click()
    page.get_by_role("dialog").get_by_role("button", name="Restore", exact=True).click()
    page.get_by_role("button", name="All campaigns", exact=True).click()
    expect(card).to_be_visible()

    # Archive a sent campaign from detail; all underlying records stay intact.
    with sqlite3.connect(database) as db:
        before = {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("deliveries", "tracking_events", "tracked_links", "messages")}
    page.get_by_role("button", name="Design recruiting", exact=False).click()
    page.locator(".back-row summary").click()
    expect(page.get_by_role("button", name="Delete draft", exact=True)).to_have_count(0)
    page.get_by_role("button", name="Archive campaign", exact=True).click()
    page.get_by_role("dialog").get_by_role("button", name="Archive campaign", exact=True).click()
    expect(page.get_by_role("button", name="All campaigns", exact=True)).to_be_visible()
    page.get_by_role("button", name="Archived", exact=True).click()
    page.get_by_role("button", name="Design recruiting", exact=False).click()
    expect(page.get_by_text("Jordan Lee", exact=True)).to_be_visible()
    expect(page.get_by_text("Restore this campaign to select recipients and send.")).to_be_visible()
    with sqlite3.connect(database) as db:
        after = {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in before}
    assert before == after
    page.locator(".back-row summary").click()
    page.get_by_role("button", name="Restore", exact=True).click()
    page.get_by_role("dialog").get_by_role("button", name="Restore", exact=True).click()
    page.get_by_role("button", name="All campaigns", exact=True).click()

    # Seed only this disposable database, with explicit Test source metadata.
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO gmail_accounts(user_id,email,refresh) VALUES(?,?,?)", (uid, "alex@example.org", "not-a-real-credential"))
        for index in range(23):
            db.execute("INSERT INTO contacts(user_id,email,name,company,role,status,source) VALUES(?,?,?,?,?,'New','Test batch')", (uid, f"qa{index}@example.org", f"QA {index}", "Acme", "Engineer"))
    page.reload()
    page.get_by_role("button", name="Recoverable draft", exact=False).click()
    jordan = page.locator(".recipient-row").filter(has_text="jordan@example.org")
    jordan.get_by_role("checkbox").check()
    page.get_by_label("Filter recipients").fill("qa")
    expect(page.get_by_text("1 of 20 selected", exact=True)).to_be_visible()
    for checkbox in page.locator(".recipient-row input").all()[:19]:
        checkbox.check()
    expect(page.get_by_text("20 of 20 selected", exact=True)).to_be_visible()
    expect(page.locator(".recipient-row input:not(:checked)").first).to_be_disabled()
    page.get_by_label("Filter recipients").fill("")
    page.get_by_label("Show selected", exact=True).check()
    expect(page.locator(".recipient-row")).to_have_count(20)
    page.get_by_role("button", name="Clear selection").click()
    expect(page.get_by_text("0 of 20 selected", exact=True)).to_be_visible()
    page.get_by_label("Show selected", exact=True).uncheck()
    page.get_by_label("Exclude contacts marked Test in source").check()
    expect(page.locator(".recipient-row")).to_have_count(1)
    page.get_by_label("Exclude contacts marked Test in source").uncheck()
    page.get_by_label("Import batch", exact=True).select_option("Test batch")
    expect(page.locator(".recipient-row")).to_have_count(23)
    page.get_by_label("Import batch", exact=True).select_option("")
    jordan.get_by_role("checkbox").check()
    page.get_by_role("button", name="Review & send to 1 contact(s)", exact=True).click()
    modal = page.get_by_role("dialog")
    expect(modal).to_contain_text("{{company}}")
    expect(modal).to_contain_text("{{role}}")
    expect(modal).to_contain_text("Hi Jordan Lee at your organization")
    expect(modal).to_contain_text("Resume filename: No attachment")
    expect(modal.get_by_role("button", name="Confirm send to 1 recipient")).to_be_disabled()
    modal.get_by_label("jordan@example.org company", exact=True).fill("Acme")
    modal.get_by_label("jordan@example.org role", exact=True).fill("Engineer")
    modal.get_by_role("button", name="Save recipient changes").click()
    expect(modal).to_contain_text("Hi Jordan Lee at Acme")
    expect(modal).to_contain_text("Applying for Engineer.")
    expect(modal.get_by_role("button", name="Confirm send to 1 recipient")).to_be_enabled()
    audit("recipient-review-dark")
    for width in (820, 390):
        page.set_viewport_size({"width": width, "height": 900})
        audit(f"recipient-review-{width}")
    page.set_viewport_size({"width": 1440, "height": 960})
    modal.get_by_role("button", name="Remove recipient").click()
    expect(modal).to_have_count(0)
    # Remove an active draft from detail and return to the list.
    page.locator(".back-row summary").click()
    page.get_by_role("button", name="Delete draft", exact=True).click()
    page.get_by_role("dialog").get_by_role("button", name="Delete draft", exact=True).click()
    expect(page.get_by_role("button", name="Deleted drafts", exact=True)).to_be_visible()

    # CSV correction / skip / final count, then Excel and PDF previews.
    page.goto(base + "/contacts")
    page.locator('input[type="file"]').set_input_files({"name": "review.csv", "mimeType": "text/csv", "buffer": b"email,name,company,role\njordan@example.org,Jordan,,\nfresh@example.org,Fresh,,\nfresh@example.org,Duplicate,,\ninvalid,Bad,,"})
    modal = page.get_by_role("dialog")
    expect(modal).to_contain_text("1 invalid addresses")
    expect(modal).to_contain_text("1 duplicates within file")
    expect(modal).to_contain_text("1 already in Contacts")
    modal.get_by_label("Skip row 1", exact=True).check()
    modal.get_by_label("Skip row 3", exact=True).check()
    modal.locator("fieldset").nth(3).get_by_label("email", exact=True).fill("fixed@example.org")
    expect(modal).to_contain_text("Final import count: 2")
    audit("import-review-dark")
    for width in (820, 390):
        page.set_viewport_size({"width": width, "height": 900})
        audit(f"import-review-{width}")
    page.set_viewport_size({"width": 1440, "height": 960})
    modal.get_by_role("button", name="Confirm import 2 contacts").click()
    expect(page.get_by_text("fresh@example.org", exact=True)).to_be_visible()
    expect(page.get_by_text("fixed@example.org", exact=True)).to_be_visible()

    workbook = Workbook()
    workbook.active.append(["email", "name"])
    workbook.active.append(["excel.person@example.org", "Excel"])
    workbook.active.append(["bad-address", "Correct me"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    page.locator('input[type="file"]').set_input_files({"name": "review.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "buffer": buffer.getvalue()})
    expect(modal).to_contain_text("1 invalid addresses")
    modal.get_by_label("Skip row 2", exact=True).check()
    modal.get_by_role("button", name="Confirm import 1 contact").click()
    expect(page.get_by_text("excel.person@example.org", exact=True)).to_be_visible()
    page.locator('input[type="file"]').set_input_files({"name": "review.pdf", "mimeType": "application/pdf", "buffer": pdf_address()})
    expect(modal.get_by_label("email", exact=True)).to_have_value("pdf.person@example.org")
    expect(modal).to_contain_text("1 missing personalization fields")
    modal.get_by_role("button", name="Confirm import 1 contact").click()
    expect(page.get_by_text("pdf.person@example.org", exact=True)).to_be_visible()

    # Connection status is distinct from a failed sync and survives navigation.
    page.route("**/api/inbox/sync", lambda route: route.fulfill(status=502, json={"detail": "Test sync unavailable"}))
    page.goto(base + "/inbox")
    page.get_by_role("button", name="Sync Gmail replies", exact=True).click()
    expect(page.get_by_label("Gmail sync status")).to_contain_text("Connected")
    expect(page.get_by_label("Gmail sync status")).to_contain_text("Last sync failed")
    expect(page.get_by_role("button", name="Retry sync", exact=True)).to_be_visible()
    page.unroute("**/api/inbox/sync")
    assert not send_attempts, send_attempts
    print("Passed request retries, retained data, persistent draft recovery, archive/history, recipient limit/filter/review/correction, independent defaults, CSV/Excel/PDF previews and sync/connection separation. No send endpoint was called.")
