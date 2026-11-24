const API_BASE = "/api/v1";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : body.detail?.code;
    throw new Error(detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export interface LoginResponse {
  status: "authenticated" | "mfa_required";
  access_token?: string;
  mfa_ticket?: string;
  methods?: string[];
  mfa_setup_required?: boolean;
}

export function register(email: string, password: string) {
  return apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function mfaVerify(mfaTicket: string, method: string, code: string) {
  return apiFetch("/mfa/verify", {
    method: "POST",
    body: JSON.stringify({ mfa_ticket: mfaTicket, method, code }),
  });
}

export interface TotpEnrollResponse {
  secret: string;
  provisioning_uri: string;
}

export function totpEnroll(): Promise<TotpEnrollResponse> {
  return apiFetch("/mfa/totp/enroll", { method: "POST" });
}

export function totpConfirm(code: string) {
  return apiFetch("/mfa/totp/confirm", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export function regenerateRecoveryCodes() {
  return apiFetch("/mfa/recovery-codes/regenerate", { method: "POST" });
}

export interface SessionOut {
  id: string;
  ip_addr: string | null;
  user_agent: string | null;
  amr: string[];
  created_current: boolean;
}

export function listSessions(): Promise<SessionOut[]> {
  return apiFetch("/auth/sessions");
}

export function revokeSession(sid: string) {
  return apiFetch(`/auth/sessions/${sid}`, { method: "DELETE" });
}

export function logoutAll() {
  return apiFetch("/auth/logout-all", { method: "POST" });
}
