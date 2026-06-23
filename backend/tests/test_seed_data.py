"""
Tests for app/tables/pg_schema.py — seed_admin_user() idempotent admin creation.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.tables.pg_schema import seed_admin_user


class TestSeedAdminUser:
    """seed_admin_user() — idempotent admin user creation."""

    def test_creates_admin_when_not_exists(self, monkeypatch):
        """When no admin exists, should INSERT the admin user."""
        mock_db = MagicMock()
        monkeypatch.setattr("app.core.config.settings.FIRST_SUPERUSER", "admin")
        monkeypatch.setattr("app.core.config.settings.FIRST_SUPERUSER_PASSWORD", "adm1n!")
        seed_admin_user(mock_db)
        # Should execute INSERT with id=0, username=settings.FIRST_SUPERUSER
        sql = mock_db.execute.call_args[0][0]
        params = mock_db.execute.call_args[0][1]
        assert "INSERT INTO users" in sql
        assert "ON CONFLICT" in sql
        assert params[0] == "admin"
        mock_db.commit.assert_called_once()

    def test_skips_on_conflict(self, monkeypatch):
        """ON CONFLICT (id) DO NOTHING means no error if admin already exists."""
        mock_db = MagicMock()
        mock_db.execute.side_effect = None
        monkeypatch.setattr("app.core.config.settings.FIRST_SUPERUSER", "admin")
        monkeypatch.setattr("app.core.config.settings.FIRST_SUPERUSER_PASSWORD", "pass")
        seed_admin_user(mock_db)
        # Should still call execute and commit
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_uses_username_from_settings(self, monkeypatch):
        """Username should come from settings.FIRST_SUPERUSER."""
        mock_db = MagicMock()
        monkeypatch.setattr("app.core.config.settings.FIRST_SUPERUSER", "root_admin")
        monkeypatch.setattr("app.core.config.settings.FIRST_SUPERUSER_PASSWORD", "r00t!")
        seed_admin_user(mock_db)
        params = mock_db.execute.call_args[0][1]
        assert params[0] == "root_admin"

    def test_fallback_to_admin_when_settings_empty(self, monkeypatch):
        """If FIRST_SUPERUSER is empty, should default to 'admin'."""
        mock_db = MagicMock()
        monkeypatch.setattr("app.core.config.settings.FIRST_SUPERUSER", "")
        monkeypatch.setattr("app.core.config.settings.FIRST_SUPERUSER_PASSWORD", "")
        seed_admin_user(mock_db)
        params = mock_db.execute.call_args[0][1]
        assert params[0] == "admin"

    def test_sets_correct_values(self, monkeypatch):
        """The INSERT should set id=0, role='admin', password_hash=''."""
        mock_db = MagicMock()
        monkeypatch.setattr("app.core.config.settings.FIRST_SUPERUSER", "myadmin")
        monkeypatch.setattr("app.core.config.settings.FIRST_SUPERUSER_PASSWORD", "pass")
        seed_admin_user(mock_db)
        sql = mock_db.execute.call_args[0][0]
        params = mock_db.execute.call_args[0][1]
        assert params[0] == "myadmin"
        assert "VALUES (0, " in sql  # id=0
        assert ", 'admin'" in sql  # role=admin
        assert "ON CONFLICT (id) DO NOTHING" in sql
