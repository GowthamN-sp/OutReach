import { useRef, useEffect } from "react";
import { Inbox, X, ShieldCheck } from "lucide-react";
export function Badge({ children, tone = "neutral" }) {
  return (
    <span className={"badge " + tone}>
      <span className="badge-dot" />
      {children}
    </span>
  );
}
export function Empty({ icon: Icon = Inbox, title, desc, action }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon size={25} />
      </span>
      <h3>{title}</h3>
      <p>{desc}</p>
      {action}
    </div>
  );
}
export function Head({ eyebrow, title, desc, action }) {
  return (
    <div className="section-head">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{desc}</p>
      </div>
      {action && <div className="head-action">{action}</div>}
    </div>
  );
}
export function Btn({
  children,
  icon: Icon,
  secondary = false,
  ghost = false,
  onClick,
  disabled = false,
  type = "button",
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={
        "btn " +
        (secondary ? "btn-secondary " : "") +
        (ghost ? "btn-ghost" : "")
      }
      onClick={onClick}
    >
      {Icon && <Icon size={16} />}
      <span>{children}</span>
    </button>
  );
}
export function DemoNotice({ boot }) {
  return !boot?.gmail_connected ? (
    <div className="notice">
      <ShieldCheck size={17} />
      <span>
        <strong>Gmail is disconnected.</strong> Connect your mailbox in Settings
        to send email and sync replies.
      </span>
    </div>
  ) : null;
}
export function Modal({ title, close, children, wide = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog
      ref={ref}
      aria-label={title}
      className={"modal " + (wide ? "wide" : "")}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      onClick={(e) => {
        if (e.target === ref.current) {
          const r = ref.current.getBoundingClientRect();
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            close();
        }
      }}
    >
      <div className="modal-header">
        <h2>{title}</h2>
        <button
          type="button"
          className="icon-btn"
          aria-label="Close dialog"
          onClick={close}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
