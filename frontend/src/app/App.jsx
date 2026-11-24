import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import Layout from "../components/Layout";
import Auth from "../pages/Auth";
const Dashboard = lazy(() => import("../pages/Dashboard"));
const Contacts = lazy(() => import("../pages/Contacts"));
const Campaigns = lazy(() => import("../pages/Campaigns"));
const Inbox = lazy(() => import("../pages/Inbox"));
const Resume = lazy(() => import("../pages/Resume"));
const Analytics = lazy(() => import("../pages/Analytics"));
const Sent = lazy(() => import("../pages/Sent"));
const Settings = lazy(() => import("../pages/Settings"));
import { api, setSession } from "../services/api";

const pages = {
  dashboard: Dashboard,
  contacts: Contacts,
  campaigns: Campaigns,
  inbox: Inbox,
  resume: Resume,
  analytics: Analytics,
  sent: Sent,
  settings: Settings,
};
export default function App() {
  const [user, setUser] = useState(null),
    [boot, setBoot] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [tick, setTick] = useState(0),
    [toast, setToast] = useState(null);
  const timer = useRef(),
    go = useNavigate(),
    location = useLocation();
  const notify = useCallback((msg, err = false) => {
    clearTimeout(timer.current);
    setToast({ msg, err });
    timer.current = setTimeout(() => setToast(null), 5000);
  }, []);
  function clear() {
    setSession(null);
    setUser(null);
    setBoot(null);
    setToast(null);
    clearTimeout(timer.current);
  }
  async function accept(session) {
    setSession(session);
    const data = await api("/bootstrap");
    setBoot(data);
    setUser(session.user);
    setError("");
  }
  async function restore() {
    setLoading(true);
    setError("");
    try {
      await accept(await api("/session"));
    } catch (e) {
      if (e.status !== 401) setError(e.message);
      else clear();
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    restore();
    window.addEventListener("session-expired", clear);
    return () => {
      window.removeEventListener("session-expired", clear);
      clearTimeout(timer.current);
    };
  }, []);
  async function refresh() {
    try {
      setBoot(await api("/bootstrap"));
      setTick((n) => n + 1);
    } catch (e) {
      notify(e.message, true);
    }
  }
  async function logout() {
    try {
      await api("/logout", { method: "POST" });
      clear();
      go("/login", { replace: true });
    } catch (e) {
      notify(e.message, true);
    }
  }
  if (loading || error)
    return (
      <main className="loading-splash">
        {error ? (
          <div role="alert">
            <p>{error}</p>
            <button className="btn" onClick={restore}>
              Retry connection
            </button>
          </div>
        ) : (
          "Loading workspace…"
        )}
      </main>
    );
  if (!user)
    return (
      <Routes>
        {["login", "signup"].map((p) => (
          <Route
            key={p}
            path={"/" + p}
            element={<Auth key={p} signup={p === "signup"} onDone={accept} />}
          />
        ))}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  const page = location.pathname.slice(1);
  if (!page || page === "login" || page === "signup")
    return <Navigate replace to="/dashboard" />;
  const props = {
    user,
    updateUser: setUser,
    boot,
    tick,
    refresh,
    notify,
    navigate: (p) => go("/" + p),
  };
  return (
    <Layout
      page={page}
      go={go}
      user={user}
      boot={boot}
      refresh={refresh}
      logout={logout}
      toast={toast}
    >
      <Routes>
        {Object.entries(pages).map(([path, Page]) => (
          <Route
            key={path}
            path={"/" + path}
            element={
              <Suspense fallback={<p role="status">Loading page…</p>}>
                <Page {...props} />
              </Suspense>
            }
          />
        ))}
        <Route
          path="*"
          element={
            <section>
              <h1>Page not found</h1>
              <button className="btn" onClick={() => go("/dashboard")}>
                Back to overview
              </button>
            </section>
          }
        />
      </Routes>
    </Layout>
  );
}
