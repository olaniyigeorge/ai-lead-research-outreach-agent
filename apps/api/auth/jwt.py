"""Verifies Supabase-issued access tokens.

New Supabase projects sign JWTs asymmetrically (ES256/RS256) with rotatable
"JWT Signing Keys" rather than a single shared HS256 secret -- there is no
secret to put in .env at all. Verification instead fetches the project's
public keys from its JWKS endpoint, keyed by the `kid` in the token header.
`PyJWKClient` handles fetching, caching, and kid-matching.
"""

import logging
from functools import lru_cache

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient

from apps.api.config import get_settings

logger = logging.getLogger(__name__)

_SUPPORTED_ALGORITHMS = ["ES256", "RS256"]


@lru_cache
def _jwks_client() -> PyJWKClient:
    settings = get_settings()
    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)


def decode_supabase_jwt(token: str) -> dict:
    settings = get_settings()
    if not settings.supabase_url:
        raise HTTPException(status_code=503, detail="Auth is not configured yet")

    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=_SUPPORTED_ALGORITHMS,
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        # Without this, the real reason (bad signature, wrong kid, expired
        # exp, unsupported alg, ...) was previously discarded -- the caller
        # only ever saw the generic HTTPException below, both here and one
        # layer up in auth_service.py's re-wrap into a 502.
        logger.exception("Supabase JWT verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    return payload
