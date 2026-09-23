import logging
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from apps.api.auth.allowlist import is_email_allowed, normalize_email
from apps.api.auth.jwt import decode_supabase_jwt
from apps.api.auth.session import start_session
from apps.api.auth.supabase_client import SupabaseAuthError, request_otp, verify_otp

logger = logging.getLogger(__name__)


def request_otp_for_email(db: Session, email: str) -> None:
    normalized = normalize_email(email)
    if not is_email_allowed(db, normalized):
        raise HTTPException(status_code=403, detail="This email is not authorized for this app")

    try:
        request_otp(normalized)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def verify_otp_for_email(db: Session, email: str, token: str) -> dict:
    normalized = normalize_email(email)
    try:
        result = verify_otp(normalized, token)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    access_token = result.get("access_token")
    refresh_token = result.get("refresh_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Supabase did not return an access token")

    try:
        payload = decode_supabase_jwt(access_token)
    except HTTPException as exc:
        # decode_supabase_jwt() is written for the request-auth path (a bad
        # token there is the caller's fault -> 401); here we're verifying a
        # token Supabase itself just issued, so a decode failure is ours.
        # decode_supabase_jwt() already logs the underlying PyJWTError and
        # retries transient JWKS-fetch failures itself -- forward its actual
        # status/detail (e.g. 503 "please try again" for a network blip)
        # rather than flattening every cause into one generic 502, which
        # only told the user to do the exact same thing that had just failed.
        logger.error(
            "Failed to decode a token Supabase itself just issued for %s: %s", normalized, exc.detail
        )
        raise

    supabase_user_id = uuid.UUID(payload["sub"])
    session = start_session(db, supabase_user_id, normalized)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": session.expires_at,
    }
