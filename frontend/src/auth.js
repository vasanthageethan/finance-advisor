const BASE_URL = "http://localhost:8000";
const TOKEN_KEY = "finance_advisor_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Shared fetch wrapper for every authenticated API call -- attaches the
// bearer token and, on a 401 (expired/invalid session), clears it and
// forces back to the login screen rather than leaving the app stuck
// silently failing every request.
export async function authedFetch(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  });
  if (res.status === 401) {
    clearToken();
    window.location.reload();
    throw new Error("Session expired");
  }
  return res;
}

export async function getAuthStatus() {
  const res = await fetch(`${BASE_URL}/auth/status`);
  if (!res.ok) throw new Error("Could not reach the server");
  return res.json();
}

export async function setPassword(password) {
  const res = await fetch(`${BASE_URL}/auth/set-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Could not set password");
  const data = await res.json();
  setToken(data.access_token);
  return data;
}

export async function login(email, password) {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Login failed");
  const data = await res.json();
  setToken(data.access_token);
  return data;
}

export async function logout() {
  clearToken();
}

// Deliberately plain fetch, not authedFetch -- this is the initial
// "am I already logged in" check AuthGate makes on load. A 401 here just
// means "not logged in yet," not "session expired mid-use," so it must
// not trigger authedFetch's reload-back-to-login behavior.
export async function getMe() {
  const res = await fetch(`${BASE_URL}/auth/me`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}
