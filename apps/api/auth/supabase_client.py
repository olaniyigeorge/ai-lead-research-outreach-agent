"""Thin proxy to Supabase Auth's REST API for the passwordless email OTP flow.

FastAPI is the only caller of these endpoints -- the frontend never talks to
Supabase directly (see docs/work/koya_lead_agent_architecture.md and the
Milestone 0/1 plan). Both endpoints are public Supabase Auth endpoints that
only need the project's publishable key, not a user session or the secret key.
"""

import httpx

from apps.api.config import get_settings


class SupabaseAuthError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _error_detail(resp: httpx.Response) -> str:
    """Supabase Auth error bodies are JSON like

        {"code":429,"error_code":"over_email_send_rate_limit","msg":"..."}

    -- pull out the human-readable `msg` rather than ever surfacing the raw
    JSON to a caller (it eventually reaches the frontend as `ApiError.message`
    and gets rendered directly to the user).
    """
    try:
        body = resp.json()
    except ValueError:
        return "Something went wrong. Please try again."
    if isinstance(body, dict):
        msg = body.get("msg") or body.get("error_description") or body.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg
    return "Something went wrong. Please try again."


def _client() -> httpx.Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise SupabaseAuthError(503, "Supabase auth is not configured yet")
    return httpx.Client(
        base_url=settings.supabase_url.rstrip("/"),
        headers={"apikey": settings.supabase_publishable_key, "Content-Type": "application/json"},
        timeout=10.0,
    )


def request_otp(email: str) -> None:
    with _client() as client:
        resp = client.post("/auth/v1/otp", json={"email": email, "create_user": True})
    if resp.status_code >= 400:
        raise SupabaseAuthError(resp.status_code, _error_detail(resp))


def verify_otp(email: str, token: str) -> dict:
    with _client() as client:
        resp = client.post(
            "/auth/v1/verify",
            json={"email": email, "token": token, "type": "email"},
        )
    if resp.status_code >= 400:
        raise SupabaseAuthError(resp.status_code, _error_detail(resp))
    return resp.json()
