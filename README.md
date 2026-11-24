# OutreachDesk

OutreachDesk is a personal Gmail outreach workspace for managing recruiter contacts, resume versions, campaigns and conversations. Each OutreachDesk account owns its data. Gmail connection is optional until a user sends a message or syncs conversations.

Dark mode is the first-visit default. The sun/moon control on the authentication screens and workspace header changes the whole interface. The browser remembers the choice across refreshes and sign-ins. The only value the app saves in local storage is the theme preference.

## Run on Windows

Use two PowerShell windows. Start both from the project directory. The backend launcher installs dependencies and upgrades the **v2** database before starting FastAPI. It falls back to `.venv-v2` if the old `.venv` references a missing interpreter.

**Terminal 1**

```powershell
Set-Location D:\Projects\OutreachDesk
.\start-backend.ps1
.venv\Scripts\Activate.ps1
```

**Terminal 2**

```powershell
Set-Location D:\Projects\OutreachDesk
.\start-frontend.ps1
```

Open [OutreachDesk on localhost](http://localhost:5173). Use the same hostname throughout the Google authorization flow so the callback receives the session cookie.

### Manual setup for a fresh checkout

Use Python 3.11.15 and Node.js 22.12+ with npm. Check which interpreter `python --version` selects in your terminal. In an existing checkout with a broken virtual environment, use the launchers above to preserve it.

```powershell
Set-Location D:\Projects\OutreachDesk\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
```

```powershell
Set-Location D:\Projects\OutreachDesk\frontend
npm.cmd ci
npm.cmd run dev
```

## First workspace

1. Choose **Create an account**, enter a name and email, and choose a 12–128 character password. Registration opens the personal dashboard. Settings supports changing the profile, sign-in email and password. A password change invalidates other sessions.
2. Open **Resume Vault** to upload named PDFs up to 8 MB each. Preview, download or delete versions and select the default. Each campaign stores the particular resume version chosen when the campaign was created.
3. Open **Contacts** to add or edit recruiters or import a CSV, XLSX workbook or text-readable PDF. Review and correct names, addresses, companies and roles before saving. Duplicate email addresses are skipped within the current account. Each file may contain up to 1,000 distinct contacts. PDF import reads up to 25 pages and supports readable tables and email text. Image-only scans require OCR before import.
4. Connect a mailbox in **Settings** when ready to send.
5. In **Campaigns**, create a campaign with a subject and plain-text body. Use `{{name}}`, `{{company}}` and `{{role}}` for personalization. Save the text as a reusable template if desired. Choose an attachment and use **Preview PDF** to check it.
6. Open the saved campaign, select one to 20 contacts and review the actual recipients in the confirmation dialog. Each recipient receives an individual message. **Sent emails**, campaign history and the **History** action on a contact show submissions and errors.
7. In **Inbox**, choose **Sync Gmail replies** to fetch sent messages and replies from the most recent 120 tracked conversations for the connected mailbox. Open a conversation to reply inside OutreachDesk or open the original in Gmail. Disconnecting drops the locally stored Gmail credential. Existing threads stay in the workspace.

## Google OAuth and configuration

Enable the Gmail API in Google Cloud, configure a consent screen and add your Gmail address as a test user during development. Create a **Web application** OAuth client with the exact authorized redirect URI `http://localhost:8000/api/auth/google/callback`. Put its ID and secret in the backend environment. The app requests `gmail.send` and `gmail.readonly` for sending, reading the connected address and synchronizing thread bodies. Public distribution with the read scope may require Google verification. [Google Cloud credentials](https://console.cloud.google.com/apis/credentials) · [Gmail scope reference](https://developers.google.com/workspace/gmail/api/auth/scopes) · [Gmail thread requirements](https://developers.google.com/workspace/gmail/api/guides/threads)

Generate a Fernet key once if this deployment needs a new key. Save it privately as `ENCRYPTION_KEY` and restart the backend. Keep an existing working key when upgrading.

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Defaults to `development`. Set `production` when deployed. |
| `ALLOW_SIGNUP` | Development defaults to open and production defaults to closed. The signup endpoint applies a database-backed attempt limit. |
| `FRONTEND_URL` | Exact trusted browser origin for CORS, origin checks and OAuth completion. Default `http://localhost:5173`. |
| `COOKIE_SECURE` | Set true for HTTPS. Production mode enforces secure cookies. |
| `V2_DATABASE_PATH` | Defaults to `data/outreachdesk-v2.db`. Relative paths resolve from `backend`. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Google OAuth web-client credentials and callback. |
| `ENCRYPTION_KEY` | Fernet key for Gmail refresh tokens. |
| `PUBLIC_BASE_URL` | Optional externally reachable HTTPS backend origin for opt-in image and click callbacks. |
| `DAILY_SEND_LIMIT` | Per-user rolling 24-hour quota, default 25. Campaign submissions and dashboard replies share the limit. |
| `API_PROXY_TARGET` | Frontend development proxy target. Default `http://127.0.0.1:8000`. |

The old `APP_PASSWORD`, `APP_SECRET`, `DATABASE_PATH` and `FILES_DIR` settings belong to v1. Application sessions use random opaque HttpOnly cookies and server-side expiry. The database stores a digest of the cookie and a separate CSRF token. Remembered sessions expire after 14 days, ordinary sessions after 12 hours. Passwords use Argon2id. Google authorization state is session-bound, single-use and expires after ten minutes.

## Source layout

```text
backend/
  app/
    main.py                     FastAPI assembly, CORS, validation and error handling
    config.py, security.py      Environment, passwords, sessions, CSRF and throttling
    db.py, models.py            Database sessions, ownership checks and ORM entities
    schemas.py                  Pydantic request and response models
    api/
      auth.py, gmail.py         Accounts, profiles and Google authorization
      contacts.py, resumes.py   Contacts, import and private PDF endpoints
      campaigns.py, mail.py     Campaigns, templates, send and conversation routes
      analytics.py, tracking.py Reporting and public tracking callbacks
    integrations/google.py      Google OAuth and Gmail HTTP client
    services/
      importer.py               CSV, Excel and PDF extraction
      sending.py, inbox.py      Reservations, MIME messages, sync and replies
  alembic/versions/             Versioned database schema
  tools/migrate_legacy.py       Offline ownership assignment
  tests/                       Account, isolation, Gmail, analytics and migration checks
  data/                        Local databases and original v1 files
  alembic.ini, pyproject.toml
  requirements.txt, requirements-dev.txt, .env.example

frontend/
  src/
    main.jsx, app/App.jsx       React entry, session lifecycle and protected routes
    components/                 Layout, theme control, dialogs, charts and composer
    pages/                      Auth, Dashboard, Contacts, Campaigns, Inbox,
                                Sent, Analytics, Resume, Profile and Settings
    services/api.js             Cookie/CSRF client and paged collection requests
    styles/                     Theme variables and responsive styles
    utils/format.js             Dates, times and numbers
  tests/                       Chrome workflow, contrast and layout checks
  index.html, package.json, package-lock.json
  vite.config.js, eslint.config.js, .env.example
```

PDF bytes are stored in private, owner-scoped database rows. This keeps backup, deletion and default selection transactional. A campaign recipient is represented by one delivery row per campaign/contact pair. Synced messages are grouped by owner, mailbox and Gmail thread ID.

## Migrations and existing data

Run `python -m alembic upgrade head` from the backend directory using the project interpreter. V2 starts with a separate SQLite file. The migration checks for a v1 schema and refuses to upgrade it in place.

For a shared v1 installation, keep ambiguous records archived. Where ownership is known, an operator can copy a **single-owner** archive into a registered, empty v2 workspace. Stop both servers and back up the legacy database, uploads and v2 database first. Review the archive and independently verify the destination account. For mixed-owner source data, prepare a reviewed, referentially complete single-owner copy for each intended owner.

The following example uses a destination account that the operator has already verified. Set `$owner` to its actual sign-in email.

```powershell
Set-Location D:\Projects\OutreachDesk\backend
$owner = 'verified-owner@example.org'
.\.venv\Scripts\python.exe -m tools.migrate_legacy --source .\data\outreachdesk.db --owner $owner
```

The default invocation previews counts and rolls back. Add `--resume .\data\uploads\active_resume.pdf` when migrating an existing resume. Repeat the reviewed command with `--apply` to commit. The tool opens the archive read-only, builds new IDs, preserves linked send and tracking history and rolls back if it encounters conflicting or orphaned records. Duplicate attempts for one campaign/contact pair require operator review before import. Gmail must be reconnected by the owner. Preserve the original archive for audit.

## Sending and analytics

- **Sent** counts Gmail-accepted campaign messages. Campaign reply rate is the proportion with at least one synced reply from the original recipient. Refresh the Inbox to update it.
- **Open signals** count distinct tracked messages whose image was requested. **Click signals** count distinct tracked messages with a followed link. Image blocking, Gmail proxy caching and security scanners can distort both measures. PDF attachment activity is unavailable.
- Tracking is opt-in per campaign and requires a reachable HTTPS callback origin. A localhost-only service can send and sync Gmail but recipients cannot reach its tracking routes.
- A database reservation prevents repeat submissions of the same campaign to the same contact. Explicit Gmail rejection permits a manual retry. A timeout or interruption may leave a submission **Unconfirmed** or **Preparing**. Check Gmail Sent before taking further action. These statuses block automatic retries.

## Verification

From `backend`, choose the working project interpreter. Substitute `.venv-v2` if the launcher selected its fallback.

```powershell
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python -m pip install -r requirements-dev.txt
& $python -m compileall -q app alembic tools
& $python -m ruff check app alembic tests tools
& $python -m pytest -q
```

From `frontend`, install the lockfile and run the static checks.

```powershell
npm.cmd ci
npm.cmd run lint
npm.cmd run build
```

The browser suite starts a temporary backend and Vite server on loopback ports. It requires Chrome, Node on PATH and Python Playwright in the test environment.

```powershell
Set-Location D:\Projects\OutreachDesk\backend
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe ..\frontend\tests\browser_smoke.py
```

The suite can use `NODE_BINARY` for an explicit Node executable and `OD_SCREENSHOTS` for optional screenshots. It checks dark-first rendering, keyboard toggling, remembered choice, form validation, protected navigation, representative text contrast and page overflow. Gmail integration tests use mocks. Live Google consent, actual message acceptance and externally hosted tracking require deployment-specific verification.

## Deployment

Serve the built frontend and proxy `/api` under the same HTTPS origin. Configure SPA fallback to `index.html`, the production frontend origin, Google callback and externally reachable tracking origin. Run Alembic before starting the API. Use `APP_ENV=production`, keep signup closed until enrollment and abuse controls are configured, and restrict database, backup and encryption-key access. Configure your proxy to trust only known forwarding hosts and omit OAuth callback query strings and tracking tokens from access logs. Apply upload-size limits at the proxy and back up the database together with the separately protected encryption key.

## Campaign recovery, recipient review and imports

Run the normal backend launcher after upgrading, or run `python -m alembic upgrade head` from `backend` with the project interpreter before starting the API. Migration `c93f50b8e721` adds nullable campaign recovery timestamps and a separate table for the latest Gmail sync result. Existing campaign contents and delivery history are retained.

Campaign cards and detail pages have an **Actions** menu. **Delete draft** moves a campaign without any delivery history to **Deleted drafts**, where **Restore** remains available after reload or signing in again. Any delivery reservation or attempt, including failed or unconfirmed delivery, prevents draft deletion. **Archive campaign** moves a campaign to **Archived** without changing messages, tracking events, replies or reporting totals. Restore it before sending again. Deletion, archiving and send preparation share the user write lock; send preparation rechecks campaign state after token exchange.

Recipient selection survives searches and filters, supports **Show selected**, **Clear selection**, import-source/batch filtering, and exclusion of contacts explicitly marked `Test` in their source. Older imports only have the source `Import`; their individual batch identities cannot be reconstructed. Review previews use the sender's substitution and plain-text rendering functions. Referenced but missing name/company/role values must be corrected or the recipient removed before sending. Review shows the actual resume filename and warns when attachment copy has no selected file. Tracking defaults remain independent, with per-campaign choices in the composer.

CSV, Excel and table-based PDF previews retain invalid and duplicate rows. Correct or skip flagged rows before confirming the final import count. Missing personalization fields are reported separately from invalid addresses. Free-text PDF extraction can identify readable addresses, but cannot reliably infer missing table rows or arbitrary malformed addresses. New imports store a distinct source/batch label. Commit revalidates addresses and skips addresses added by another request after preview.

Workspace pages distinguish loading, failed, successful-empty and populated results. Failed refreshes retain successful results in account-scoped memory, with an inline Retry action; private workspace data is not saved in browser storage. Requests from an older page/filter cannot overwrite newer results. Inbox reports the persisted latest sync result independently from mailbox connection status. A connected mailbox does not imply a successful sync.

The browser suite uses disposable data and blocks the send endpoint during recovery/review/import regressions. It covers failed requests and retries, retained data after navigation, persistent draft recovery, archive/history preservation, recipient limits and correction, independent tracking defaults, and CSV/Excel/PDF preview. Live Gmail delivery is outside these checks.

Verification for this update: **57 backend tests passed**; Ruff, compilation, ESLint and the production build passed. Chrome passed the workflow suite and audited eight workspace pages in two themes at 1440, 820 and 390 px, plus recipient-review and import dialogs at all three widths. Screenshots are under `qa/recovery/`. The confirmed frontend causes were empty arrays being rendered as successful empty responses after failures, discarded results during refetch, and generic handling of non-JSON server errors. Import normalization previously discarded invalid and duplicate rows before review. The original multi-page server outage was not reproducible through read-only queries against the current database.

The local database was upgraded after a consistent backup at `backend/data/backups/pre-recovery-20261124T154744Z.db`. All pre-existing row/field values across the 13 original application tables matched the backup after migration. SQLite integrity and foreign-key checks passed. No live Gmail sends were made; `.env` and the Gmail encryption key were not changed.

The visual reference for the original dashboard was Anik Deb’s [Website Analytics Dashboard Dark Version](https://dribbble.com/shots/19240388-Website-Analytics-Dashboard-Dark-Version).

## Email tracking: setup and verification

Tracking remains off by default. In **Settings → Optional tracking defaults**, enable open tracking, click tracking, both, or neither. These defaults initialize only new campaigns. Review each campaign's independent controls before sending. Changing preferences never modifies existing campaigns or enables tracking retroactively in previously sent email.

### What changed

The original renderer only linkified URLs when click tracking was enabled, escaped existing HTML anchors, and used a regex that could include punctuation or HTML-escaped query strings in destinations. Public configuration was checked only with `startswith("https://")`, not revalidated at send time. Events had no first/last summaries, click-event link identity, message-level setting snapshots, or original-body snapshots. Settings could not persist tracking defaults, and reporting did not distinguish untracked messages from zero observed signals.

The shared renderer now creates ordinary clickable HTTP/HTTPS links in every campaign email, preserves allowlisted formatting and safe anchors, escapes unsupported markup, and rejects unsafe or malformed destinations. It preserves query strings and common trailing sentence punctuation. Use an explicit HTML anchor when punctuation is intentionally part of a URL. Safe `mailto:` and `tel:` anchors remain direct. Unsubscribe/opt-out paths, `rel="unsubscribe"`, and anchors with `data-no-track` remain direct; mark custom preference, legal or other exempt links with `data-no-track`. Existing tracking paths are not wrapped again. Arbitrary scripts, custom styles, remote images and rich HTML templates are intentionally not supported by this small email allowlist.

Gmail receives UTF-8 plain text and HTML in `multipart/alternative`, nested within `multipart/mixed` when a PDF is attached. The stored resume filename and PDF bytes are unchanged. The plain-text alternative contains original destinations; clicks in a plain-text-only client are not tracked. This follows Gmail's [MIME and base64URL sending workflow](https://developers.google.com/workspace/gmail/api/guides/sending).

Public routes:

- `GET /api/track/open/{token}` returns a transparent 1×1 GIF with no-cache/no-store headers. Invalid, disabled, deleted or nonaccepted-message tokens return the same harmless image without recording an event.
- `GET /api/track/click/{token}` records a signal and returns a 302 redirect only to the stored HTTP/HTTPS destination, revalidated at request time. Invalid or disabled tokens return 404. URL/destination query parameters are ignored.
- Old `/api/o/{token}.gif` and `/api/t/{token}` URLs continue to work for previously tracked messages.

The token is an opaque cryptographically random identifier. New events record `open_signal` or `link_click`, message association, timestamp, token association, and click link ID. Separate message summaries hold first and latest timestamps and total requests; transactional SQL increments avoid losing concurrent requests. Gmail acceptance alone never creates a signal. Tracking events do not store IP addresses, user agents, or location. A forwarded message or a scanner can still generate a signal associated with the original delivery.

### Database migration and preservation

Alembic revision `b82e49a7d610` follows `a7dbf0963495`. It adds user preferences, immutable-at-send message choices/content, first/last/count summaries, event identifier/link associations, event history and link lookup indexes, and SQLite cleanup triggers. It preserves existing users, authentication, Gmail credentials, resumes, campaign records, tokens and events. Old event names are normalized and first/last/count values are backfilled from real history. Old message choices are copied from their immutable campaign choices. No original email body is fabricated for older deliveries, and no link identity is fabricated for historical click events that lacked it.

Back up the SQLite database and separately protect the existing encryption key before upgrading. Do not replace `.env` or rotate `ENCRYPTION_KEY`. Apply migrations from `backend` with a working interpreter:

```powershell
Set-Location D:\Projects\OutreachDesk\backend
.\.verify-env\Scripts\python.exe -m alembic upgrade head
```

This checkout's `.venv` points to a missing Python 3.11 executable. The existing `.verify-env` runs Python 3.13 and has the application/test dependencies. The source targets Python 3.11, but the verification environment for this change is Python 3.13. For a fresh 3.11 environment, install Python 3.11, run `py -3.11 -m venv .venv-v2`, then `.\.venv-v2\Scripts\python.exe -m pip install -r requirements-dev.txt`; substitute that interpreter in the commands below. Do not delete the existing environment or database to repair the launcher.

### Exact local PowerShell commands

Terminal 1 — backend (uses existing configuration and credentials):

```powershell
Set-Location D:\Projects\OutreachDesk\backend
.\.verify-env\Scripts\python.exe -m alembic upgrade head
.\.verify-env\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

Terminal 2 — frontend:

```powershell
Set-Location D:\Projects\OutreachDesk\frontend
npm.cmd run dev -- --port 5173
```

If Node/npm is unavailable on PATH (as in the restricted verification environment), the already installed Playwright runtime can run Vite directly:

```powershell
Set-Location D:\Projects\OutreachDesk\frontend
& ..\backend\.verify-env\Lib\site-packages\playwright\driver\node.exe node_modules\vite\bin\vite.js --host 127.0.0.1 --port 5173
```

Open `http://localhost:5173`; keep the configured `FRONTEND_URL=http://localhost:5173` and existing Google OAuth callback. Do not change CORS, origin checks or authentication to match the tunnel.

Terminal 3 — intentionally expose the local backend for a controlled test:

```powershell
cloudflared tunnel --url http://localhost:8000
```

If needed, install the Cloudflare client using the [official installation instructions](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/). Copy the generated HTTPS origin into the existing `backend/.env`:

```dotenv
PUBLIC_BASE_URL=https://your-generated-host.trycloudflare.com
```

Do not literally use the example hostname. Stop and restart the backend after saving `.env`; Python reload does not reliably reload environment files. Leave the tunnel running for the test. Check `https://your-generated-host.trycloudflare.com/api/health` from outside the local machine. Settings validates URL syntax and rejects localhost/private IP literals; it does not prove DNS, TLS or internet reachability. Private DNS aliases cannot be detected by syntax validation.

Cloudflare Quick Tunnels have temporary hostnames and no uptime guarantee; disconnecting ends access and a new tunnel gets a different hostname. Existing emails retain their original URL, so changing PUBLIC_BASE_URL cannot repair them. Use a stable public HTTPS hostname and managed deployment for long-running campaigns. See [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

The command exposes the entire backend service through Cloudflare, including public login/signup and API documentation, not just tracking routes. Normal contact, resume, Gmail, settings and dashboard APIs still require the existing session and CSRF checks. Set `ALLOW_SIGNUP=false` after creating your test account before exposing a development instance. Do not expose a debugger or unrelated service. Do not place an interactive login gate in front of tracking routes; mail image proxies cannot authenticate. For a production tracking hostname, configure a reverse proxy to expose only the tracking paths; keep the dashboard/API on their protected application origin. Keep access logs disabled/redacted for tokens and OAuth callback queries, protect database/backups, and review Cloudflare/proxy log retention separately from the application's tracking data. Stop the tunnel after testing. This implementation never starts a tunnel automatically.

### Analytics semantics and retention

Overview counts Gmail-accepted campaign messages; open/click counts are unique accepted messages with observed signals. Open-signal rate uses accepted messages with open tracking enabled; click-signal rate uses accepted messages with click tracking enabled. A click-enabled message with no eligible links still belongs to that configured cohort. Without an eligible tracking cohort, rates are null and the UI shows **Not tracked**. An enabled message with no recorded event shows **No signal observed**. Reply rate counts accepted messages with at least one synced inbound reply. Sync Inbox to refresh replies. Active campaigns means campaigns with an accepted send in the last 14 days, because this application has no campaign scheduler/status lifecycle.

Trend charts show unique messages per activity day in UTC; a message can appear on several days, so daily signals should not be summed as lifetime unique-message totals. Campaign reports show sent/open/click/reply message counts and latest activity. Recipient activity and Sent Emails support search, campaign/status/activity filters and paging. Select a recipient for its original source body, tracking choices, paged timestamped events and associated replies. Body source is displayed as escaped text to avoid executing content or requesting a tracking pixel from the dashboard.

Existing retention policy retains contacts with send history and provides no account/message deletion UI. SQLite cleanup triggers ensure event and tracked-link rows are removed transactionally when an operator deletes the associated message or account as part of an authorized retention operation. Delete dependent synced messages and other account records in foreign-key order; unsupported direct parent deletion still fails without partial cleanup. Do not remove delivery reservations just to clear analytics because doing so could permit duplicate sends. There is no automatic event-expiration job; define an appropriate retention period and backup-expiry policy for your deployment. Tokens are effectively bearer identifiers, so do not publish them in UI, support logs or screenshots.

Tracking is optional analytics. Disclose image and link measurement to recipients, determine applicable consent/lawful-basis and retention requirements for your jurisdiction, and honor opt-outs. Enabling a toggle does not itself establish compliance or recipient consent. Review current [ICO storage/access technology guidance](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/cookies-and-similar-technologies/) and, for applicable US commercial email, the [FTC CAN-SPAM guidance](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business). The app does not automatically supply a privacy notice, mailing address, unsubscribe service, or consent registry; those must match your actual use. It never attempts to bypass image blocking, proxy caching, or recipient protections.

### Controlled manual verification (no external contacts)

1. Use only sender/recipient email accounts you control. Run FastAPI and Vite using the commands above.
2. Start the Cloudflare Tunnel yourself. Set PUBLIC_BASE_URL and restart FastAPI. Check the public health URL.
3. Enable both tracking defaults in Settings and save. Create a new campaign and verify both composer checkboxes are enabled.
4. Add only your test recipient. Use a body such as `Hello {{name}}`, a new line, `https://github.com/your-test-profile?tab=repositories`, and `<a href="https://www.linkedin.com/in/your-test-profile">LinkedIn</a>`. Optionally attach a known test PDF.
5. Review and manually send one email. Verify the Sent status means accepted by Gmail and no open signal is created merely by sending.
6. Verify arrival, UTF-8 formatting, clickable GitHub/LinkedIn links, and the unchanged PDF filename/content. Gmail's Show original should contain both plain and HTML MIME alternatives.
7. Load remote images in the recipient mailbox if permitted by that client. Look for an open signal in Sent Emails/Analytics. Blocked or cached images may generate no new request; that is not a failed send.
8. Click a tracked link. Verify the exact original URL opens, including query parameters, and a click signal appears on the correct recipient and campaign. Security scanners may generate earlier/additional signals.
9. Open the email detail view; check first/last timestamps, total requests and event history. Reply from the controlled recipient and sync Inbox; verify the associated reply and reply rate.
10. Stop/restart FastAPI while leaving the tunnel up. Confirm historical signals persist. Repeat a pixel request and confirm first time stays fixed while last time/count update (a mail client may cache and not make another request).
11. Create new campaigns with open-only, click-only and neither enabled. Send only to your controlled account. With neither enabled, ordinary links must still work and the detail view must say Not tracked. Old tracked messages retain their original behavior.
12. Stop the tunnel. Expect old temporary tracking URLs to stop working; do not use them for recruiter campaigns.

### Automated verification

Tests use disposable SQLite databases and mock Gmail calls; they do not send mail. The tests cover all four settings combinations, valid/invalid tokens, GIF response/cache headers, concurrent/repeated requests, first/last summaries, stored redirects, encoding/punctuation/multiple links/anchors, unsafe schemes, ownership isolation, analytics denominators, history pagination, UTF-8 MIME, exact attachment preservation, migration preservation and cleanup. The browser smoke suite uses a temporary database and loopback servers with synthetic test fixtures, then exercises search, details, preference persistence, composer defaults, both themes and three viewport widths.

```powershell
Set-Location D:\Projects\OutreachDesk\backend
.\.verify-env\Scripts\python.exe -m ruff check app alembic tests tools
# Use a new, disposable path; pytest may clear a specified basetemp directory.
.\.verify-env\Scripts\python.exe -m pytest -q --basetemp (Join-Path $PWD ('.test-' + [guid]::NewGuid().ToString('N')))
Set-Location ..\frontend
& ..\backend\.verify-env\Lib\site-packages\playwright\driver\node.exe node_modules\eslint\bin\eslint.js src
& ..\backend\.verify-env\Lib\site-packages\playwright\driver\node.exe node_modules\vite\bin\vite.js build
Set-Location ..
$env:NODE_BINARY = (Resolve-Path .\backend\.verify-env\Lib\site-packages\playwright\driver\node.exe).Path
.\backend\.verify-env\Scripts\python.exe frontend\tests\browser_smoke.py
```

Live Google consent, actual Gmail delivery/recipient rendering, public tunnel reachability and behavior of real Gmail proxies/scanners require the controlled manual test above. No synthetic metrics are used in the running application's dashboards.

Sent Emails also has a **Replies sent** tab for every dashboard reply submission, with search/status/campaign filters and original-body snapshots for new replies. Older reply attempts retain their real status/timestamp but may lack recipient/body metadata; the UI labels those fields unavailable instead of guessing. Dashboard replies use ordinary clickable HTML links and remain untracked. The Accepted by Gmail overview card includes accepted campaign messages plus accepted dashboard replies; its subtitle separates them. Signal/reply rates and trend charts remain explicitly campaign-message metrics, so follow-up replies cannot dilute the tracking cohort or reply rate.

### Changed source files

- Backend configuration and assembly: `backend/.env.example`, `backend/app/main.py`, `backend/app/models.py`, `backend/app/schemas.py`.
- Backend routes: `backend/app/api/analytics.py`, `backend/app/api/auth.py`, `backend/app/api/campaigns.py`, `backend/app/api/tracking.py`, `backend/app/api/sent_replies.py` (new).
- Backend services: `backend/app/services/email_html.py` (new), `backend/app/services/tracking.py` (new), `backend/app/services/reporting.py` (new), `backend/app/services/sending.py`, `backend/app/services/inbox.py`.
- Migration and legacy compatibility: `backend/alembic/versions/b82e49a7d610_tracking_signals.py` (new), `backend/tools/migrate_legacy.py`.
- Backend tests: `backend/tests/test_tracking.py` (new), `backend/tests/test_migration.py`, `backend/tests/test_workspace.py`.
- Reusable UI: `frontend/src/components/Tracking.jsx` (new), `frontend/src/components/TrackingSettings.jsx` (new), `frontend/src/components/RecipientActivity.jsx` (new), `frontend/src/components/EmailDetail.jsx` (new), `frontend/src/components/Charts.jsx`, `frontend/src/components/Composer.jsx`.
- Pages: `frontend/src/pages/Settings.jsx`, `frontend/src/pages/Analytics.jsx`, `frontend/src/pages/Dashboard.jsx`, `frontend/src/pages/Sent.jsx`, `frontend/src/pages/Campaigns.jsx`.
- Styling and UI verification: `frontend/src/styles/globals.css`, `frontend/tests/browser_smoke.py`.
- Documentation: `README.md`.

Generated outputs are in `frontend/dist/` and `qa/tracking/`. The application database was upgraded in place after a consistent SQLite backup at `backend/data/backups/pre-tracking-20261123T030825Z.db`; all preexisting row values were checked against the backup, allowing only the documented event-kind normalization. SQLite integrity and foreign-key checks passed. The real `.env` and Gmail encryption key were not edited; PUBLIC_BASE_URL remains blank until the developer intentionally starts a tunnel or configures stable hosting.

Verification completed: **46 backend tests passed** on Python 3.13; Ruff and Python compilation passed; ESLint and the Vite production build passed. The browser smoke suite passed account/navigation/theme/refresh checks and audited eight workspace pages in two themes at 1440, 820 and 390 px, plus authentication and dialogs. It also verified tracking defaults, composer inheritance, search, email event/reply details, the sent-replies tab and analytics error recovery. The GIF was independently decoded as 1×1 with transparent alpha. One upstream Starlette TestClient/httpx deprecation warning remains; it did not fail tests. No real emails were sent and no tunnel was started.
