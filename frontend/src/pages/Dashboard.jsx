import {
  Users,
  Send,
  Plus,
  ArrowUpRight,
  ChevronDown,
  AlertTriangle,
  TrendingUp,
} from "lucide-react";
import { useEffect, useState } from "react";
import { date } from "../utils/format";
import { Badge, Empty, Head, Btn } from "../components/UI";
import { api } from "../services/api";
import { Stats, SendChart } from "../components/Charts";
import { rate } from "../components/Tracking";
export default function Dashboard({ tick, user, navigate, notify }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setError("");
    api("/analytics")
      .then((data) => {
        if (active) setD(data);
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          notify(e.message, true);
        }
      });
    return () => {
      active = false;
    };
  }, [tick, retry, notify]);
  return (
    <>
      <Head
        eyebrow="YOUR OUTREACH AT A GLANCE"
        title={"Good to see you, " + user.name.split(" ")[0]}
        desc="Manage conversations, follow up thoughtfully, and keep your applications organized."
        action={
          <Btn onClick={() => navigate("campaigns")} icon={Plus}>
            Campaign studio
          </Btn>
        }
      />
      {error ? (
        <div className="panel pad" role="alert">
          {error}{" "}
          <button className="text-link" onClick={() => setRetry(retry + 1)}>
            Retry
          </button>
        </div>
      ) : d ? (
        <>
          <Stats stats={d} />
          <div className="dash-grid">
            <div className="panel chart-panel">
              <div className="panel-header">
                <div>
                  <h3>Sending activity</h3>
                  <p>Outgoing messages · last 14 days</p>
                </div>
                <span className="soft-pill">
                  Last 14 days <ChevronDown size={14} />
                </span>
              </div>
              <SendChart data={d.days} />
            </div>
            <div className="panel insight-panel">
              <div className="panel-header">
                <div>
                  <h3>Outreach health</h3>
                  <p>Signals from your account</p>
                </div>
                <span className="mini-ring">
                  <TrendingUp size={19} />
                </span>
              </div>
              <div className="metric-stack">
                <div>
                  <span>Reply rate</span>
                  <strong>
                    {d.sent ? Math.round((d.replies / d.sent) * 100) : 0}%
                  </strong>
                </div>
                <div className="thin-track">
                  <span
                    style={{
                      width: `${d.sent ? Math.min(100, (d.replies / d.sent) * 100) : 0}%`,
                    }}
                  />
                </div>
                <div>
                  <span>Open-signal rate</span>
                  <strong>{rate(d.open_rate)}</strong>
                </div>
                <div className="thin-track blue">
                  <span
                    style={{
                      width: `${d.open_rate || 0}%`,
                    }}
                  />
                </div>
                <div>
                  <span>Click-signal rate</span>
                  <strong>{rate(d.click_rate)}</strong>
                </div>
              </div>
              <div className="insight-help">
                <AlertTriangle size={16} />
                <span>
                  Open and click signals can be triggered by email security
                  systems.
                </span>
              </div>
            </div>
          </div>
          <div className="panel table-panel">
            <div className="panel-header">
              <div>
                <h3>Recent outreach</h3>
                <p>Latest submissions and Gmail status</p>
              </div>
              <button
                className="text-link"
                onClick={() => navigate("campaigns")}
              >
                View campaigns <ArrowUpRight size={15} />
              </button>
            </div>
            {d.recent.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>RECIPIENT</th>
                      <th>CAMPAIGN</th>
                      <th>DATE</th>
                      <th>STATUS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.recent.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <div className="table-person">
                            <span className="person-avatar">
                              {(r.name || r.email).slice(0, 1).toUpperCase()}
                            </span>
                            <div>
                              <strong>{r.name || r.email}</strong>
                              <small>{r.company || r.email}</small>
                            </div>
                          </div>
                        </td>
                        <td>{r.campaign}</td>
                        <td>{date(r.sent_at)}</td>
                        <td>
                          <Badge
                            tone={r.status === "Sent" ? "success" : "warning"}
                          >
                            {r.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty
                icon={Send}
                title="Your outreach journey starts here"
                desc="Import contacts and create your first campaign to see activity."
                action={
                  <Btn onClick={() => navigate("contacts")} icon={Users}>
                    Add contacts
                  </Btn>
                }
              />
            )}
          </div>
          {d.campaigns.length > 0 && (
            <div className="panel pad">
              <h3>Campaign performance</h3>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Campaign</th>
                      <th>Sent</th>
                      <th>Replied</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.campaigns.map((c) => (
                      <tr key={c.id}>
                        <td>{c.name}</td>
                        <td>{c.sent_count}</td>
                        <td>{c.reply_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="panel pad">Loading analytics…</div>
      )}
    </>
  );
}
