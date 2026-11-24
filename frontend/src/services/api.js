let csrf = "";
export function setSession(session) {
  csrf = session?.csrf || "";
}
export async function api(
  path,
  { method = "GET", body, form = false, signal } = {},
) {
  const headers = {};
  if (method !== "GET") headers["X-CSRF-Token"] = csrf;
  if (body && !form) headers["Content-Type"] = "application/json";
  const response = await fetch("/api" + path, {
    method,
    signal,
    credentials: "same-origin",
    headers,
    body: body ? (form ? body : JSON.stringify(body)) : undefined,
  });
  if (!response.ok) {
    if (
      response.status === 401 &&
      !["/login", "/signup", "/session"].includes(path)
    )
      window.dispatchEvent(new Event("session-expired"));
    const error = await response.json().catch(() => ({}));
    throw Object.assign(
      new Error(error.detail || "The request failed. Please try again."),
      { status: response.status },
    );
  }
  return response.json();
}
export async function allPages(path) {
  const rows = [];
  for (let offset = 0; ; offset += 200) {
    const page = await api(
      path +
        (path.includes("?") ? "&" : "?") +
        "offset=" +
        offset +
        "&limit=200",
    );
    rows.push(...page);
    if (page.length < 200) return rows;
  }
}
