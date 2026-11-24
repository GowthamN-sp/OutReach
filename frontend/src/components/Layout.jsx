import ThemeToggle from "./ThemeToggle";
import {
  LayoutDashboard,
  Users,
  Send,
  Inbox,
  FileText,
  BarChart3,
  Settings,
  Mail,
  Menu,
  X,
  LogOut,
  RefreshCw,
  ChevronRight,
  MailCheck,
} from "lucide-react";
import { useState } from "react";

import { DemoNotice } from "../components/UI";
const NAV = [
  { id: "dashboard", label: "Overview", icon: LayoutDashboard },
  { id: "contacts", label: "Contacts", icon: Users },
  { id: "campaigns", label: "Campaigns", icon: Send },
  { id: "inbox", label: "Inbox", icon: Inbox },
  { id: "resume", label: "Resume Vault", icon: FileText },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "sent", label: "Sent emails", icon: Mail },
  { id: "settings", label: "Settings", icon: Settings },
];
export default function Layout({
  page,
  go,
  user,
  boot,
  refresh,
  logout,
  toast,
  children,
}) {
  const [open, setOpen] = useState(false);
  const initials = user.name
    .split(/\s+/)
    .slice(0, 2)
    .map((s) => s[0])
    .join("")
    .toUpperCase();
  function navigate(p) {
    go("/" + p);
    setOpen(false);
  }
  return (
    <div className="app-shell">
      <div
        onClick={() => setOpen(false)}
        className={"shade " + (open ? "show" : "")}
      />
      <aside className={"sidebar " + (open ? "open" : "")}>
        <div className="brand">
          <div className="brand-mark">
            <MailCheck size={21} />
          </div>
          <div>
            outreach<span>desk.</span>
            <small>EMAIL INTELLIGENCE</small>
          </div>
          <button
            aria-label="Close navigation"
            className="mobile-close"
            onClick={() => setOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <div className="nav-block">
          <div className="nav-label">WORKSPACE</div>
          {NAV.slice(0, -1).map((n) => (
            <button
              key={n.id}
              title={n.label}
              aria-label={n.label}
              className={"nav-item " + (page === n.id ? "active" : "")}
              onClick={() => navigate(n.id)}
            >
              <n.icon size={18} strokeWidth={1.8} />
              {n.label}
            </button>
          ))}
          <div className="nav-label bottom-label">PREFERENCES</div>
          {NAV.slice(-1).map((n) => (
            <button
              key={n.id}
              title={n.label}
              aria-label={n.label}
              className={"nav-item " + (page === n.id ? "active" : "")}
              onClick={() => navigate(n.id)}
            >
              <n.icon size={18} />
              {n.label}
            </button>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="profile">
            <div className="avatar">{initials}</div>
            <div>
              <b>{user.name}</b>
              <small>{user.email}</small>
            </div>
            <button title="Log out" onClick={logout}>
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <div className="top-left">
            <button
              aria-label="Open navigation"
              className="hamburger"
              onClick={() => setOpen(true)}
            >
              <Menu size={22} />
            </button>
            <span className="breadcrumb">Workspace</span>
            <ChevronRight size={14} />
            <strong>{NAV.find((x) => x.id === page)?.label}</strong>
          </div>
          <div className="top-right">
            <ThemeToggle />
            <span className="top-date">
              {new Date().toLocaleDateString("en-IN", {
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </span>
            <button title="Refresh data" className="icon-btn" onClick={refresh}>
              <RefreshCw size={17} />
            </button>
            <button className="connection" onClick={() => navigate("settings")}>
              <span
                className={
                  "live-dot " + (boot?.gmail_connected ? "connected" : "")
                }
              />
              {boot?.gmail_connected ? "Gmail Connected" : "Connect Gmail"}
            </button>
            <div className="avatar small">{initials}</div>
          </div>
        </header>
        <main className="content">
          <DemoNotice boot={boot} />
          {children}
        </main>
      </div>
      {toast && (
        <div role="status" className={"toast " + (toast.err ? "bad" : "")}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
