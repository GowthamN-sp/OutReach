import { useState } from "react";
import { api } from "../services/api";
import useResource from "../services/useResource";
import { attachmentWarning } from "../utils/campaign";
import ResourceStatus from "./ResourceStatus";
import { Modal, Btn } from "./UI";

export default function CampaignReview({
  campaign,
  selected,
  contacts,
  remove,
  close,
  send,
  busy,
  contactsChanged,
  gmail,
  sendError,
}) {
  const [recipient, setRecipient] = useState(selected[0]);
  const [edits, setEdits] = useState({}),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false);
  const resource = useResource(
    `preview:${campaign.id}:${selected.join(",")}`,
    () =>
      api(`/campaigns/${campaign.id}/preview`, {
        method: "POST",
        body: { campaign_id: campaign.id, contact_ids: selected },
      }),
  );
  const rows = resource.data?.recipients || [];
  const chosen = rows.find((row) => row.contact_id === recipient) || rows[0];
  const blocked = rows.some((row) => row.missing.length || row.already_sent);
  async function fix(row) {
    setSaving(true);
    setError("");
    try {
      const contact = contacts.find((c) => c.id === row.contact_id);
      await api(`/contacts/${row.contact_id}`, {
        method: "PUT",
        body: { ...contact, ...edits[row.contact_id] },
      });
      contactsChanged();
      await resource.load();
      setEdits((previous) => {
        const next = { ...previous };
        delete next[row.contact_id];
        return next;
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <Modal
      title="Review campaign recipients"
      close={busy || saving ? () => {} : close}
      wide
    >
      <p>
        From {gmail || "Gmail is disconnected"} · {selected.length} separate
        message{selected.length === 1 ? "" : "s"} · {campaign.name}
      </p>
      <ResourceStatus resource={resource} label="recipient previews" />
      <p>
        Resume filename:{" "}
        <strong>{resource.data?.resume_filename || "No attachment"}</strong>
      </p>
      {attachmentWarning(campaign.body, campaign.resume_id) && (
        <p className="notice">
          Your message says a resume is attached, but no file is selected.
        </p>
      )}
      {rows.map((row) => (
        <div className="review-recipient" key={row.contact_id}>
          <div className="actions">
            <strong>{row.email}</strong>
            <Btn
              secondary
              disabled={busy || saving}
              onClick={() => remove(row.contact_id)}
            >
              Remove recipient
            </Btn>
          </div>
          {row.already_sent && (
            <p role="alert">
              Already sent or awaiting reconciliation. Remove this recipient.
            </p>
          )}
          {row.missing.length > 0 && (
            <>
              <p className="notice">
                Missing personalization:{" "}
                {row.missing.map((field) => `{{${field}}}`).join(", ")}. The
                preview shows fallback text; fix these values or remove the
                recipient before sending.
              </p>
              <div className="form-grid two">
                {row.missing.map((field) => (
                  <label key={field}>
                    {field}
                    <input
                      aria-label={`${row.email} ${field}`}
                      value={edits[row.contact_id]?.[field] ?? ""}
                      onChange={(e) =>
                        setEdits((previous) => ({
                          ...previous,
                          [row.contact_id]: {
                            ...previous[row.contact_id],
                            [field]: e.target.value,
                          },
                        }))
                      }
                    />
                  </label>
                ))}
              </div>
              <Btn
                secondary
                disabled={
                  saving ||
                  busy ||
                  row.missing.some(
                    (field) => !edits[row.contact_id]?.[field]?.trim(),
                  )
                }
                onClick={() => fix(row)}
              >
                Save recipient changes
              </Btn>
            </>
          )}
        </div>
      ))}
      {chosen && (
        <div className="email-preview">
          <label>
            Preview as recipient
            <select
              aria-label="Preview as recipient"
              value={chosen.contact_id}
              onChange={(e) => setRecipient(Number(e.target.value))}
            >
              {rows.map((row) => (
                <option key={row.contact_id} value={row.contact_id}>
                  {row.email}
                </option>
              ))}
            </select>
          </label>
          <div className="mail-meta">
            <span>SUBJECT</span>
            <strong>{chosen.subject}</strong>
          </div>
          <pre>{chosen.body}</pre>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      {sendError && <p role="alert">{sendError}</p>}
      <div className="modal-actions">
        <Btn secondary disabled={busy || saving} onClick={close}>
          Back to recipients
        </Btn>
        <Btn
          disabled={
            busy ||
            saving ||
            resource.loading ||
            !!resource.error ||
            !rows.length ||
            blocked ||
            Object.keys(edits).some((id) => selected.includes(Number(id))) ||
            !gmail
          }
          onClick={send}
        >
          {busy
            ? "Sending…"
            : `Confirm send to ${rows.length} recipient${rows.length === 1 ? "" : "s"}`}
        </Btn>
      </div>
    </Modal>
  );
}
