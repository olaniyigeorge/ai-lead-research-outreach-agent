from types import SimpleNamespace
from unittest.mock import patch

import jwt as pyjwt
import pytest
from fastapi import HTTPException
from jwt.exceptions import PyJWKClientConnectionError

from apps.api.auth import jwt as jwt_module
from apps.api.auth.jwt import decode_supabase_jwt


class _FakeSigningKey:
    def __init__(self, key: str):
        self.key = key


@pytest.fixture(autouse=True)
def _fake_settings():
    with patch.object(jwt_module, "get_settings", lambda: SimpleNamespace(supabase_url="https://project.supabase.co")):
        yield


def _fake_client(get_signing_key_from_jwt):
    return SimpleNamespace(get_signing_key_from_jwt=get_signing_key_from_jwt)


def test_decode_succeeds_on_first_try(monkeypatch):
    calls = {"n": 0}

    def fake_get_key(token):
        calls["n"] += 1
        return _FakeSigningKey("k")

    with patch.object(jwt_module, "_jwks_client", lambda: _fake_client(fake_get_key)):
        with patch.object(pyjwt, "decode", lambda *a, **k: {"sub": "1", "email": "a@b.com"}):
            payload = decode_supabase_jwt("token")

    assert payload == {"sub": "1", "email": "a@b.com"}
    assert calls["n"] == 1


def test_decode_retries_transient_jwks_connection_errors_then_succeeds():
    calls = {"n": 0}

    def fake_get_key(token):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PyJWKClientConnectionError("network blip")
        return _FakeSigningKey("k")

    with (
        patch.object(jwt_module, "_jwks_client", lambda: _fake_client(fake_get_key)),
        patch.object(jwt_module.time, "sleep", lambda _: None),
        patch.object(pyjwt, "decode", lambda *a, **k: {"sub": "1", "email": "a@b.com"}),
    ):
        payload = decode_supabase_jwt("token")

    assert payload == {"sub": "1", "email": "a@b.com"}
    assert calls["n"] == 3


def test_decode_gives_up_after_max_attempts_as_a_503():
    def fake_get_key(token):
        raise PyJWKClientConnectionError("still down")

    with (
        patch.object(jwt_module, "_jwks_client", lambda: _fake_client(fake_get_key)),
        patch.object(jwt_module.time, "sleep", lambda _: None),
    ):
        with pytest.raises(HTTPException) as exc_info:
            decode_supabase_jwt("token")

    assert exc_info.value.status_code == 503


def test_decode_does_not_retry_a_genuinely_invalid_token():
    calls = {"n": 0}

    def fake_get_key(token):
        calls["n"] += 1
        return _FakeSigningKey("k")

    def fake_decode(*a, **k):
        raise pyjwt.InvalidSignatureError("bad signature")

    with (
        patch.object(jwt_module, "_jwks_client", lambda: _fake_client(fake_get_key)),
        patch.object(pyjwt, "decode", fake_decode),
    ):
        with pytest.raises(HTTPException) as exc_info:
            decode_supabase_jwt("token")

    assert exc_info.value.status_code == 401
    assert calls["n"] == 1
