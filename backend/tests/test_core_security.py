"""
Tests for app/core/security.py — password hashing and JWT creation utilities.
"""

import re
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import bcrypt
import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    get_password_hash,
    verify_password,
)


class TestVerifyPassword:
    """verify_password() — bcrypt password verification."""

    def test_correct_password_returns_true(self):
        password = "my_secure_password"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        assert verify_password(password, hashed) is True

    def test_wrong_password_returns_false(self):
        password = "correct_password"
        wrong = "wrong_password"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        assert verify_password(wrong, hashed) is False

    def test_empty_password(self):
        hashed = bcrypt.hashpw(b"", bcrypt.gensalt()).decode()
        assert verify_password("", hashed) is True

    def test_empty_string_wrong_password(self):
        hashed = bcrypt.hashpw(b"somepass", bcrypt.gensalt()).decode()
        assert verify_password("", hashed) is False

    def test_special_characters(self):
        password = "P@ssw0rd!~#$%^&*()_+-=[]{}|;:',.<>?/"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        assert verify_password(password, hashed) is True

    def test_unicode_password(self):
        password = "密码测试🔑"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        assert verify_password(password, hashed) is True

    def test_password_at_72_char_boundary(self):
        """bcrypt truncates at 72 bytes — test at boundary."""
        password = "a" * 72
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        assert verify_password(password, hashed) is True


class TestGetPasswordHash:
    """get_password_hash() — bcrypt password hashing."""

    def test_returns_non_empty_hash(self):
        hashed = get_password_hash("my_password")
        assert isinstance(hashed, str)
        assert len(hashed) > 20

    def test_hash_starts_with_bcrypt_prefix(self):
        hashed = get_password_hash("my_password")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$") or hashed.startswith("$2y$")

    def test_hash_has_correct_format(self):
        """Bcrypt hash format: $2b$<cost>$<22-char-salt><31-char-hash>."""
        hashed = get_password_hash("my_password")
        pattern = r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$"
        assert re.match(pattern, hashed) is not None, f"Hash {hashed} does not match bcrypt format"

    def test_hash_is_deterministic_with_salt(self):
        """Each call should produce a different hash (different salt)."""
        hash1 = get_password_hash("same_password")
        hash2 = get_password_hash("same_password")
        assert hash1 != hash2

    def test_round_trip(self):
        """Hashing then verifying should succeed."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_empty_password_hash(self):
        hashed = get_password_hash("")
        assert isinstance(hashed, str)
        assert len(hashed) > 20
        assert verify_password("", hashed) is True

    def test_cost_factor_default(self):
        """Default bcrypt cost should be >= 10."""
        hashed = get_password_hash("password")
        cost = int(hashed.split("$")[2])
        assert cost >= 10


class TestCreateAccessToken:
    """create_access_token() from security.py (distinct from auth.py version)."""

    def test_returns_string_token(self):
        token = create_access_token(subject="1")
        assert isinstance(token, str)
        assert len(token) > 10

    def test_payload_contains_sub_and_exp(self):
        token = create_access_token(subject="42")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "42"
        assert "exp" in payload

    def test_expiry_respects_custom_delta(self):
        token = create_access_token(subject="1", expires_delta=timedelta(hours=1))
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected = datetime.now(timezone.utc) + timedelta(hours=1)
        # Allow 5 second tolerance
        assert abs((exp - expected).total_seconds()) < 5

    def test_default_expiry_is_24h(self):
        token = create_access_token(subject="1")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        assert abs((exp - expected).total_seconds()) < 5

    def test_int_subject_converted_to_string(self):
        token = create_access_token(subject=123)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "123"
