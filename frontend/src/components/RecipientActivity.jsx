import { useEffect, useState } from "react";
import { allPages, api } from "../services/api";
import { Badge, Empty } from "./UI";
import { Pager, Signal } from "./Tracking";
import EmailDetail from "./EmailDetail";
import { time } from "../utils/format";

export default function RecipientActivity({
  tick,
  campaignId = "",
  title = "Recipient activity",
  source = "sent",
}) {
  const [rows, setRows] = useState(null),
    [error, setError] = useState("");
  const [filters, setFilters] = useState({
    search: "",
    status: "",
    signal: "",
    campaign_id: "",
  });
  const [page, setPage] = useState(0),
    [retry, setRetry] = useState(0);
  const [campaigns, setCampaigns] = useState([]),
    [selected, setSelected] = useState(null);
  useEffect(() => {
    let active = true;
    allPages("/campaigns")
      .then((r) => {
        if (active) setCampaigns(r);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [tick]);
  useEffect(() => {
    const controller = new AbortController();
    setRows(null);
    setError("");
    const query = new URLSearchParams({
      ...filters,
      offset: page * 25,
      limit: 26,
    });
    if (campaignId) query.set("campaign_id", campaignId);
    if (!query.get("campaign_id")) query.delete("campaign_id");
    api(`/${source}?${query}`, { signal: controller.signal })
      .then(setRows)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [filters, page, tick, retry, campaignId, source]);
  function filter(key, value) {
    setFilters({ ...filters, [key]: value });
    setPage(0);
  }
  return (
    <div className="panel pad">
      <h3>{title}</h3>
      <div className="activity-filters">
        <label>
          Search
          <input
            type="search"
            placeholder="Recipient, company or subject"
            value={filters.search}
            onChange={(e) => filter("search", e.target.value)}
          />
        </label>
        {!campaignId && (
          <label>
            Campaign
            <select
              value={filters.campaign_id}
              onChange={(e) => filter("campaign_id", e.target.value)}
            >
              <option value="">All campaigns</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Gmail status
          <select
            value={filters.status}
            onChange={(e) => filter("status", e.target.value)}
          >
            <option value="">All statuses</option>
            {["Sent", "Failed", "Unconfirmed", "Preparing"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Activity
          <select
            disabled={source !== "sent"}
            value={filters.signal}
            onChange={(e) => filter("signal", e.target.value)}
          >
            <option value="">All activity</option>
            <option value="open">Open signal</option>
            <option value="click">Click signal</option>
            <option value="reply">Reply received</option>
            <option value="untracked">Not tracked</option>
          </select>
        </label>
      </div>
      {error ? (
        <div role="alert">
          {error}{" "}
          <button className="text-link" onClick={() => setRetry(retry + 1)}>
            Retry
          </button>
        </div>
      ) : !rows ? (
        <p role="status">Loading messages…</p>
      ) : rows.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Recipient</th>
                <th>Campaign / subject</th>
                <th>Gmail status</th>
                <th>First open signal</th>
                <th>First click signal</th>
                <th>Reply status</th>
                <th>Last activity</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 25).map((r) => (
                <tr key={r.id}>
                  <td>
                    <button
                      className="text-link"
                      onClick={() => setSelected(r.id)}
                    >
                      {r.name || r.email}
                    </button>
                    <small>{r.email}</small>
                    <small>{r.company}</small>
                  </td>
                  <td>
                    {r.campaign}
                    <small>
                      {r.subject || "Historical subject unavailable"}
                    </small>
                  </td>
                  <td>
                    <Badge tone={r.status === "Sent" ? "success" : "warning"}>
                      {r.status}
                    </Badge>
                    {r.error && <small>{r.error}</small>}
                  </td>
                  <td>
                    <Signal enabled={r.tracking_open} first={r.first_open_at} />
                  </td>
                  <td>
                    <Signal
                      enabled={r.tracking_click}
                      first={r.first_click_at}
                    />
                  </td>
                  <td>
                    {source === "sent"
                      ? r.replies
                        ? `${r.replies} received`
                        : "No reply found"
                      : "See Inbox thread"}
                  </td>
                  <td>{time(r.last_activity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          title="No matching messages"
          desc="Send history and observed signals will appear here. Adjust your filters or send a reviewed campaign."
        />
      )}
      <Pager
        page={page}
        setPage={setPage}
        more={rows?.length > 25}
        busy={!rows}
      />
      {selected && (
        <EmailDetail
          key={selected}
          id={selected}
          source={source}
          close={() => setSelected(null)}
        />
      )}
    </div>
  );
}
