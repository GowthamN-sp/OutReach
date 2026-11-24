import { useState } from "react";
import { api } from "../services/api";
import { Btn } from "./UI";
import { TrackingChoices, TrackingDisclosure } from "./Tracking";

export default function TrackingSettings({ boot, refresh, notify }) {
  const [value, setValue] = useState({
    tracking_open: !!boot.tracking_open,
    tracking_click: !!boot.tracking_click,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/settings/tracking", { method: "PUT", body: value });
      refresh();
      notify("Tracking defaults saved for new campaigns");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="panel pad settings-wide" onSubmit={save}>
      <h3>Optional tracking defaults</h3>
      <p className="muted">
        Off by default. Choose independent defaults for new campaigns, then
        review them in the composer. Existing campaigns and sent messages keep
        their original choices.
      </p>
      <TrackingChoices
        value={value}
        onChange={setValue}
        ready={boot.tracking_ready}
      />
      <TrackingDisclosure />
      <p className="muted">
        For local testing, intentionally start{" "}
        <code>cloudflared tunnel --url http://localhost:8000</code>, copy its
        HTTPS origin into <code>backend/.env</code> as{" "}
        <code>PUBLIC_BASE_URL</code>, and restart FastAPI. A configured origin
        is not a connectivity test. Temporary tunnels stop working when
        disconnected and are unsuitable for long-running campaigns.
      </p>
      {error && <p role="alert">{error}</p>}
      <Btn type="submit" disabled={busy}>
        {busy ? "Saving…" : "Save tracking defaults"}
      </Btn>
    </form>
  );
}
