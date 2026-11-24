import { useState } from "react";
import { Head } from "../components/UI";
import { allPages, api } from "../services/api";
import { Stats, SendChart } from "../components/Charts";
import { Pager, TrackingDisclosure } from "../components/Tracking";
import RecipientActivity from "../components/RecipientActivity";
import useResource from "../services/useResource";
import ResourceStatus from "../components/ResourceStatus";
import { time } from "../utils/format";

export default function Analytics({ tick }) {
  const [campaign, setCampaign] = useState("");
  const [search, setSearch] = useState(""),
    [page, setPage] = useState(0);
  const campaignList = useResource(
    "campaigns:all",
    () => allPages("/campaigns"),
    [tick],
  );
  const campaigns = campaignList.data || [];
  const report = useResource(
    "analytics:" + campaign,
    () => api("/analytics" + (campaign ? `?campaign_id=${campaign}` : "")),
    [tick],
  );
  const d = report.data;
  const filtered = campaigns.filter((c) =>
    `${c.name} ${c.subject}`.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <Head
        eyebrow="MEASURABLE OUTREACH"
        title="Analytics & insights"
        desc="Gmail acceptance, optional signals and synced replies. Rates count unique messages."
      />
      <ResourceStatus resource={campaignList} label="campaign filters" />
      <div className="panel pad analytics-filter">
        <label>
          Report scope
          <select
            value={campaign}
            onChange={(e) => setCampaign(e.target.value)}
          >
            <option value="">All campaigns</option>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ResourceStatus resource={report} label="analytics" />
      {d ? (
        <>
          <Stats stats={d} />
          <div className="panel chart-panel">
            <div className="panel-header">
              <div>
                <h3>{campaign ? "Campaign activity" : "Outreach over time"}</h3>
                <p>Last 14 days · UTC · unique messages per activity day</p>
              </div>
            </div>
            <SendChart data={d.days} signals />
            <p className="muted">
              A message may have signals on several days. Open and click rates
              use accepted messages with that tracking enabled. Active campaigns
              have an accepted send in the last 14 days.
            </p>
          </div>
          <div className="panel pad campaign-performance">
            <h3>Campaign performance</h3>
            <label>
              Search campaigns
              <input
                type="search"
                value={search}
                placeholder="Campaign name or subject"
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(0);
                }}
              />
            </label>
            {filtered.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Campaign</th>
                      <th>Accepted by Gmail</th>
                      <th>With open signals</th>
                      <th>With click signals</th>
                      <th>With replies</th>
                      <th>Latest activity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.slice(page * 10, page * 10 + 10).map((c) => (
                      <tr key={c.id}>
                        <td>
                          <button
                            className="text-link"
                            onClick={() => setCampaign(String(c.id))}
                          >
                            {c.name}
                          </button>
                        </td>
                        <td>{c.sent_count}</td>
                        <td>{c.open_tracked ? c.open_count : "Not tracked"}</td>
                        <td>
                          {c.click_tracked ? c.click_count : "Not tracked"}
                        </td>
                        <td>{c.reply_count}</td>
                        <td>{time(c.latest_activity)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : campaignList.data !== undefined &&
              !campaignList.error &&
              !campaignList.loading ? (
              <p className="muted">
                No matching campaigns. Create a campaign to begin.
              </p>
            ) : null}
            <Pager
              page={page}
              setPage={setPage}
              more={filtered.length > (page + 1) * 10}
            />
          </div>
          <RecipientActivity key={campaign} tick={tick} campaignId={campaign} />
          <TrackingDisclosure />
        </>
      ) : null}
    </>
  );
}
