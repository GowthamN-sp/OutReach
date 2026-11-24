import { useEffect, useState } from "react";
import { api } from "../services/api";
export default function ThreadReply({ message, notify, sync, enabled }) {
  const [body, setBody] = useState(""),
    [busy, setBusy] = useState(false),
    [key, setKey] = useState(() => crypto.randomUUID());
  useEffect(() => {
    setBody("");
    setKey(crypto.randomUUID());
  }, [message.gmail_thread_id]);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/inbox/" + message.id + "/reply", {
        method: "POST",
        body: { body, request_id: key },
      });
      setBody("");
      setKey(crypto.randomUUID());
      notify("Gmail accepted your reply");
      await sync();
    } catch (err) {
      notify(err.message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="compose-form thread-detail-foot" onSubmit={submit}>
      <label>
        Reply
        <textarea
          rows={3}
          required
          maxLength={15000}
          value={body}
          onChange={(e) => {
            setBody(e.target.value);
            setKey(crypto.randomUUID());
          }}
        />
      </label>
      <button className="btn" disabled={!enabled || busy || !body.trim()}>
        {busy ? "Sending…" : "Send reply"}
      </button>
    </form>
  );
}
