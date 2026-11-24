import { useState } from "react";
import { Link } from "react-router-dom";
import { MailCheck, Eye, EyeOff, ArrowRight } from "lucide-react";
import { api } from "../services/api";
import ThemeToggle from "../components/ThemeToggle";

export default function Auth({ signup, onDone }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [visible, setVisible] = useState(false);
  async function submit(e) {
    e.preventDefault();
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    if (signup && fields.confirm !== fields.password) {
      setError("The passwords must match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const data = signup
        ? { name: fields.name, email: fields.email, password: fields.password }
        : {
            email: fields.email,
            password: fields.password,
            remember: !!fields.remember,
          };
      await onDone(
        await api(signup ? "/signup" : "/login", {
          method: "POST",
          body: data,
        }),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <header className="auth-header">
        <div className="brand auth-brand">
          <div className="brand-mark">
            <MailCheck size={21} />
          </div>
          <div>
            outreach<span>desk.</span>
          </div>
        </div>
        <ThemeToggle />
      </header>
      <section className="login-card">
        <h1>{signup ? "Create your account" : "Welcome back"}</h1>
        <p>
          {signup
            ? "Create a personal workspace for your outreach."
            : "Sign in to your OutreachDesk workspace."}
        </p>
        <form onSubmit={submit}>
          {signup && (
            <label>
              Full name
              <input name="name" required autoComplete="name" maxLength={140} />
            </label>
          )}
          <label>
            Email address
            <input
              type="email"
              name="email"
              autoComplete="username"
              required
              maxLength={254}
            />
          </label>
          <label>
            Password
            <span className="password-field">
              <input
                type={visible ? "text" : "password"}
                name="password"
                required
                autoComplete={signup ? "new-password" : "current-password"}
                minLength={signup ? 12 : 1}
                maxLength={128}
                aria-describedby={signup ? "password-hint" : undefined}
              />
              <button
                type="button"
                aria-label={visible ? "Hide password" : "Show password"}
                onClick={() => setVisible(!visible)}
              >
                {visible ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </span>
          </label>
          {signup ? (
            <>
              <small id="password-hint">Use 12–128 characters.</small>
              <label>
                Confirm password
                <input
                  type={visible ? "text" : "password"}
                  name="confirm"
                  required
                  autoComplete="new-password"
                />
              </label>
            </>
          ) : (
            <label className="check-line">
              <input name="remember" type="checkbox" />
              Remember me for 14 days
            </label>
          )}
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          <button className="btn" disabled={busy}>
            {busy ? "Please wait…" : signup ? "Create account" : "Sign in"}
            <ArrowRight size={16} />
          </button>
        </form>
        <p className="auth-switch">
          {signup ? "Already have an account?" : "New to OutreachDesk?"}{" "}
          <Link to={signup ? "/login" : "/signup"}>
            {signup ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </section>
    </main>
  );
}
