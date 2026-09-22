// `||`, not `??` -- a deploy platform can set this to an empty string
// rather than leaving it unset, which `??` would not fall back on.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const SESSION_STORAGE_KEY = "koya_session";
const EMAIL_STORAGE_KEY = "koya_user_email";

export type Session = {
  access_token: string;
  refresh_token: string | null;
  expires_at: string;
};

export function saveSession(session: Session, email: string) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  window.sessionStorage.setItem(EMAIL_STORAGE_KEY, email);
}

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
  return raw ? (JSON.parse(raw) as Session) : null;
}

export function getUserEmail(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(EMAIL_STORAGE_KEY);
}

export function clearSession() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
  window.sessionStorage.removeItem(EMAIL_STORAGE_KEY);
}

/** Logs out and sends the user back to sign-in. Safe to call from anywhere
 * (a button, or automatically when the API reports the session expired). */
export function logout() {
  clearSession();
  if (typeof window !== "undefined") {
    window.location.href = "/sign-in";
  }
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const session = getSession();
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (session) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    if (res.status === 401) {
      // Session expired or invalid server-side (e.g. the 1-hour app window
      // lapsed) -- clear the stale client-side session and send the user
      // straight back to sign-in rather than leaving them on a dead-end
      // error message with no way forward.
      logout();
    }
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }

  if (res.status === 204 || res.status === 202) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const api = {
  requestOtp: (email: string) => request<void>("/auth/request-otp", { method: "POST", body: JSON.stringify({ email }) }),
  verifyOtp: (email: string, token: string) =>
    request<Session>("/auth/verify-otp", { method: "POST", body: JSON.stringify({ email, token }) }),
  createRun: (objective: string) => request<RunOut>("/runs", { method: "POST", body: JSON.stringify({ objective }) }),
  listRuns: () => request<RunSummary[]>("/runs"),
  getRun: (runId: string) => request<RunOut>(`/runs/${runId}`),
  updateIcp: (runId: string, body: UpdateIcpBody) =>
    request<RunOut>(`/runs/${runId}/icp`, { method: "PATCH", body: JSON.stringify(body) }),
  getMe: () => request<Me>("/auth/me"),
  listAllowlist: () => request<AllowedActorOut[]>("/admin/allowlist"),
  createAllowlistEntry: (body: CreateAllowedActorBody) =>
    request<AllowedActorOut>("/admin/allowlist", { method: "POST", body: JSON.stringify(body) }),
  deleteAllowlistEntry: (entryId: string) =>
    request<void>(`/admin/allowlist/${entryId}`, { method: "DELETE" }),
};

export type ICPCriteria = {
  version: number;
  target_company_type: string | null;
  industries: string[];
  geography: string[];
  headcount_range: string | null;
  buyer_persona: string | null;
  business_problem: string | null;
  hard_filters: string[];
  soft_preferences: string[];
  disqualifiers: string[];
  assumptions_made: string[];
  needs_confirmation: string[];
  confirmed: boolean;
};

export type RunOut = {
  id: string;
  objective: string;
  status: string;
  lead_count_limit: number | null;
  icp: ICPCriteria | null;
  total_claude_cost_usd: number;
};

export type RunSummary = {
  id: string;
  objective: string;
  status: string;
  lead_count_limit: number | null;
  created_at: string;
};

export type UpdateIcpBody = {
  lead_count: number;
  confirm: boolean;
  hard_filters?: string[];
  soft_preferences?: string[];
};

export type Me = {
  email: string;
  is_admin: boolean;
};

export type AllowedActorOut = {
  id: string;
  email: string | null;
  email_domain: string | null;
  label: string | null;
  is_admin: boolean;
  expires_at: string | null;
  created_at: string;
};

export type CreateAllowedActorBody = {
  email?: string;
  email_domain?: string;
  label?: string;
  expires_at?: string;
};

export { ApiError };
