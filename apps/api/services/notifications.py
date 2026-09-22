from datetime import datetime

from apps.api.config import get_settings
from apps.api.integrations.resend_client import send_email


def send_access_granted_email(email: str, label: str | None, expires_at: datetime | None) -> bool:
    app_url = get_settings().app_url

    expiry_html = (
        f"""
        <tr>
          <td style="padding-top: 20px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="background: #f5f6f5; border: 1px solid #d8dbd9; border-radius: 10px;">
              <tr>
                <td style="padding: 12px 16px; font-size: 13px; color: #5c646c;">
                  This access expires on
                  <strong style="color: #1f2429;">{expires_at.strftime('%B %d, %Y at %H:%M UTC')}</strong>.
                </td>
              </tr>
            </table>
          </td>
        </tr>
        """
        if expires_at
        else ""
    )
    label_html = (
        f"""
        <tr>
          <td style="padding-top: 16px; font-size: 12px; color: #5c646c;">
            Note: {label}
          </td>
        </tr>
        """
        if label
        else ""
    )

    html = f"""
    <div style="background: #f5f6f5; padding: 32px 16px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width: 480px; margin: 0 auto;">
        <tr>
          <td style="padding-bottom: 20px;">
            <span style="display: inline-block; width: 28px; height: 28px; border-radius: 8px; background: #2563eb; color: #ffffff; font-weight: 700; font-size: 14px; line-height: 28px; text-align: center;">K</span>
            <span style="margin-left: 8px; font-size: 14px; font-weight: 600; color: #1f2429; vertical-align: middle;">Koya Lead Agent</span>
          </td>
        </tr>
        <tr>
          <td style="background: #ffffff; border: 1px solid #d8dbd9; border-radius: 16px; padding: 32px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="font-size: 20px; font-weight: 600; color: #1f2429; padding-bottom: 12px;">
                  You've been granted access
                </td>
              </tr>
              <tr>
                <td style="font-size: 14px; line-height: 1.6; color: #1f2429;">
                  You can now sign in using <strong>{email}</strong>. Enter this email address on the sign-in page
                  and we'll send you a one-time code - no password needed.
                </td>
              </tr>
              <tr>
                <td style="padding-top: 24px;">
                  <a href="{app_url}"
                     style="display: inline-block; background: #2563eb; color: #ffffff; font-size: 14px; font-weight: 500; text-decoration: none; padding: 10px 20px; border-radius: 8px;">
                    Sign in to Koya Lead Agent
                  </a>
                </td>
              </tr>
              {expiry_html}
              {label_html}
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding-top: 20px; font-size: 12px; color: #5c646c; text-align: center;">
            {app_url}
          </td>
        </tr>
      </table>
    </div>
    """.strip()

    return send_email(email, "You've been granted access to Koya Lead Agent", html)
