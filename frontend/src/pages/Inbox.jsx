import ThreadReply from "../components/ThreadReply";
import { Inbox, MessageSquareText, RefreshCw } from "lucide-react";
import { useState } from "react";
import useResource from "../services/useResource";
import ResourceStatus from "../components/ResourceStatus";
import { date, time } from "../utils/format";
import { Badge, Empty, Head, Btn } from "../components/UI";
import { allPages, api } from "../services/api";
export default function InboxPage({ tick, notify, boot }) {
  const [active, setActive] = useState(null),
    [busy, setBusy] = useState(false);
  const [syncError, setSyncError] = useState("");
  const syncStatus = useResource(
    "inbox-sync-status",
    () => api("/inbox/sync-status"),
    [tick],
  );
  const resource = useResource("inbox", () => allPages("/inbox"), [tick]);
  const items = resource.data || [];
  async function sync() {
    setBusy(true);
    setSyncError("");
    try {
      let x = await api("/inbox/sync", { method: "POST" });
      resource.load();
      notify(`Synced ${x.threads_checked} threads · ${x.added} new messages`);
    } catch (e) {
      setSyncError(e.message);
      notify(e.message, true);
    } finally {
      setBusy(false);
      syncStatus.load();
    }
  }
  let tids = [
    ...new Set(items.map((x) => x.mailbox + "/" + x.gmail_thread_id)),
  ];
  let threads = tids.map((id) => ({
    id,
    messages: items.filter((m) => m.mailbox + "/" + m.gmail_thread_id === id),
  }));
  threads.sort(
    (a, b) =>
      new Date(b.messages[0].received_at) - new Date(a.messages[0].received_at),
  );
  const chosen = threads.find((x) => x.id === active) || threads[0];
  return (
    <>
      <Head
        eyebrow="CONVERSATION HUB"
        title="Gmail conversations"
        desc="Read replies to messages sent through OutreachDesk, in one organized view."
        action={
          <Btn
            icon={RefreshCw}
            disabled={busy || !boot.gmail_connected}
            onClick={sync}
          >
            {busy ? "Syncing…" : "Sync Gmail replies"}
          </Btn>
        }
      />
      <div className="panel pad" aria-label="Gmail sync status">
        <p>
          Gmail connection:{" "}
          {boot.gmail_connected
            ? `Connected (${boot.gmail_email})`
            : "Disconnected"}
        </p>
        <ResourceStatus resource={syncStatus} label="latest sync status" />
        <p
          role={
            syncError || syncStatus.data?.status === "failed"
              ? "alert"
              : "status"
          }
        >
          {busy
            ? "Syncing Gmail..."
            : syncError
              ? `Last sync failed: ${syncError}`
              : syncStatus.data
                ? `Last sync ${syncStatus.data.status} at ${time(syncStatus.data.occurred)}: ${syncStatus.data.detail}`
                : syncStatus.data === null
                  ? "No Gmail sync has been recorded."
                  : ""}
        </p>
        {(syncError || syncStatus.data?.status === "failed") && (
          <Btn
            secondary
            disabled={busy || !boot.gmail_connected}
            onClick={sync}
          >
            Retry sync
          </Btn>
        )}
      </div>
      <ResourceStatus resource={resource} label="conversations" />
      <div className="inbox-layout">
        <div className="panel thread-list">
          <div className="inbox-search">
            <span>
              <Inbox size={17} /> Conversations
            </span>
            <Badge>{threads.length}</Badge>
          </div>
          {threads.length ? (
            threads.map((t) => {
              let m = t.messages[0];
              return (
                <button
                  className={
                    "thread " + (chosen?.id === t.id ? "selected" : "")
                  }
                  key={t.id}
                  onClick={() => setActive(t.id)}
                >
                  <div className="person-avatar">
                    {(m.contact_name || m.sender || "?")[0].toUpperCase()}
                  </div>
                  <div>
                    <div className="thread-line">
                      <strong>
                        {m.contact_name || m.sender || "Unknown contact"}
                      </strong>
                      <small>{date(m.received_at)}</small>
                    </div>
                    <b>{m.subject || "(no subject)"}</b>
                    <p>{(m.body || "No plain-text preview").slice(0, 110)}</p>
                    <Badge
                      tone={
                        t.messages.some((x) => x.direction === "inbound")
                          ? "success"
                          : "neutral"
                      }
                    >
                      {t.messages.some((x) => x.direction === "inbound")
                        ? "Reply received"
                        : "Sent"}
                    </Badge>
                  </div>
                </button>
              );
            })
          ) : resource.data !== undefined &&
            !resource.error &&
            !resource.loading ? (
            <Empty
              icon={Inbox}
              title="No synced threads"
              desc="Send a campaign, then use Sync Gmail replies to import conversations."
            />
          ) : null}
        </div>
        <div className="panel thread-detail">
          {chosen ? (
            <>
              <div className="thread-detail-head">
                <div>
                  <h3>{chosen.messages[0].subject}</h3>
                  <p>
                    {chosen.messages[0].contact_name ||
                      chosen.messages[0].sender}
                  </p>
                </div>
                <Badge>{chosen.messages.length} messages</Badge>
              </div>
              <div className="message-stack">
                {[...chosen.messages].reverse().map((m) => (
                  <article
                    key={m.id}
                    className={"message-bubble " + m.direction}
                  >
                    <div className="message-top">
                      <strong>
                        {m.direction === "outbound"
                          ? "You"
                          : m.direction === "inbound"
                            ? "Recruiter reply"
                            : "Participant"}
                      </strong>
                      <small>{time(m.received_at)}</small>
                    </div>
                    <p className="message-from">{m.sender}</p>
                    <pre>
                      {m.body ||
                        "Plain-text body unavailable; open the original in Gmail."}
                    </pre>
                  </article>
                ))}
              </div>
              <a
                className="text-link pad-head"
                target="_blank"
                rel="noreferrer"
                href={
                  "https://mail.google.com/mail/?authuser=" +
                  encodeURIComponent(chosen.messages[0].mailbox) +
                  "#all/" +
                  encodeURIComponent(chosen.messages[0].gmail_thread_id)
                }
              >
                Open in Gmail
              </a>
              <ThreadReply
                key={chosen.id}
                message={chosen.messages[0]}
                enabled={boot.gmail_email === chosen.messages[0].mailbox}
                notify={notify}
                sync={sync}
              />
            </>
          ) : resource.data !== undefined &&
            !resource.error &&
            !resource.loading ? (
            <Empty
              icon={MessageSquareText}
              title="All your conversations in one place"
              desc="Once you send messages and sync Gmail, responses will appear here."
            />
          ) : null}
        </div>
      </div>
    </>
  );
}
