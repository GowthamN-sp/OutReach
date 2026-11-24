import Composer from "../components/Composer";
import { Signal } from "../components/Tracking";
import {
  Send,
  Plus,
  Search,
  ArrowUpRight,
  Mail,
  MessageSquareText,
  Paperclip,
  ArrowRight,
  ArrowLeft,
  Loader2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { date, time } from "../utils/format";
import { Badge, Empty, Head, Btn } from "../components/UI";
import { allPages, api } from "../services/api";
export default function Campaigns({ tick, refresh, notify, boot }) {
  const [items, setItems] = useState([]),
    [contacts, setContacts] = useState([]),
    [newOpen, setNewOpen] = useState(false),
    [active, setActive] = useState(null),
    [selected, setSelected] = useState([]),
    [deliveries, setDeliveries] = useState([]),
    [busy, setBusy] = useState(false),
    [search, setSearch] = useState("");
  const [templates, setTemplates] = useState([]),
    [resumes, setResumes] = useState([]);
  const historyRequest = useRef(0);
  const load = async () => {
    try {
      setItems(await allPages("/campaigns"));
      setTemplates(await api("/templates"));
      setResumes(await api("/resumes"));
      setContacts(await allPages("/contacts"));
    } catch (e) {
      notify(e.message, true);
    }
  };
  useEffect(() => {
    load();
  }, [tick]);
  async function selectCampaign(c) {
    setActive(c);
    setSelected([]);
    setSearch("");
    const request = ++historyRequest.current;
    setDeliveries([]);
    try {
      const rows = await allPages("/campaigns/" + c.id + "/deliveries");
      if (request === historyRequest.current) setDeliveries(rows);
    } catch (e) {
      notify(e.message, true);
    }
  }
  async function send() {
    if (!boot.gmail_connected) {
      notify("Connect your Gmail account in Settings first", true);
      return;
    }
    if (!selected.length) return;
    if (
      !confirm(
        `Send “${active.subject}” from ${boot.gmail_email} as separate messages to:\n${contacts
          .filter((c) => selected.includes(c.id))
          .map((c) => c.email)
          .join("\n")}`,
      )
    )
      return;
    setBusy(true);
    try {
      let r = await api("/send", {
        method: "POST",
        body: { campaign_id: active.id, contact_ids: selected, confirm: true },
      });
      notify(
        `${r.sent} email(s) sent; ${r.results.length - r.sent} skipped or failed`,
      );
      selectCampaign(active);
      load();
      refresh();
    } catch (e) {
      notify(e.message, true);
    } finally {
      setBusy(false);
    }
  }
  const already = new Set(
    deliveries.filter((x) => x.status !== "Failed").map((x) => x.contact_id),
  );
  const possible = contacts.filter(
    (x) =>
      !already.has(x.id) &&
      `${x.name} ${x.email} ${x.company}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <Head
        eyebrow="PERSONALIZED OUTREACH"
        title="Campaign studio"
        desc="Write once, personalize carefully, and send with your connected Gmail."
        action={
          <Btn
            icon={Plus}
            onClick={() => {
              setNewOpen(true);
            }}
          >
            Create campaign
          </Btn>
        }
      />
      {active ? (
        <>
          <div className="back-row">
            <button className="text-link" onClick={() => setActive(null)}>
              <ArrowLeft size={16} /> All campaigns
            </button>
            <Badge>{active.name}</Badge>
          </div>
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
                  <strong>{active.subject}</strong>
                </div>
                <pre>{active.body}</pre>
                {!!active.attach_resume && (
                  <span className="attachment">
                    <Paperclip size={15} />{" "}
                    {resumes.find((r) => r.id === active.resume_id)?.name ||
                      "PDF attached"}
                  </span>
                )}
              </div>
              <div className="toggle-line muted">
                {active.tracking_open ? "Open signals on" : "Open tracking off"}{" "}
                ·{" "}
                {active.tracking_click
                  ? "Click signals on"
                  : "Click tracking off"}
              </div>
            </div>
            <div className="panel pad">
              <div className="panel-header">
                <div>
                  <h3>Choose recipients</h3>
                  <p>Up to 20 contacts per batch</p>
                </div>
                <Badge tone={selected.length ? "info" : "neutral"}>
                  {selected.length} selected
                </Badge>
              </div>
              <div className="search-wrap full">
                <Search size={16} />
                <input
                  placeholder="Filter contacts..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="recipient-list">
                {possible.length ? (
                  possible.map((c) => (
                    <label key={c.id} className="recipient-row">
                      <input
                        type="checkbox"
                        checked={selected.includes(c.id)}
                        disabled={
                          !selected.includes(c.id) && selected.length >= 20
                        }
                        onChange={() =>
                          setSelected((p) =>
                            p.includes(c.id)
                              ? p.filter((x) => x !== c.id)
                              : [...p, c.id],
                          )
                        }
                      />
                      <span className="person-avatar">
                        {(c.name || c.email)[0].toUpperCase()}
                      </span>
                      <span>
                        <strong>{c.name || c.email}</strong>
                        <small>{c.email}</small>
                      </span>
                    </label>
                  ))
                ) : (
                  <p className="muted">
                    No unsent matching contacts. Add contacts first.
                  </p>
                )}
              </div>
              <Btn
                icon={busy ? Loader2 : Send}
                disabled={busy || !selected.length}
                onClick={send}
              >
                {busy
                  ? "Sending…"
                  : `Review & send to ${selected.length} contact(s)`}
              </Btn>
              <p className="privacy-note">
                You will be asked to confirm before sending. No automatic
                follow-ups.
              </p>
            </div>
          </div>
          <div className="panel table-panel">
            <div className="panel-header pad-head">
              <h3>Campaign delivery history</h3>
              <span className="results">{deliveries.length} records</span>
            </div>
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
            ) : (
              <Empty
                title="No messages sent yet"
                desc="Choose recipients above to begin your first campaign."
                icon={Send}
              />
            )}
          </div>
        </>
      ) : (
        <div className="campaign-grid">
          {items.map((c) => (
            <button
              key={c.id}
              className="campaign-card"
              onClick={() => selectCampaign(c)}
            >
              <div className="campaign-top">
                <span className="campaign-icon">
                  <Mail size={20} />
                </span>
                <span className="circle-arrow">
                  <ArrowUpRight size={18} />
                </span>
              </div>
              <h3>{c.name}</h3>
              <p>{c.subject}</p>
              <div className="campaign-metrics">
                <span>
                  <Send size={14} /> {c.sent_count} sent
                </span>
                <span>
                  <MessageSquareText size={14} /> {c.reply_count} replied
                </span>
              </div>
              <div className="campaign-footer">
                Created {date(c.created_at)} <ArrowRight size={15} />
              </div>
            </button>
          ))}
          {!items.length && (
            <div className="panel full-grid">
              <Empty
                icon={Mail}
                title="Your first campaign awaits"
                desc="Create a thoughtful introduction, pick contacts, and send using Gmail."
                action={
                  <Btn
                    icon={Plus}
                    onClick={() => {
                      setNewOpen(true);
                    }}
                  >
                    Create a campaign
                  </Btn>
                }
              />
            </div>
          )}
        </div>
      )}
      {newOpen && (
        <Composer
          close={() => setNewOpen(false)}
          templates={templates}
          setTemplates={setTemplates}
          resumes={resumes}
          boot={boot}
          refresh={refresh}
          notify={notify}
        />
      )}
    </>
  );
}
