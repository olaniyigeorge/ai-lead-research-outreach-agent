"""Direct Resend calls for app-triggered notifications -- distinct from
Supabase Auth's OTP emails, which go through Supabase's own custom-SMTP
config (also backed by Resend, but that path never touches this module).
"""

import logging

import httpx

from apps.api.config import get_settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html: str) -> bool:
    """Best-effort: a failed notification email must never block the action
    that triggered it (e.g. granting access) -- the DB write is the source
    of truth, this is a courtesy notification. Returns True on success."""
    settings = get_settings()
    if not settings.resend_api_key or not settings.email_from_address:
        logger.warning("Resend not configured -- skipping email to %s", to)
        return False

    from_header = (
        f"{settings.email_from_name} <{settings.email_from_address}>"
        if settings.email_from_name
        else settings.email_from_address
    )

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": from_header, "to": [to], "subject": subject, "html": html},
            timeout=10.0,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.exception("failed to send email to %s via Resend", to)
        return False
