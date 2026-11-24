import { time } from "../utils/format";

export const rate = (value) => (value == null ? "Not tracked" : `${value}%`);
export function Signal({ enabled, first, count }) {
  return (
    <span className="signal-summary">
      {!enabled ? (
        "Not tracked"
      ) : first ? (
        <>
          {time(first)}
          {count != null && (
            <small>
              {count} observed request{count === 1 ? "" : "s"}
            </small>
          )}
        </>
      ) : (
        "No signal observed"
      )}
    </span>
  );
}
export function TrackingDisclosure() {
  return (
    <p className="privacy-note">
      Open signals record image requests, not proof of reading. Image blocking,
      caching, email-client proxies and automated security scanners affect open
      and click signals. No IP addresses, location or user-agent data are stored
      in tracking events. Only newly sent emails can use tracking.
    </p>
  );
}
export function TrackingChoices({ value, onChange, ready }) {
  return (
    <>
      <div className="option-row">
        <label>
          <input
            type="checkbox"
            checked={value.tracking_open}
            disabled={!ready && !value.tracking_open}
            onChange={(e) =>
              onChange({ ...value, tracking_open: e.target.checked })
            }
          />{" "}
          Open tracking
        </label>
        <label>
          <input
            type="checkbox"
            checked={value.tracking_click}
            disabled={!ready && !value.tracking_click}
            onChange={(e) =>
              onChange({ ...value, tracking_click: e.target.checked })
            }
          />{" "}
          Click tracking
        </label>
      </div>
      {!ready && (
        <p className="notice">
          Tracking is not configured. Set PUBLIC_BASE_URL to a public HTTPS
          origin and restart the backend.
        </p>
      )}
    </>
  );
}
export function Pager({ page, setPage, more, busy = false }) {
  return (
    <div className="actions pagination" aria-label="Pagination">
      <button
        className="btn btn-secondary"
        disabled={busy || page === 0}
        onClick={() => setPage(page - 1)}
      >
        Previous
      </button>
      <span>Page {page + 1}</span>
      <button
        className="btn btn-secondary"
        disabled={busy || !more}
        onClick={() => setPage(page + 1)}
      >
        Next
      </button>
    </div>
  );
}
