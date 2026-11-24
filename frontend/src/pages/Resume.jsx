import { useState, useEffect } from "react";
import { FileText, Download, Eye, Trash2 } from "lucide-react";
import { Head, Badge, Empty } from "../components/UI";
import { api } from "../services/api";
export default function Resume({ tick, refresh, notify }) {
  const [rows, setRows] = useState(null),
    [preview, setPreview] = useState(null),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api("/resumes")
      .then(setRows)
      .catch((e) => notify(e.message, true));
  }, [tick, notify]);
  async function upload(e) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    try {
      await api("/resumes", {
        method: "POST",
        body: new FormData(form),
        form: true,
      });
      form.reset();
      refresh();
      notify("Resume saved");
    } catch (err) {
      notify(err.message, true);
    } finally {
      setBusy(false);
    }
  }
  async function act(row, remove) {
    if (remove && !confirm("Delete " + row.name + "?")) return;
    try {
      await api("/resumes/" + row.id + (remove ? "" : "/default"), {
        method: remove ? "DELETE" : "PUT",
      });
      if (remove && preview === row.id) setPreview(null);
      refresh();
    } catch (err) {
      notify(err.message, true);
    }
  }
  return (
    <>
      <Head
        title="Resume vault"
        desc="Keep PDF versions for different roles and choose a default for new campaigns."
      />
      <div className="resume-layout">
        <div className="panel pad">
          <h3>Saved resumes</h3>
          {rows === null ? (
            <p>Loading…</p>
          ) : !rows.length ? (
            <Empty
              icon={FileText}
              title="No resumes yet"
              desc="Upload a PDF to attach it to your outreach."
            />
          ) : (
            rows.map((r) => (
              <div key={r.id} className="resume-file">
                <div>
                  <strong>{r.name}</strong>
                  <small>
                    {r.filename} · {Math.ceil(r.size / 1024)} KB
                  </small>
                  {r.is_default ? (
                    <Badge>Default</Badge>
                  ) : (
                    <button className="text-link" onClick={() => act(r, false)}>
                      Make default
                    </button>
                  )}
                </div>
                <button
                  className="icon-btn"
                  aria-label={"Preview " + r.name}
                  onClick={() => setPreview(preview === r.id ? null : r.id)}
                >
                  <Eye size={18} />
                </button>
                <a
                  className="icon-btn"
                  aria-label={"Download " + r.name}
                  href={"/api/resumes/" + r.id + "/file?download=true"}
                >
                  <Download size={18} />
                </a>
                <button
                  className="icon-btn"
                  aria-label={"Delete " + r.name}
                  onClick={() => act(r, true)}
                >
                  <Trash2 size={17} />
                </button>
              </div>
            ))
          )}
          {preview && (
            <iframe
              className="pdf-frame"
              src={"/api/resumes/" + preview + "/file"}
              title="Resume preview"
            />
          )}
        </div>
        <form className="panel pad form-grid" onSubmit={upload}>
          <h3>Upload a version</h3>
          <label>
            Resume name
            <input
              name="name"
              maxLength={140}
              placeholder="Python Developer Resume"
            />
          </label>
          <label>
            PDF file · up to 8 MB
            <input
              name="file"
              type="file"
              accept="application/pdf,.pdf"
              required
            />
          </label>
          <button className="btn" disabled={busy}>
            {busy ? "Uploading…" : "Upload resume"}
          </button>
        </form>
      </div>
    </>
  );
}
