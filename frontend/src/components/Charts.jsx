import {
  Users,
  Send,
  Eye,
  MessageSquareText,
  MousePointerClick,
  Percent,
} from "lucide-react";
import { rate } from "./Tracking";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";
import { fmt } from "../utils/format";
export function Stats({ stats }) {
  let data = [
    {
      name: "Accepted by Gmail",
      value: stats.accepted_total || 0,
      icon: Send,
      accent: "purple",
      note: `${stats.sent} campaign messages · ${stats.accepted_replies || 0} replies sent`,
    },
    {
      name: "Open signals",
      value: stats.open_tracked ? stats.open_signals : "Not tracked",
      icon: Eye,
      accent: "blue",
      note: "Image loads · not confirmed reads",
    },
    {
      name: "Replies",
      value: stats.replies || 0,
      icon: MessageSquareText,
      accent: "green",
      note: "Replies detected in synced threads",
    },
    {
      name: "Click signals",
      value: stats.click_tracked ? stats.click_signals : "Not tracked",
      icon: MousePointerClick,
      accent: "orange",
      note: "Messages with observed link requests",
    },
    {
      name: "Open-signal rate",
      value: rate(stats.open_rate),
      icon: Percent,
      accent: "blue",
      note: `${stats.open_tracked} accepted messages with open tracking`,
    },
    {
      name: "Click-signal rate",
      value: rate(stats.click_rate),
      icon: Percent,
      accent: "orange",
      note: `${stats.click_tracked} accepted messages with click tracking`,
    },
    {
      name: "Reply rate",
      value: stats.reply_rate == null ? "No sends yet" : `${stats.reply_rate}%`,
      icon: MessageSquareText,
      accent: "green",
      note: "Messages with replies / accepted messages",
    },
    {
      name: "Active campaigns",
      value: stats.active_campaigns || 0,
      icon: Users,
      accent: "orange",
      note: "Accepted sends in the last 14 days",
    },
  ];
  return (
    <div className="stat-grid">
      {data.map((d) => (
        <div className="stat-card" key={d.name}>
          <div className="stat-top">
            <span>{d.name}</span>
            <span className={"stat-icon " + d.accent}>
              <d.icon size={19} />
            </span>
          </div>
          <div
            className={
              "stat-number" + (typeof d.value === "string" ? " stat-text" : "")
            }
          >
            {typeof d.value === "number" ? fmt(d.value) : d.value}
          </div>
          <div className="stat-note">{d.note}</div>
        </div>
      ))}
    </div>
  );
}
export function SendChart({ data, signals = false }) {
  return (
    <div className="chart-area">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 15, right: 5, left: -25, bottom: 0 }}
        >
          <defs>
            <linearGradient id="fillSent" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#906eff" stopOpacity=".35" />
              <stop offset="95%" stopColor="#906eff" stopOpacity="0" />
            </linearGradient>
          </defs>
          <CartesianGrid
            vertical={false}
            stroke="var(--border)"
            strokeDasharray="4 5"
          />
          <XAxis
            dataKey="day"
            tickFormatter={(v) => v.slice(5)}
            stroke="var(--muted)"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            dy={12}
          />
          <YAxis
            allowDecimals={false}
            stroke="var(--muted)"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              color: "var(--text)",
            }}
          />
          {signals && <Legend />}
          <Area
            type="monotone"
            dataKey="sent"
            name="Campaign sends"
            stroke="var(--accent)"
            strokeWidth={3}
            fill="url(#fillSent)"
            dot={{ r: 3, strokeWidth: 0, fill: "var(--accent)" }}
          />
          {signals && (
            <Area
              type="monotone"
              name="Open signals"
              dataKey="open_signals"
              stroke="#5bafea"
              fill="transparent"
            />
          )}
          {signals && (
            <Area
              type="monotone"
              name="Click signals"
              dataKey="click_signals"
              stroke="#efaf79"
              fill="transparent"
            />
          )}
          {signals && (
            <Area
              type="monotone"
              name="Replies"
              dataKey="replies"
              stroke="#52cca8"
              fill="transparent"
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
