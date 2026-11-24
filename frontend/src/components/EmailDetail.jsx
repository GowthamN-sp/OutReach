import { useEffect, useState } from "react";
import { api } from "../services/api";
import { Modal } from "./UI";
import { Pager, Signal } from "./Tracking";
import { time } from "../utils/format";

function History({ id, type }) {
  const [page, setPage] = useState(0),
    [rows, setRows] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setRows(null);
    setError("");
    api(`/sent/${id}/${type}?offset=${page * 50}&limit=51`, {
      signal: controller.signal,
    })
      .then(setRows)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [id, type, page]);
  return (
    <section className="detail-section">
      <h3>
        {type === "events"
          ? "Timestamped tracking events"
          : "Associated replies"}
      </h3>
      {error ? (
        <p role="alert">{error}</p>
      ) : !rows ? (
        <p role="status">Loading…</p>
      ) : rows.length ? (
        rows.slice(0, 50).map((row) => (
          <div className="activity-event" key={row.id}>
            {type === "events" ? (
              <>
                <strong>
                  {row.kind === "open_signal" ? "Open signal" : "Click signal"}
                </strong>
                <time>{time(row.occurred)}</time>
              </>
            ) : (
              <>
                <strong>{row.subject}</strong>
                <small>
                  {row.sender} · {time(row.received_at)}
                </small>
                <pre>{row.body}</pre>
              </>
            )}
          </div>
        ))
      ) : (
        <p className="muted">
          {type === "events"
            ? "No signal observed. Tracking must have been enabled when sent."
            : "No replies found. Sync Inbox to check connected Gmail threads."}
        </p>
      )}
      <Pager
        page={page}
        setPage={setPage}
        more={rows?.length > 50}
        busy={!rows}
      />
    </section>
  );
}

export default function EmailDetail({ id, close, source = "sent" }) {
  const [d, setD] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    api(`/${source}/${id}`, { signal: controller.signal })
      .then(setD)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [id, source]);
  return (
    <Modal title="Email detail" close={close} wide>
      <div className="pad email-detail">
        {error ? (
          <p role="alert">{error}</p>
        ) : !d ? (
          <p role="status">Loading email…</p>
        ) : (
          <>
            <h3>{d.subject || "Historical subject unavailable"}</h3>
            <p>
              {d.name} &lt;{d.email}&gt; · {d.campaign}
            </p>
            <p>
              Gmail status: <strong>{d.status}</strong> · {time(d.sent_at)}
            </p>
            {d.error && <p role="alert">{d.error}</p>}
            <div className="detail-signals">
              <div>
                <strong>
                  Open tracking: {d.tracking_open ? "Enabled at send" : "Off"}
                </strong>
                <Signal
                  enabled={d.tracking_open}
                  first={d.first_open_at}
                  count={d.open_requests}
                />
                <small>Last signal: {time(d.last_open_at)}</small>
              </div>
              <div>
                <strong>
                  Click tracking: {d.tracking_click ? "Enabled at send" : "Off"}
                </strong>
                <Signal
                  enabled={d.tracking_click}
                  first={d.first_click_at}
                  count={d.click_requests}
                />
                <small>Last signal: {time(d.last_click_at)}</small>
              </div>
            </div>
            <h3>Original email body</h3>
            {d.body_available ? (
              <pre className="original-body">{d.body}</pre>
            ) : (
              <p className="muted">
                This older message predates body snapshots. Check Gmail Sent for
                its exact original content.
              </p>
            )}
            {source === "sent" ? (
              <>
                {d.tracking_open || d.tracking_click ? (
                  <History id={id} type="events" />
                ) : (
                  <p className="muted">
                    Not tracked. No tracking was enabled for this message.
                  </p>
                )}
                <History id={id} type="replies" />
              </>
            ) : (
              <p className="muted">
                Dashboard replies are untracked. Associated conversation
                messages are available in Inbox.
              </p>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
