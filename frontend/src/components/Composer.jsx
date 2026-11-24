import { useState } from "react";
import { Check } from "lucide-react";
import { api } from "../services/api";
import { Btn, Modal } from "./UI";
import { TrackingChoices, TrackingDisclosure } from "./Tracking";
const INITIAL = {
  name: "",
  subject: "",
  body: "",
  resume_id: null,
  tracking_open: false,
  tracking_click: false,
};
export default function Composer({
  close,
  templates,
  setTemplates,
  resumes,
  boot,
  refresh,
  notify,
}) {
  const [compose, setCompose] = useState({
    ...INITIAL,
    tracking_open: !!boot.tracking_open && boot.tracking_ready,
    tracking_click: !!boot.tracking_click && boot.tracking_ready,
    resume_id: resumes.find((r) => r.is_default)?.id || null,
  });
  async function create(e) {
    e.preventDefault();
    try {
      await api("/campaigns", { method: "POST", body: compose });
      close();

      refresh();
      notify("Campaign saved as a draft");
    } catch (e) {
      notify(e.message, true);
    }
  }
  return (
    <Modal title="Create a campaign" close={close} wide>
      <form className="compose-form" onSubmit={create}>
        <label>
          Use a template
          <select
            defaultValue=""
            onChange={(e) => {
              const t = templates.find((t) => t.id === Number(e.target.value));
              if (t)
                setCompose({
                  ...compose,
                  name: t.name,
                  subject: t.subject,
                  body: t.body,
                });
            }}
          >
            <option value="">Choose a template</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <div className="form-grid two">
          <label>
            Campaign name
            <input
              value={compose.name}
              onChange={(e) => setCompose({ ...compose, name: e.target.value })}
              required
            />
          </label>
          <label>
            Subject line
            <input
              value={compose.subject}
              onChange={(e) =>
                setCompose({ ...compose, subject: e.target.value })
              }
              required
            />
          </label>
        </div>
        <label>
          Message body
          <textarea
            rows={12}
            value={compose.body}
            onChange={(e) => setCompose({ ...compose, body: e.target.value })}
            required
          />
        </label>
        <p className="muted">
          Variables: <code>{"{{name}}"}</code>, <code>{"{{company}}"}</code>,{" "}
          <code>{"{{role}}"}</code>. A separate message is generated for each
          recipient.
        </p>
        <div className="option-row">
          <label>
            Resume attachment
            <select
              value={compose.resume_id || ""}
              onChange={(e) =>
                setCompose({
                  ...compose,
                  resume_id: Number(e.target.value) || null,
                })
              }
            >
              <option value="">No attachment</option>
              {resumes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
          {compose.resume_id && (
            <a
              className="text-link"
              target="_blank"
              rel="noreferrer"
              href={"/api/resumes/" + compose.resume_id + "/file"}
            >
              Preview PDF
            </a>
          )}
        </div>
        <TrackingChoices
          value={compose}
          onChange={setCompose}
          ready={boot.tracking_ready}
        />
        <TrackingDisclosure />
        <div className="modal-actions">
          <Btn secondary onClick={close}>
            Cancel
          </Btn>
          <Btn
            secondary
            onClick={async () => {
              try {
                await api("/templates", { method: "POST", body: compose });
                setTemplates(await api("/templates"));
                notify("Template saved");
              } catch (e) {
                notify(e.message, true);
              }
            }}
          >
            Save as template
          </Btn>
          <Btn type="submit" icon={Check}>
            Save campaign
          </Btn>
        </div>
      </form>
    </Modal>
  );
}
