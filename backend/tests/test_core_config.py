"""
Tests for app/core/config.py — Pydantic Settings with environment-aware validation.
"""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings, parse_cors


class TestParseCors:
    """parse_cors() helper function."""

    def test_comma_separated_string(self):
        result = parse_cors("http://localhost,https://example.com")
        assert result == ["http://localhost", "https://example.com"]

    def test_single_origin_string(self):
        result = parse_cors("http://localhost:3000")
        assert result == ["http://localhost:3000"]

    def test_empty_string(self):
        result = parse_cors("")
        assert result == []

    def test_list_input(self):
        result = parse_cors(["http://a.com", "http://b.com"])
        assert result == ["http://a.com", "http://b.com"]

    def test_string_with_spaces(self):
        result = parse_cors(" http://a.com , http://b.com ")
        assert result == ["http://a.com", "http://b.com"]

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            parse_cors(42)


class TestSettingsDefaults:
    """Default values when no environment variables are set.

    NOTE: The .env file (loaded by pydantic-settings via env_file="../.env") sets
    several values. These tests either accept env-provided values or pass explicit
    constructor arguments to isolate test scenarios.
    """

    def test_default_project_name(self):
        s = Settings()
        assert s.PROJECT_NAME == "InnovOS"

    def test_default_api_prefix(self):
        s = Settings()
        assert s.API_V1_STR == "/api"

    def test_default_secret_key_from_env(self):
        """When INNOVOS_JWT_SECRET is set in .env, it's used (not auto-generated)."""
        s = Settings()
        assert s.SECRET_KEY is not None
        assert len(s.SECRET_KEY) > 0

    def test_postgres_defaults(self):
        s = Settings()
        assert s.POSTGRES_SERVER == "localhost"
        assert s.POSTGRES_PORT == 5432
        assert s.POSTGRES_USER == "innovos"
        assert s.POSTGRES_DB == "innovos"

    def test_database_url_auto_built(self):
        """DATABASE_URL is auto-built from components when not explicitly set."""
        s = Settings()
        assert s.POSTGRES_PASSWORD in s.DATABASE_URL
        assert "@localhost" in s.DATABASE_URL

    def test_explicit_database_url_takes_precedence(self):
        """When DATABASE_URL is passed explicitly, it should be used."""
        s = Settings(DATABASE_URL="postgresql://custom:pass@remote:9000/mydb")
        assert s.DATABASE_URL == "postgresql://custom:pass@remote:9000/mydb"

    def test_cors_origins_defaults_empty(self):
        s = Settings()
        assert s.BACKEND_CORS_ORIGINS == []

    def test_access_token_expires_24h(self):
        s = Settings()
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 60 * 24

    def test_s3_defaults(self):
        s = Settings()
        assert s.S3_ENDPOINT == ""
        assert s.S3_BUCKET == "innovos-files"
        assert s.S3_REGION == "us-east-1"

    def test_otp_defaults_present(self):
        s = Settings()
        assert s.OTP_TTL_SECONDS == 600
        assert s.OTP_MAX_ATTEMPTS == 5
        assert s.OTP_RESEND_COOLDOWN == 60
        assert s.EMAIL_OTP_SOFT_FAIL is False


class TestSettingsEnvAliases:
    """Settings should accept values via alternative env variable names."""

    def test_environment_via_env_alias(self):
        s = Settings(ENVIRONMENT="production", POSTGRES_PASSWORD="securepass",
                     BACKEND_CORS_ORIGINS=["https://example.com"])
        assert s.ENVIRONMENT == "production"


class TestSettingsDatabaseUrlAutoBuild:
    """DATABASE_URL auto-build from component fields."""

    def test_auto_build_custom_server(self):
        s = Settings(
            POSTGRES_SERVER="db.example.com",
            POSTGRES_PORT=15432,
            POSTGRES_USER="app_user",
            POSTGRES_DB="app_db",
            POSTGRES_PASSWORD="p@ss",
        )
        expected = "postgresql://app_user:p@ss@db.example.com:15432/app_db"
        assert s.DATABASE_URL == expected

    def test_auto_build_with_password(self):
        """When POSTGRES_PASSWORD is set explicitly, it should appear in URL."""
        s = Settings(POSTGRES_PASSWORD="my_pass")
        assert "my_pass" in s.DATABASE_URL


class TestSettingsProductionValidation:
    """Production environment should enforce stricter validation."""

    def test_empty_postgres_password_raises_in_production(self):
        with pytest.raises(ValueError, match="POSTGRES_PASSWORD must be set in production"):
            Settings(ENVIRONMENT="production", BACKEND_CORS_ORIGINS=["https://example.com"],
                     POSTGRES_PASSWORD="")

    def test_empty_cors_origins_raises_in_production(self):
        with pytest.raises(ValueError, match="BACKEND_CORS_ORIGINS must be configured"):
            Settings(ENVIRONMENT="production", POSTGRES_PASSWORD="securepass",
                     BACKEND_CORS_ORIGINS=[])

    def test_both_required_fields_set_in_production(self):
        s = Settings(
            ENVIRONMENT="production",
            POSTGRES_PASSWORD="securepass",
            BACKEND_CORS_ORIGINS=["https://myapp.com"],
        )
        assert s.ENVIRONMENT == "production"
        assert s.POSTGRES_PASSWORD == "securepass"

    def test_development_does_not_require_password(self):
        s = Settings(ENVIRONMENT="development", POSTGRES_PASSWORD="")
        assert s.POSTGRES_PASSWORD == ""


class TestSettingsDefaultSecretCheck:
    """_check_default_secret should warn in dev but raise in production."""

    def test_changethis_warns_in_dev(self):
        with pytest.warns(UserWarning, match="changethis"):
            Settings(ENVIRONMENT="development", POSTGRES_PASSWORD="changethis")

    def test_changethis_raises_in_production(self):
        with pytest.raises(ValueError, match="changethis"):
            Settings(
                ENVIRONMENT="production",
                POSTGRES_PASSWORD="realpass",
                BACKEND_CORS_ORIGINS=["https://example.com"],
                SECRET_KEY="changethis",
            )
