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
  requestAccess: (email: string, reason: string) =>
    request<AccessRequestOut>("/auth/request-access", { method: "POST", body: JSON.stringify({ email, reason: reason || undefined }) }),
  verifyOtp: (email: string, token: string) =>
    request<Session>("/auth/verify-otp", { method: "POST", body: JSON.stringify({ email, token }) }),
  createRun: (objective: string) => request<RunOut>("/runs", { method: "POST", body: JSON.stringify({ objective }) }),
  listRuns: () => request<RunSummary[]>("/runs"),
  getRun: (runId: string) => request<RunOut>(`/runs/${runId}`),
  updateIcp: (runId: string, body: UpdateIcpBody) =>
    request<RunOut>(`/runs/${runId}/icp`, { method: "PATCH", body: JSON.stringify(body) }),
  selectIcpVersion: (runId: string, version: number) =>
    request<RunOut>(`/runs/${runId}/icp/select-version`, { method: "PATCH", body: JSON.stringify({ version }) }),
  startRun: (runId: string) => request<RunOut>(`/runs/${runId}/start`, { method: "POST" }),
  topUpDiscovery: (runId: string, additionalCount: number) =>
    request<RunOut>(`/runs/${runId}/discovery/top-up`, {
      method: "POST",
      body: JSON.stringify({ additional_count: additionalCount }),
    }),
  useDiscoveryBuffer: (runId: string, count: number) =>
    request<RunOut>(`/runs/${runId}/discovery/use-buffer`, {
      method: "POST",
      body: JSON.stringify({ count }),
    }),
  startScrape: (runId: string) => request<RunOut>(`/runs/${runId}/scrape`, { method: "POST" }),
  startQualify: (runId: string) => request<RunOut>(`/runs/${runId}/qualify`, { method: "POST" }),
  startDraft: (runId: string) => request<RunOut>(`/runs/${runId}/draft`, { method: "POST" }),
  resetRun: (runId: string) => request<RunOut>(`/runs/${runId}/reset`, { method: "POST" }),
  listToolCalls: (runId: string) => request<ToolCallLog[]>(`/runs/${runId}/tool-calls`),
  getMe: () => request<Me>("/auth/me"),
  listAllowlist: () => request<AllowedActorOut[]>("/admin/allowlist"),
  createAllowlistEntry: (body: CreateAllowedActorBody) =>
    request<AllowedActorOut>("/admin/allowlist", { method: "POST", body: JSON.stringify(body) }),
  deleteAllowlistEntry: (entryId: string) =>
    request<void>(`/admin/allowlist/${entryId}`, { method: "DELETE" }),
  listAccessRequests: () => request<AccessRequestOut[]>("/admin/access-requests"),
  decideAccessRequest: (requestId: string, decision: "granted" | "rejected") =>
    request<AccessRequestOut>(`/admin/access-requests/${requestId}/decide`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
};

export type AccessRequestOut = {
  id: string;
  email: string;
  reason: string | null;
  status: string;
  created_at: string;
  decided_at: string | null;
  decided_by_email: string | null;
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

export type LeadSource = {
  id: string;
  lead_id: string;
  url: string;
  page_type: string;
  http_status: number | null;
  content_summary: string | null;
  truncated: boolean;
  fetched_at: string;
};

export type Draft = {
  id: string;
  lead_id: string;
  channel: string;
  subject: string | null;
  body: string;
  personalization_note: string | null;
  cited_source_ids: string[];
  created_at: string;
};

export type Lead = {
  id: string;
  company_name: string;
  company_domain: string;
  qualification_status: string;
  source_raw: Record<string, unknown>;
  created_at: string;
  is_buffer: boolean;
  confidence_score: number | null;
  fit_reasons: string[];
  concerns: string[];
  missing_information: string[];
  sources: LeadSource[];
  drafts: Draft[];
  last_error: string | null;
};

export type RunOut = {
  id: string;
  objective: string;
  status: string;
  lead_count_limit: number | null;
  icp: ICPCriteria | null;
  icp_versions: ICPCriteria[];
  leads: Lead[];
  total_run_cost_usd: number;
  claude_cost_by_stage: Record<string, number>;
  external_usage: ExternalUsage[];
};

export type ExternalUsage = {
  stage: string;
  source: string;
  units: number;
  estimated_cost_usd: number | null;
};

export type ToolCallLog = {
  id: string;
  stage: string;
  tool_name: string;
  input_summary: Record<string, unknown> | null;
  result_summary: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
  created_at: string;
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
  target_company_type?: string;
  industries?: string[];
  geography?: string[];
  headcount_range?: string;
  buyer_persona?: string;
  business_problem?: string;
  hard_filters?: string[];
  soft_preferences?: string[];
  disqualifiers?: string[];
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
  last_login_at: string | null;
};

export type CreateAllowedActorBody = {
  email?: string;
  email_domain?: string;
  label?: string;
  expires_at?: string;
};

export { ApiError };
