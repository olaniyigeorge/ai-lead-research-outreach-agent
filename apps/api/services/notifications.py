from datetime import datetime

from apps.api.config import get_settings
from apps.api.integrations.resend_client import send_email


def send_access_granted_email(email: str, label: str | None, expires_at: datetime | None) -> bool:
    app_url = get_settings().app_url
    expiry_line = (
        f"<p>This access expires on <strong>{expires_at.strftime('%B %d, %Y at %H:%M UTC')}</strong>.</p>"
        if expires_at
        else "<p>This access does not expire.</p>"
    )
    label_line = f"<p>Note: {label}</p>" if label else ""

    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #1f2429;">You've been granted access</h2>
      <p>You can now sign in to the Koya Lead Agent at
        <a href="{app_url}" style="color: #2563eb;">{app_url}</a> using this email address.
        Enter your email there and we'll send you a one-time sign-in code.</p>
      {expiry_line}
      {label_line}
    </div>
    """.strip()

    return send_email(email, "You've been granted access to Koya Lead Agent", html)
