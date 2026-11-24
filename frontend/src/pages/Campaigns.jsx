import Composer from "../components/Composer";
import CampaignReview from "../components/CampaignReview";
import ResourceStatus from "../components/ResourceStatus";
import { Signal } from "../components/Tracking";
import {
  Send,
  Plus,
  Search,
  Mail,
  MessageSquareText,
  Paperclip,
  ArrowLeft,
} from "lucide-react";
import { useState } from "react";
import { date, time } from "../utils/format";
import { Badge, Empty, Head, Btn, Modal } from "../components/UI";
import { allPages, api } from "../services/api";
import useResource from "../services/useResource";
import { attachmentWarning } from "../utils/campaign";

export default function Campaigns({ tick, refresh, notify, boot }) {
  const [view, setView] = useState("active"),
    [active, setActive] = useState(null);
  const [selected, setSelected] = useState([]),
    [search, setSearch] = useState("");
  const [batch, setBatch] = useState(""),
    [showSelected, setShowSelected] = useState(false),
    [excludeTest, setExcludeTest] = useState(false);
  const [newOpen, setNewOpen] = useState(false),
    [review, setReview] = useState(false),
    [busy, setBusy] = useState(false);
  const [action, setAction] = useState(null),
    [actionError, setActionError] = useState(null),
    [feedback, setFeedback] = useState("");
  const list = useResource(
    "campaigns:" + view,
    () => allPages("/campaigns?view=" + view),
    [tick],
  );
  const contactList = useResource("contacts", () => allPages("/contacts"), [
    tick,
  ]);
  const resumeList = useResource("resumes", () => api("/resumes"), [tick]);
  const templateList = useResource("templates", () => api("/templates"), [
    tick,
  ]);
  const history = useResource(
    "deliveries:" + (active?.id || "none"),
    () =>
      active
        ? allPages(`/campaigns/${active.id}/deliveries`)
        : Promise.resolve([]),
    [tick],
  );
  const items = list.data || [],
    contacts = contactList.data || [],
    resumes = resumeList.data || [],
    deliveries = history.data || [];
  const current = active
    ? items.find((c) => c.id === active.id) || active
    : null;
  const already = new Set(
    deliveries.filter((d) => d.status !== "Failed").map((d) => d.contact_id),
  );
  const possible = contacts.filter(
    (c) =>
      (!showSelected || selected.includes(c.id)) &&
      (!batch || c.source === batch) &&
      (!excludeTest || !/\btest\b/i.test(c.source)) &&
      `${c.name} ${c.email} ${c.company} ${c.role}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  function selectCampaign(c) {
    setActive(c);
    setSelected([]);
    setSearch("");
    setBatch("");
    setShowSelected(false);
    setActionError(null);
  }
  async function mutate() {
    const { campaign, kind } = action;
    setBusy(true);
    setActionError(null);
    try {
      await api(
        `/campaigns/${campaign.id}${kind === "delete" ? "" : "/" + kind}`,
        { method: kind === "delete" ? "DELETE" : "POST" },
      );
      setFeedback(
        `${campaign.name}: ${kind === "delete" ? "draft deleted. Restore it from Deleted drafts." : kind === "archive" ? "campaign archived. History is preserved." : "campaign restored."}`,
      );
      setAction(null);
      if (active?.id === campaign.id) {
        setActive(null);
        setReview(false);
        setSelected([]);
      }
      await list.load();
      refresh();
    } catch (e) {
      setActionError({ id: campaign.id, message: e.message });
      setAction(null);
      list.load();
      history.load();
    } finally {
      setBusy(false);
    }
  }
  function actions(c) {
    return (
      <details className="campaign-actions">
        <summary>
          Actions<span className="sr-only"> for {c.name}</span>
        </summary>
        <div className="action-menu">
          {c.archived_at || c.deleted_at ? (
            <Btn
              secondary
              disabled={busy}
              onClick={() => setAction({ campaign: c, kind: "restore" })}
            >
              Restore
            </Btn>
          ) : (
            <>
              {!c.delivery_count && (
                <Btn
                  secondary
                  disabled={busy}
                  onClick={() => setAction({ campaign: c, kind: "delete" })}
                >
                  Delete draft
                </Btn>
              )}
              <Btn
                secondary
                disabled={busy}
                onClick={() => setAction({ campaign: c, kind: "archive" })}
              >
                Archive campaign
              </Btn>
            </>
          )}
        </div>
      </details>
    );
  }
  async function send() {
    setBusy(true);
    try {
      const result = await api("/send", {
        method: "POST",
        body: { campaign_id: active.id, contact_ids: selected, confirm: true },
      });
      notify(
        `${result.sent} email(s) sent; ${result.results.length - result.sent} skipped or failed`,
      );
      setReview(false);
      setSelected([]);
      history.load();
      list.load();
      refresh();
    } catch (e) {
      setActionError({ id: active.id, message: e.message });
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Head
        eyebrow="PERSONALIZED OUTREACH"
        title="Campaign studio"
        desc="Write once, personalize carefully, and send with your connected Gmail."
        action={
          <Btn
            icon={Plus}
            disabled={
              resumeList.data === undefined || templateList.data === undefined
            }
            onClick={() => setNewOpen(true)}
          >
            Create campaign
          </Btn>
        }
      />
      <ResourceStatus resource={list} label="campaigns" />
      <ResourceStatus resource={resumeList} label="resumes" />
      <ResourceStatus resource={templateList} label="templates" />
      {feedback && (
        <p className="notice" role="status">
          {feedback}
        </p>
      )}
      {active ? (
        <>
          <div className="back-row">
            <button
              className="text-link"
              onClick={() => {
                setActive(null);
                setActionError(null);
              }}
            >
              <ArrowLeft size={16} /> All campaigns
            </button>
            <Badge>{current.name}</Badge>
            {actions(current)}
          </div>
          {actionError?.id === active.id && (
            <p className="notice" role="alert">
              {actionError.message}
            </p>
          )}
          <div className="two-col">
            <div className="panel pad">
              <div className="panel-header">
                <div>
                  <h3>Message preview</h3>
                  <p>Variables are replaced per contact</p>
                </div>
              </div>
              <div className="email-preview">
                <div className="mail-meta">
                  <span>SUBJECT</span>
                  <strong>{current.subject}</strong>
                </div>
                <pre>{current.body}</pre>
                {current.resume_id && (
                  <span className="attachment">
                    <Paperclip size={15} />
                    {resumes.find((r) => r.id === current.resume_id)
                      ?.filename || "Resume selected"}
                  </span>
                )}
              </div>
              {attachmentWarning(current.body, current.resume_id) && (
                <p className="notice">
                  Your message says a resume is attached, but no file is
                  selected.
                </p>
              )}
              <p className="muted">
                {current.tracking_open
                  ? "Open signals on"
                  : "Open tracking off"}{" "}
                ·{" "}
                {current.tracking_click
                  ? "Click signals on"
                  : "Click tracking off"}
              </p>
            </div>
            <div className="panel pad">
              <div className="panel-header">
                <div>
                  <h3>Choose recipients</h3>
                  <p>Up to 20 contacts per batch</p>
                </div>
                <Badge>{selected.length} of 20 selected</Badge>
              </div>
              {current.archived_at || current.deleted_at ? (
                <p>Restore this campaign to select recipients and send.</p>
              ) : (
                <>
                  <ResourceStatus resource={contactList} label="contacts" />
                  <div className="actions selection-tools">
                    <label>
                      <input
                        type="checkbox"
                        checked={showSelected}
                        onChange={(e) => setShowSelected(e.target.checked)}
                      />{" "}
                      Show selected
                    </label>
                    <Btn
                      secondary
                      disabled={!selected.length}
                      onClick={() => setSelected([])}
                    >
                      Clear selection
                    </Btn>
                  </div>
                  <div className="search-wrap full">
                    <Search size={16} />
                    <input
                      aria-label="Filter recipients"
                      placeholder="Filter contacts..."
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </div>
                  <label>
                    Import batch
                    <select
                      aria-label="Import batch"
                      value={batch}
                      onChange={(e) => setBatch(e.target.value)}
                    >
                      <option value="">All sources / import batches</option>
                      {[...new Set(contacts.map((c) => c.source))].map(
                        (source) => (
                          <option key={source}>{source}</option>
                        ),
                      )}
                    </select>
                  </label>
                  <label className="option-row">
                    <input
                      type="checkbox"
                      checked={excludeTest}
                      onChange={(e) => setExcludeTest(e.target.checked)}
                    />{" "}
                    Exclude contacts marked Test in source
                  </label>
                  <div className="recipient-list">
                    {possible.map((c) => (
                      <label key={c.id} className="recipient-row">
                        <input
                          type="checkbox"
                          checked={selected.includes(c.id)}
                          disabled={
                            already.has(c.id) ||
                            history.data === undefined ||
                            history.loading ||
                            !!history.error ||
                            (!selected.includes(c.id) && selected.length >= 20)
                          }
                          onChange={() =>
                            setSelected((previous) =>
                              previous.includes(c.id)
                                ? previous.filter((id) => id !== c.id)
                                : [...previous, c.id],
                            )
                          }
                        />
                        <span className="person-avatar">
                          {(c.name || c.email)[0].toUpperCase()}
                        </span>
                        <span>
                          <strong>{c.name || c.email}</strong>
                          <small>{c.email}</small>
                          {already.has(c.id) && (
                            <small>
                              Already sent / awaiting reconciliation
                            </small>
                          )}
                        </span>
                      </label>
                    ))}
                    {!possible.length &&
                      contactList.data !== undefined &&
                      !contactList.loading &&
                      !contactList.error && (
                        <p className="muted">
                          No matching contacts. Adjust filters or add contacts.
                        </p>
                      )}
                  </div>
                  <Btn
                    icon={Send}
                    disabled={
                      busy ||
                      !selected.length ||
                      history.loading ||
                      !!history.error
                    }
                    onClick={() => setReview(true)}
                  >{`Review & send to ${selected.length} contact(s)`}</Btn>
                  <p className="privacy-note">
                    Preview each recipient and confirm before sending. No
                    automatic follow-ups.
                  </p>
                </>
              )}
            </div>
          </div>
          <div className="panel table-panel">
            <div className="panel-header pad-head">
              <h3>Campaign delivery history</h3>
              <span className="results">{deliveries.length} records</span>
            </div>
            <ResourceStatus
              resource={history}
              label="campaign delivery history"
            />
            {deliveries.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>CONTACT</th>
                      <th>SENT</th>
                      <th>STATUS</th>
                      <th>OPEN SIGNAL</th>
                      <th>CLICK SIGNAL</th>
                      <th>REPLIES</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deliveries.map((d) => (
                      <tr key={d.id}>
                        <td>
                          <strong>{d.name || d.email}</strong>
                          <br />
                          <small>{d.email}</small>
                        </td>
                        <td>{time(d.sent_at)}</td>
                        <td>
                          <Badge
                            tone={d.status === "Sent" ? "success" : "warning"}
                          >
                            {d.status}
                          </Badge>
                          {d.error && <small>{d.error}</small>}
                        </td>
                        <td>
                          <Signal
                            enabled={d.tracking_open}
                            first={d.first_open_at}
                            count={d.opens}
                          />
                        </td>
                        <td>
                          <Signal
                            enabled={d.tracking_click}
                            first={d.first_click_at}
                            count={d.clicks}
                          />
                        </td>
                        <td>{d.replies}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : history.data !== undefined &&
              !history.error &&
              !history.loading ? (
              <Empty
                title="No messages sent yet"
                desc="Choose recipients above to begin your first campaign."
                icon={Send}
              />
            ) : null}
          </div>
        </>
      ) : (
        <>
          <div className="actions campaign-views" aria-label="Campaign views">
            {[
              ["active", "All campaigns"],
              ["archived", "Archived"],
              ["deleted", "Deleted drafts"],
            ].map(([value, label]) => (
              <button
                key={value}
                className="btn btn-secondary"
                aria-pressed={view === value}
                onClick={() => {
                  setView(value);
                  setActionError(null);
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="campaign-grid">
            {items.map((c) => (
              <article key={c.id} className="campaign-card">
                <div className="campaign-top">
                  <span className="campaign-icon">
                    <Mail size={20} />
                  </span>
                  {actions(c)}
                </div>
                <button
                  className="campaign-open"
                  onClick={() => selectCampaign(c)}
                >
                  <h3>{c.name}</h3>
                  <p>{c.subject}</p>
                  <div className="campaign-metrics">
                    <span>
                      <Send size={14} />
                      {c.sent_count} sent
                    </span>
                    <span>
                      <MessageSquareText size={14} />
                      {c.reply_count} replied
                    </span>
                  </div>
                  <div className="campaign-footer">
                    Created {date(c.created_at)}
                  </div>
                </button>
                {actionError?.id === c.id && (
                  <p role="alert">{actionError.message}</p>
                )}
              </article>
            ))}
            {!items.length &&
              list.data !== undefined &&
              !list.loading &&
              !list.error && (
                <div className="panel full-grid">
                  <Empty
                    icon={Mail}
                    title={
                      view === "active"
                        ? "Your first campaign awaits"
                        : view === "archived"
                          ? "No archived campaigns"
                          : "No deleted drafts"
                    }
                    desc={
                      view === "active"
                        ? "Create a thoughtful introduction, pick contacts, and send using Gmail."
                        : "Removed campaigns will appear here and can be restored."
                    }
                  />
                </div>
              )}
          </div>
        </>
      )}
      {action && (
        <Modal
          title={`${action.kind === "delete" ? "Delete draft" : action.kind === "archive" ? "Archive campaign" : "Restore campaign"}: ${action.campaign.name}`}
          close={busy ? () => {} : () => setAction(null)}
        >
          <p>
            {action.kind === "delete"
              ? `Delete draft "${action.campaign.name}"? You can restore it from Deleted drafts, including after signing in again.`
              : action.kind === "archive"
                ? `Archive "${action.campaign.name}"? Delivery records, tracking events and replies will be preserved.`
                : `Restore "${action.campaign.name}" to All campaigns?`}
          </p>
          <div className="modal-actions">
            <Btn secondary disabled={busy} onClick={() => setAction(null)}>
              Cancel
            </Btn>
            <Btn disabled={busy} onClick={mutate}>
              {busy
                ? "Saving..."
                : action.kind === "delete"
                  ? "Delete draft"
                  : action.kind === "archive"
                    ? "Archive campaign"
                    : "Restore"}
            </Btn>
          </div>
        </Modal>
      )}
      {newOpen && (
        <Composer
          close={() => setNewOpen(false)}
          templates={templateList.data || []}
          setTemplates={() => templateList.load()}
          resumes={resumes}
          boot={boot}
          refresh={() => {
            list.load();
            refresh();
          }}
          notify={notify}
        />
      )}
      {review && active && (
        <CampaignReview
          campaign={current}
          selected={selected}
          contacts={contacts}
          remove={(id) => {
            setSelected((previous) => previous.filter((value) => value !== id));
            if (selected.length === 1) setReview(false);
          }}
          close={() => setReview(false)}
          send={send}
          busy={busy}
          contactsChanged={contactList.load}
          gmail={boot.gmail_connected ? boot.gmail_email : null}
          sendError={actionError?.id === active.id ? actionError.message : ""}
        />
      )}
    </>
  );
}
