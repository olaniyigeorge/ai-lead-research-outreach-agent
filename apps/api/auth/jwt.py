"""Verifies Supabase-issued access tokens.

New Supabase projects sign JWTs asymmetrically (ES256/RS256) with rotatable
"JWT Signing Keys" rather than a single shared HS256 secret -- there is no
secret to put in .env at all. Verification instead fetches the project's
public keys from its JWKS endpoint, keyed by the `kid` in the token header.
`PyJWKClient` handles fetching, caching, and kid-matching.

Root cause of the intermittent "Could not verify the issued Supabase token"
failure (2026-09-22): `get_signing_key_from_jwt` makes a real outbound HTTPS
call to Supabase's JWKS endpoint on a cache miss, and that call was never
retried -- a single dropped/slow request (common on this dev stack's WSL2
virtualized network adapter, especially right after the host sleeps/resumes)
surfaced as a hard failure on the very next sign-in attempt. Restarting the
server "fixed" it only by coincidence (a fresh process + a few seconds'
delay before the next click), not because anything was actually reset --
the same blip could, and did, happen again on the fresh process too. Fix:
retry the fetch a couple of times with backoff before giving up for real,
plus a small `leeway` on `jwt.decode` so an isolated second or two of clock
drift between this box and Supabase doesn't also read as invalid.
"""

import logging
import time
from functools import lru_cache

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from apps.api.config import get_settings

logger = logging.getLogger(__name__)

_SUPPORTED_ALGORITHMS = ["ES256", "RS256"]

# Small, cheap tolerance for clock drift between this box and Supabase's
# auth server -- a token issued a moment "in the future" relative to a
# slightly-fast local clock shouldn't fail verification over a couple of
# seconds of skew.
_CLOCK_SKEW_LEEWAY_SECONDS = 10

# The JWKS fetch is a real network call to Supabase, made synchronously on
# a cache miss -- retried a few times with backoff before this is treated
# as a real failure, rather than failing hard on the first transient blip.
_JWKS_FETCH_MAX_ATTEMPTS = 3
_JWKS_FETCH_RETRY_BACKOFF_SECONDS = 0.5


@lru_cache
def _jwks_client() -> PyJWKClient:
    settings = get_settings()
    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)


def decode_supabase_jwt(token: str) -> dict:
    settings = get_settings()
    if not settings.supabase_url:
        raise HTTPException(status_code=503, detail="Auth is not configured yet")

    client = _jwks_client()
    connection_error: PyJWKClientConnectionError | None = None
    for attempt in range(1, _JWKS_FETCH_MAX_ATTEMPTS + 1):
        try:
            signing_key = client.get_signing_key_from_jwt(token)
        except PyJWKClientConnectionError as exc:
            connection_error = exc
            logger.warning(
                "JWKS fetch attempt %d/%d failed (will retry): %s", attempt, _JWKS_FETCH_MAX_ATTEMPTS, exc
            )
            if attempt < _JWKS_FETCH_MAX_ATTEMPTS:
                time.sleep(_JWKS_FETCH_RETRY_BACKOFF_SECONDS * attempt)
                continue
            logger.error("JWKS fetch failed after %d attempts", _JWKS_FETCH_MAX_ATTEMPTS)
            raise HTTPException(
                status_code=503, detail="Could not reach Supabase to verify sign-in -- please try again"
            ) from exc
        except jwt.PyJWTError as exc:
            # Without this, the real reason (bad signature, wrong kid, expired
            # exp, unsupported alg, ...) was previously discarded -- the caller
            # only ever saw the generic HTTPException below, both here and one
            # layer up in auth_service.py's re-wrap into a 502.
            logger.exception("Supabase JWT verification failed: %s", exc)
            raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

        try:
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=_SUPPORTED_ALGORITHMS,
                options={"verify_aud": False},
                leeway=_CLOCK_SKEW_LEEWAY_SECONDS,
            )
        except jwt.PyJWTError as exc:
            logger.exception("Supabase JWT verification failed: %s", exc)
            raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    # Unreachable: the loop above always either returns or raises.
    raise HTTPException(status_code=503, detail="Could not verify the issued Supabase token") from connection_error
