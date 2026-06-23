"""
Tests for app/auth.py — JWT token creation, cookie management, token verification.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Response
from jose import JWTError, jwt

from app.auth import (
    ACCESS_TOKEN_EXPIRE_HOURS,
    SECRET_KEY,
    clear_token_cookie,
    create_access_token,
    set_token_cookie,
    _verify_admin_credentials,
)
from app.core.security import ALGORITHM

# Known key for deterministic testing
_TEST_SECRET = "test-secret-key-not-random-12345678"


@pytest.fixture(autouse=True)
def patch_secret_key(monkeypatch):
    """Use a deterministic secret key for all tests in this file."""
    monkeypatch.setattr("app.auth.SECRET_KEY", _TEST_SECRET)


class TestCreateAccessToken:
    """create_access_token() — JWT creation and payload verification."""

    def test_returns_string_token(self):
        token = create_access_token({"user_id": 1})
        assert isinstance(token, str)
        assert len(token) > 20

    def test_payload_contains_expected_fields(self):
        token = create_access_token({"user_id": 42, "role": "admin", "username": "testadmin"})
        payload = jwt.decode(token, _TEST_SECRET, algorithms=[ALGORITHM])
        assert payload["user_id"] == 42
        assert payload["role"] == "admin"
        assert payload["username"] == "testadmin"

    def test_expiry_is_24h(self):
        """Token exp claim should be ~24 hours from creation (within 3s tolerance)."""
        before = datetime.now(timezone.utc)
        token = create_access_token({"user_id": 1})
        after = datetime.now(timezone.utc)
        payload = jwt.decode(token, _TEST_SECRET, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        expected_min = before + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        expected_max = after + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        # Allow 3 second tolerance
        assert expected_min - timedelta(seconds=3) <= exp <= expected_max + timedelta(seconds=3), (
            f"Expected exp between {expected_min} and {expected_max}, got {exp}"
        )

    def test_dual_claim_user_id_to_sub(self):
        """When user_id is provided, sub is auto-populated from it."""
        token = create_access_token({"user_id": 99, "role": "user"})
        payload = jwt.decode(token, _TEST_SECRET, algorithms=[ALGORITHM])
        assert payload["sub"] == "99"
        assert payload["user_id"] == 99

    def test_dual_claim_sub_to_user_id(self):
        """When sub is provided, user_id is auto-populated from it."""
        token = create_access_token({"sub": "77", "role": "user"})
        payload = jwt.decode(token, _TEST_SECRET, algorithms=[ALGORITHM])
        assert payload["user_id"] == 77
        assert payload["sub"] == "77"

    def test_token_version_carried_through(self):
        """Token carries the token_version claim when provided."""
        token = create_access_token({"user_id": 1, "token_version": 2})
        payload = jwt.decode(token, _TEST_SECRET, algorithms=[ALGORITHM])
        assert payload["token_version"] == 2

    def test_empty_data_creates_token(self):
        """Even empty data dict should produce a token with just exp."""
        token = create_access_token({})
        payload = jwt.decode(token, _TEST_SECRET, algorithms=[ALGORITHM])
        assert "exp" in payload
        assert len(payload) >= 1


class TestTokenVerification:
    """Verification pattern used in get_current_user — valid, expired, bad signature."""

    def test_valid_token_returns_payload(self):
        token = create_access_token({"user_id": 1, "role": "admin"})
        payload = jwt.decode(token, _TEST_SECRET, algorithms=[ALGORITHM])
        assert payload["user_id"] == 1
        assert payload["role"] == "admin"

    def test_expired_token_raises(self):
        """A token with past exp should raise JWTError (ExpiredSignatureError)."""
        expired_payload = {
            "user_id": 1,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, _TEST_SECRET, algorithm=ALGORITHM)
        with pytest.raises(JWTError):
            jwt.decode(expired_token, _TEST_SECRET, algorithms=[ALGORITHM])

    def test_bad_signature_raises(self):
        """Decoding with wrong key raises JWTError."""
        token = create_access_token({"user_id": 1})
        with pytest.raises(JWTError):
            jwt.decode(token, "wrong-secret-key", algorithms=[ALGORITHM])

    def test_malformed_token_raises(self):
        """Garbage string should raise JWTError."""
        with pytest.raises(JWTError):
            jwt.decode("not.a.token", _TEST_SECRET, algorithms=[ALGORITHM])

    def test_token_missing_user_id(self):
        """Token without user_id - decode succeeds but payload lacks user_id."""
        token = jwt.encode({"role": "user", "exp": datetime.now(timezone.utc) + timedelta(days=1)}, _TEST_SECRET, algorithm=ALGORITHM)
        payload = jwt.decode(token, _TEST_SECRET, algorithms=[ALGORITHM])
        assert payload.get("user_id") is None


class TestAdminCredentials:
    """_verify_admin_credentials() — constant-time comparison."""

    def test_correct_credentials(self, monkeypatch):
        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER", "admin")
        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER_PASSWORD", "secret")
        assert _verify_admin_credentials("admin", "secret") is True

    def test_wrong_username(self, monkeypatch):
        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER", "admin")
        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER_PASSWORD", "secret")
        assert _verify_admin_credentials("wrong", "secret") is False

    def test_wrong_password(self, monkeypatch):
        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER", "admin")
        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER_PASSWORD", "secret")
        assert _verify_admin_credentials("admin", "wrong") is False

    def test_both_wrong(self, monkeypatch):
        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER", "admin")
        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER_PASSWORD", "secret")
        assert _verify_admin_credentials("bad", "creds") is False

    def test_empty_credentials(self, monkeypatch):
        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER", "")
        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER_PASSWORD", "")
        assert _verify_admin_credentials("admin", "secret") is False

    def test_uses_hmac_compare_digest(self, monkeypatch):
        """Verify the function uses hmac.compare_digest under the hood."""
        from unittest.mock import patch as mock_patch
        import hmac

        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER", "admin123")
        monkeypatch.setattr("app.auth.settings.FIRST_SUPERUSER_PASSWORD", "p@ssw0rd")
        original = hmac.compare_digest
        with mock_patch("app.auth.hmac.compare_digest", wraps=original) as mock_cmp:
            _verify_admin_credentials("admin123", "p@ssw0rd")
            assert mock_cmp.call_count == 2  # username + password


class TestCookieManagement:
    """set/clear __Host-token cookie functions."""

    def test_set_token_cookie_attributes(self):
        """set_token_cookie sets httpOnly, secure, samesite=lax, path=/."""
        response = Response()
        set_token_cookie(response, "my-token-value")
        cookie_header = response.headers.get("set-cookie", "")
        assert "__Host-token=my-token-value" in cookie_header
        lower = cookie_header.lower()
        assert "httponly" in lower
        assert "secure" in lower
        assert "samesite=lax" in lower

    def test_set_token_cookie_max_age(self):
        """The cookie max-age should match the token expiry in seconds."""
        response = Response()
        set_token_cookie(response, "token123")
        cookie_header = response.headers.get("set-cookie", "")
        expected_max_age = ACCESS_TOKEN_EXPIRE_HOURS * 3600
        assert f"max-age={expected_max_age}" in cookie_header.lower()

    def test_clear_token_cookie_expires_now(self):
        """clear_token_cookie sets empty value with max-age=0."""
        response = Response()
        clear_token_cookie(response)
        cookie_header = response.headers.get("set-cookie", "")
        lower = cookie_header.lower()
        assert "__host-token=" in lower
        assert "max-age=0" in lower

    def test_clear_token_cookie_secure_httponly(self):
        """Cleared cookie retains secure + httponly flags."""
        response = Response()
        clear_token_cookie(response)
        lower = response.headers.get("set-cookie", "").lower()
        assert "secure" in lower
        assert "httponly" in lower


class TestTokenVersionPattern:
    """JWT with token_version claim — used for token revocation."""

    def test_token_version_in_payload(self):
        """token_version should be present in JWT payload when provided."""
        token = create_access_token({"user_id": 1, "token_version": 1})
        payload = jwt.decode(token, _TEST_SECRET, algorithms=[ALGORITHM])
        assert payload["token_version"] == 1

    def test_token_version_default_not_present(self):
        """When token_version not provided, it should not be in payload."""
        token = create_access_token({"user_id": 1})
        payload = jwt.decode(token, _TEST_SECRET, algorithms=[ALGORITHM])
        assert "token_version" not in payload
