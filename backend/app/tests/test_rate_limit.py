"""Tests for app/utils/rate_limit.py

These tests verify the rate_limit module's key function logic and that
limit constants load correctly from environment variables.  They do NOT
make real HTTP requests — slowapi's own test suite covers the middleware
behaviour; we only test the pieces we wrote.
"""
import os
import importlib
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(auth_header: str | None = None, client_host: str = "1.2.3.4"):
    """Build a minimal mock Request object for the key function."""
    req = MagicMock()
    req.headers = {"Authorization": auth_header} if auth_header else {}
    req.client = MagicMock()
    req.client.host = client_host
    return req


def _make_bearer(sub: str) -> str:
    """Encode a minimal JWT with the given sub claim (no real signature needed
    for get_unverified_claims)."""
    from jose import jwt
    # Any secret works — we only test the unverified-claims path.
    return "Bearer " + jwt.encode({"sub": sub, "role": "doctor"}, "test-secret", algorithm="HS256")


# ---------------------------------------------------------------------------
# Key function tests
# ---------------------------------------------------------------------------

class TestAiKeyFunction:
    def test_valid_jwt_returns_user_key(self):
        from app.utils.rate_limit import _ai_key
        req = _make_request(auth_header=_make_bearer("42"))
        assert _ai_key(req) == "user:42"

    def test_missing_auth_falls_back_to_ip(self):
        from app.utils.rate_limit import _ai_key
        req = _make_request(auth_header=None, client_host="10.0.0.1")
        assert _ai_key(req) == "10.0.0.1"

    def test_malformed_bearer_falls_back_to_ip(self):
        from app.utils.rate_limit import _ai_key
        req = _make_request(auth_header="Bearer not.a.jwt", client_host="10.0.0.2")
        # jose will raise when decoding garbage; we expect the IP fallback
        result = _ai_key(req)
        assert result == "10.0.0.2"

    def test_non_bearer_scheme_falls_back_to_ip(self):
        from app.utils.rate_limit import _ai_key
        req = _make_request(auth_header="Basic dXNlcjpwYXNz", client_host="10.0.0.3")
        assert _ai_key(req) == "10.0.0.3"

    def test_different_users_get_different_keys(self):
        from app.utils.rate_limit import _ai_key
        req_a = _make_request(auth_header=_make_bearer("1"))
        req_b = _make_request(auth_header=_make_bearer("2"))
        assert _ai_key(req_a) != _ai_key(req_b)

    def test_no_client_returns_unknown(self):
        from app.utils.rate_limit import _ai_key
        req = _make_request()
        req.client = None  # edge case: client is None (unix socket etc.)
        result = _ai_key(req)
        assert result == "unknown"


# ---------------------------------------------------------------------------
# Limit constant tests
# ---------------------------------------------------------------------------

class TestRateLimitConstants:
    def test_defaults_are_loaded(self):
        from app.utils import rate_limit as rl
        assert "/" in rl.RATE_CHATBOT
        assert "/" in rl.RATE_AI_SUMMARY
        assert "/" in rl.RATE_AI_NOTES
        assert "/" in rl.RATE_AI_CLINICAL
        assert "/" in rl.RATE_OCR

    def test_env_override_is_respected(self, monkeypatch):
        monkeypatch.setenv("RATE_CHATBOT", "5/second")
        # Re-import the module so os.getenv() re-runs with the patched env.
        import app.utils.rate_limit as rl
        importlib.reload(rl)
        assert rl.RATE_CHATBOT == "5/second"
        # Restore defaults so other tests aren't affected.
        monkeypatch.delenv("RATE_CHATBOT", raising=False)
        importlib.reload(rl)
