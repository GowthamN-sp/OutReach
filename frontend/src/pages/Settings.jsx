import Profile from "./Profile";
import TrackingSettings from "../components/TrackingSettings";
import {
  Mail,
  LogOut,
  ExternalLink,
  AlertTriangle,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import { Badge, Head, Btn } from "../components/UI";
import { api } from "../services/api";
export default function SettingsPage({
  boot,
  refresh,
  notify,
  user,
  updateUser,
}) {
  const [busy, setBusy] = useState(false);
  async function connect() {
    setBusy(true);
    try {
      let x = await api("/auth/google/start", { method: "POST" });
      location.href = x.url;
    } catch (e) {
      notify(e.message, true);
      setBusy(false);
    }
  }
  async function disconnect() {
    if (!confirm("Disconnect Gmail? Existing local data is retained.")) return;
    try {
      await api("/auth/google/disconnect", { method: "POST" });
      refresh();
      notify("Gmail disconnected");
    } catch (e) {
      notify(e.message, true);
    }
  }
  return (
    <>
      <Head
        eyebrow="WORKSPACE CONFIGURATION"
        title="Account & settings"
        desc="Choose which Gmail account to use, and see how your data is protected."
      />
      <Profile user={user} updateUser={updateUser} notify={notify} />
      <div className="settings-layout">
        <TrackingSettings
          key={`${boot.tracking_open}-${boot.tracking_click}`}
          boot={boot}
          refresh={refresh}
          notify={notify}
        />
        <div className="panel pad">
          <div className="setting-title">
            <div className="setting-icon">
              <Mail size={22} />
            </div>
            <div>
              <h3>Gmail integration</h3>
              <p>Your own mailbox, connected through Google OAuth 2.0</p>
            </div>
          </div>
          <div className="settings-row">
            <div>
              <strong>Connection status</strong>
              <p>{boot.gmail_connected ? boot.gmail_email : "Not connected"}</p>
            </div>
            <Badge tone={boot.gmail_connected ? "success" : "warning"}>
              {boot.gmail_connected ? "Connected" : "Disconnected"}
            </Badge>
          </div>
          <div className="settings-row">
            <div>
              <strong>Access permissions</strong>
              <p>
                Send emails and read existing Gmail threads; no password stored
              </p>
            </div>
          </div>
          <div className="settings-actions">
            {boot.gmail_connected ? (
              <Btn onClick={disconnect} secondary icon={LogOut}>
                Disconnect Gmail
              </Btn>
            ) : (
              <Btn onClick={connect} disabled={busy} icon={Mail}>
                {busy ? "Preparing…" : "Connect Google account"}
              </Btn>
            )}
          </div>
        </div>
        <div className="panel pad">
          <div className="setting-title">
            <div className="setting-icon violet">
              <ShieldCheck size={22} />
            </div>
            <div>
              <h3>Safety & sending</h3>
              <p>Controls built for personal recruiter outreach</p>
            </div>
          </div>
          <div className="settings-row">
            <div>
              <strong>24-hour send limit</strong>
              <p>Prevents accidental large batches</p>
            </div>
            <b>{boot.daily_limit} emails</b>
          </div>
          <div className="settings-row">
            <div>
              <strong>Batch size</strong>
              <p>A maximum of 20 emails per manual send</p>
            </div>
            <b>20</b>
          </div>
          <div className="settings-row">
            <div>
              <strong>Open/click tracking</strong>
              <p>Off by default; needs a public HTTPS endpoint</p>
            </div>
            <Badge tone={boot.tracking_ready ? "success" : "neutral"}>
              {boot.tracking_ready ? "Available" : "Not configured"}
            </Badge>
          </div>
        </div>
        <div className="panel pad settings-wide">
          <h3>Configure Google OAuth</h3>
          <p className="muted">
            Create a Google Cloud OAuth web application, enable Gmail API, and
            add <code>http://localhost:8000/api/auth/google/callback</code> as
            an authorized redirect URI. Put the client ID and secret into the
            backend <code>.env</code> file. You will then be able to connect
            above.
          </p>
          <div className="notice">
            <AlertTriangle size={17} />
            <span>
              Google may require OAuth verification for public apps that request
              access to Gmail messages. For personal development, use a
              configured testing account and comply with Google's policies.
            </span>
          </div>
          <a
            className="text-link"
            href="https://console.cloud.google.com/apis/credentials"
            target="_blank"
            rel="noreferrer"
          >
            Google Cloud Console <ExternalLink size={15} />
          </a>
        </div>
      </div>
    </>
  );
}
