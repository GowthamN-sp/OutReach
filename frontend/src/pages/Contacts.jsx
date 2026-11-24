import { Users, Plus, Search, UploadCloud, Trash2, Check } from "lucide-react";
import { useEffect, useState } from "react";
import { time } from "../utils/format";
import { Badge, Empty, Head, Btn, Modal } from "../components/UI";
import { allPages, api } from "../services/api";
export default function Contacts({ tick, refresh, notify }) {
  const [items, setItems] = useState(null),
    [status, setStatus] = useState(""),
    [history, setHistory] = useState(null),
    [search, setSearch] = useState(""),
    [show, setShow] = useState(false),
    [importing, setImporting] = useState(false),
    [preview, setPreview] = useState(null),
    [person, setPerson] = useState({
      name: "",
      email: "",
      company: "",
      role: "",
    });
  async function load() {
    try {
      setItems(await allPages("/contacts"));
    } catch (e) {
      notify(e.message, true);
    }
  }
  useEffect(() => {
    load();
  }, [tick]);
  async function save(e) {
    e.preventDefault();
    try {
      await api("/contacts" + (person.id ? "/" + person.id : ""), {
        method: person.id ? "PUT" : "POST",
        body: person,
      });
      setShow(false);
      setPerson({ name: "", email: "", company: "", role: "" });
      load();
      refresh();
      notify("Contact saved");
    } catch (e) {
      notify(e.message, true);
    }
  }
  async function file(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    let fd = new FormData();
    fd.append("file", f);
    try {
      let x = await api("/import/preview", {
        method: "POST",
        body: fd,
        form: true,
      });
      setPreview(x);
      setImporting(true);
    } catch (err) {
      notify(err.message, true);
    }
    e.target.value = "";
  }
  async function commit() {
    try {
      let x = await api("/import/commit", {
        method: "POST",
        body: { contacts: preview.contacts },
      });
      notify(`${x.added} contacts imported · ${x.skipped} skipped`);
      setImporting(false);
      setPreview(null);
      load();
      refresh();
    } catch (e) {
      notify(e.message, true);
    }
  }
  const filtered = (items || [])
    .filter((c) => !status || c.status === status)
    .filter((x) =>
      (x.email + " " + x.name + " " + x.company)
        .toLowerCase()
        .includes(search.toLowerCase()),
    );
  return (
    <>
      <Head
        eyebrow="CONTACT MANAGEMENT"
        title="Your contacts"
        desc="A clean home for recruiters, hiring managers, and every opportunity."
        action={
          <div className="actions">
            <label className="btn btn-secondary cursor">
              <UploadCloud size={17} /> Import CSV / Excel / PDF{" "}
              <input
                hidden
                type="file"
                accept=".csv,.xlsx,.pdf"
                onChange={file}
              />
            </label>
            <Btn
              icon={Plus}
              onClick={() => {
                setPerson({ name: "", email: "", company: "", role: "" });
                setShow(true);
              }}
            >
              Add contact
            </Btn>
          </div>
        }
      />
      <div className="panel table-panel">
        <div className="table-toolbar">
          <div className="search-wrap">
            <Search size={17} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, email, company..."
            />
          </div>
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            {["New", "Contacted", "Replied"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
          <span className="results">{filtered.length} contacts</span>
        </div>
        {items === null ? (
          <p className="pad">Loading contacts…</p>
        ) : filtered.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>CONTACT</th>
                  <th>COMPANY</th>
                  <th>TARGET ROLE</th>
                  <th>SOURCE</th>
                  <th>STATUS</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <div className="table-person">
                        <span className="person-avatar">
                          {(c.name || c.email)[0].toUpperCase()}
                        </span>
                        <div>
                          <strong>{c.name || "Unnamed contact"}</strong>
                          <small>{c.email}</small>
                        </div>
                      </div>
                    </td>
                    <td>{c.company || "—"}</td>
                    <td>{c.role || "—"}</td>
                    <td>{c.source}</td>
                    <td>
                      <Badge
                        tone={
                          c.status === "Replied"
                            ? "success"
                            : c.status === "Contacted"
                              ? "info"
                              : "neutral"
                        }
                      >
                        {c.status}
                      </Badge>
                    </td>
                    <td>
                      <button
                        className="text-link"
                        onClick={() => {
                          setPerson(c);
                          setShow(true);
                        }}
                      >
                        Edit
                      </button>
                      <button
                        className="text-link"
                        onClick={async () => {
                          try {
                            setHistory({
                              contact: c,
                              rows: await allPages("/sent?contact_id=" + c.id),
                            });
                          } catch (e) {
                            notify(e.message, true);
                          }
                        }}
                      >
                        History
                      </button>
                      <button
                        className="icon-btn"
                        title="Delete if unused"
                        onClick={async () => {
                          if (!confirm("Delete this contact?")) return;
                          try {
                            await api("/contacts/" + c.id, {
                              method: "DELETE",
                            });
                            load();
                            refresh();
                          } catch (e) {
                            notify(e.message, true);
                          }
                        }}
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            icon={Users}
            title="No contacts yet"
            desc="Import a recruiter list or add contacts individually."
          />
        )}
      </div>
      {history && (
        <Modal
          title={"Outreach history · " + history.contact.email}
          close={() => setHistory(null)}
        >
          {history.rows.length ? (
            history.rows.map((r) => (
              <p key={r.id}>
                {r.campaign} · {r.status} · {time(r.sent_at)}
              </p>
            ))
          ) : (
            <p>No outreach yet.</p>
          )}
        </Modal>
      )}
      {show && (
        <Modal
          title={person.id ? "Edit contact" : "Add a contact"}
          close={() => setShow(false)}
        >
          <form onSubmit={save} className="form-grid">
            {[
              ["name", "Name"],
              ["email", "Email address"],
              ["company", "Company"],
              ["role", "Target role"],
            ].map(([k, l]) => (
              <label key={k}>
                {l}
                <input
                  type={k === "email" ? "email" : "text"}
                  required={k === "email"}
                  value={person[k]}
                  onChange={(e) =>
                    setPerson((p) => ({ ...p, [k]: e.target.value }))
                  }
                  placeholder={l}
                />
              </label>
            ))}
            <div className="modal-actions">
              <Btn secondary onClick={() => setShow(false)}>
                Cancel
              </Btn>
              <Btn type="submit" icon={Plus}>
                Save contact
              </Btn>
            </div>
          </form>
        </Modal>
      )}
      {importing && (
        <Modal
          title="Review imported contacts"
          close={() => setImporting(false)}
          wide
        >
          <p className="muted">
            Found {preview.total} unique email addresses. PDF extraction is
            approximate; check names and addresses before importing.
          </p>
          <div className="preview-list">
            {preview.contacts.map((c, i) => (
              <fieldset key={i} className="form-grid two">
                <legend>Contact {i + 1}</legend>
                {["email", "name", "company", "role"].map((k) => (
                  <label key={k}>
                    {k}
                    <input
                      value={c[k]}
                      onChange={(e) =>
                        setPreview((p) => ({
                          ...p,
                          contacts: p.contacts.map((row, j) =>
                            j === i ? { ...row, [k]: e.target.value } : row,
                          ),
                        }))
                      }
                    />
                  </label>
                ))}
              </fieldset>
            ))}
          </div>
          <div className="modal-actions">
            <Btn secondary onClick={() => setImporting(false)}>
              Cancel
            </Btn>
            <Btn
              icon={Check}
              disabled={!preview.contacts.length}
              onClick={commit}
            >
              Import {preview.contacts.length} contacts
            </Btn>
          </div>
        </Modal>
      )}
    </>
  );
}
