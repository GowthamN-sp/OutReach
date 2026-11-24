import { useState } from "react";
import { api } from "../services/api";
import { Btn, Modal } from "./UI";

export default function ImportReview({ preview, close, done }) {
  const [rows, setRows] = useState(preview.contacts);
  const [existingEmails, setExistingEmails] = useState(preview.existing_emails);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const existing = new Set(existingEmails);
  const seen = new Set();
  const reviewed = rows.map((row, index) => {
    const email = row.email.trim().toLowerCase();
    const invalid =
      !/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(email) ||
      row.issues?.includes("Invalid email address");
    const duplicate = seen.has(email);
    if (!row.skip) seen.add(email);
    const issues = [
      invalid && "Invalid email address",
      existing.has(email) && "Already in Contacts",
      duplicate && "Duplicate within file",
      ["name", "company", "role"].some(
        (k) => row[k].length > 250 || /[\r\n]/.test(row[k]),
      ) && "Fields must be one line and at most 250 characters",
    ].filter(Boolean);
    return {
      ...row,
      index,
      email,
      issues,
      invalid,
      duplicate,
      missing: ["name", "company", "role"].filter((key) => !row[key].trim()),
    };
  });
  const included = reviewed.filter((row) => !row.skip);
  const ready = included.filter((row) => !row.issues.length);
  async function commit() {
    setBusy(true);
    setError("");
    try {
      const validated = await api("/import/review", {
        method: "POST",
        body: {
          contacts: ready.map(({ email, name, company, role }) => ({
            email,
            name,
            company,
            role,
          })),
        },
      });
      setExistingEmails(validated.existing_emails);
      if (validated.contacts.some((row) => row.issues.length)) {
        const corrections = new Map(
          ready.map((row, index) => [row.index, validated.contacts[index]]),
        );
        setRows((previous) =>
          previous.map((row, index) =>
            corrections.has(index)
              ? { ...row, ...corrections.get(index) }
              : row,
          ),
        );
        setError(
          "Some rows need correction after server validation. Correct or skip the flagged rows, then confirm again.",
        );
        return;
      }
      const result = await api("/import/commit", {
        method: "POST",
        body: {
          batch: preview.batch,
          contacts: validated.contacts,
        },
      });
      done(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function change(index, key, value) {
    setRows((previous) =>
      previous.map((row, i) =>
        i === index
          ? { ...row, [key]: value, issues: key === "skip" ? row.issues : [] }
          : row,
      ),
    );
  }
  return (
    <Modal
      title="Review imported contacts"
      close={busy ? () => {} : close}
      wide
    >
      <p className="muted">
        Review every row before saving. Missing names, companies and roles may
        need correction before campaign personalization. PDF extraction is
        approximate.
      </p>
      <p role="status">
        {ready.length} valid rows · {included.filter((r) => r.invalid).length}{" "}
        invalid addresses · {included.filter((r) => r.duplicate).length}{" "}
        duplicates within file ·{" "}
        {included.filter((r) => existing.has(r.email)).length} already in
        Contacts · {included.filter((r) => r.missing.length).length} missing
        personalization fields · {rows.filter((r) => r.skip).length} skipped
      </p>
      <div className="preview-list">
        {reviewed.map((row, index) => (
          <fieldset key={index} className="form-grid two" disabled={busy}>
            <legend>Row {index + 1}</legend>
            <label className="option-row">
              <input
                type="checkbox"
                checked={!!row.skip}
                onChange={(e) => change(index, "skip", e.target.checked)}
              />{" "}
              Skip row {index + 1}
            </label>
            <p className="muted">
              {row.issues.join(" · ") || "Valid address"}
              {row.missing.length
                ? ` · Missing: ${row.missing.join(", ")}`
                : ""}
            </p>
            {["email", "name", "company", "role"].map((key) => (
              <label key={key}>
                {key}
                <input
                  disabled={row.skip}
                  value={row[key]}
                  maxLength={250}
                  onChange={(e) => change(index, key, e.target.value)}
                />
              </label>
            ))}
          </fieldset>
        ))}
      </div>
      {error && <p role="alert">{error}</p>}
      <p>
        Final import count: <strong>{ready.length}</strong>. Correct or skip
        invalid and duplicate rows to continue.
      </p>
      <div className="modal-actions">
        <Btn secondary disabled={busy} onClick={close}>
          Cancel
        </Btn>
        <Btn
          disabled={
            busy || !ready.length || included.some((row) => row.issues.length)
          }
          onClick={commit}
        >
          {busy
            ? "Importing…"
            : `Confirm import ${ready.length} contact${ready.length === 1 ? "" : "s"}`}
        </Btn>
      </div>
    </Modal>
  );
}
