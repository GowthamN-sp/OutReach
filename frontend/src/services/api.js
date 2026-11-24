import { clearResources } from "./useResource";
let csrf = "";
let owner;
export function setSession(session) {
  if (owner !== session?.user?.id) clearResources();
  owner = session?.user?.id;
  csrf = session?.csrf || "";
}
export async function api(
  path,
  { method = "GET", body, form = false, signal } = {},
) {
  const headers = {};
  if (method !== "GET") headers["X-CSRF-Token"] = csrf;
  if (body && !form) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch("/api" + path, {
      method,
      signal,
      credentials: "same-origin",
      headers,
      body: body ? (form ? body : JSON.stringify(body)) : undefined,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(
      "Cannot reach the server. Check your connection and retry.",
    );
  }
  if (!response.ok) {
    if (
      response.status === 401 &&
      !["/login", "/signup", "/session"].includes(path)
    )
      window.dispatchEvent(new Event("session-expired"));
    const error = await response.json().catch(() => ({}));
    throw Object.assign(
      new Error(
        typeof error.detail === "string"
          ? error.detail
          : response.status >= 500
            ? "The server could not complete this request. Retry; if it continues, check the backend logs."
            : `Request failed (HTTP ${response.status}). Please retry.`,
      ),
      { status: response.status },
    );
  }
  try {
    return await response.json();
  } catch {
    throw new Error(
      "The server returned an unexpected response. Check that the API is running, then retry.",
    );
  }
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
    if (!Array.isArray(page))
      throw new Error(
        "The server returned an unexpected list response. Please retry.",
      );
    rows.push(...page);
    if (page.length < 200) return rows;
  }
}
