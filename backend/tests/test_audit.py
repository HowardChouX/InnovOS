"""
Tests for app/audit.py — audit logging to the audit_log table.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.audit import log_audit


class TestLogAudit:
    """log_audit() — inserts a row into audit_log."""

    def test_inserts_with_all_fields(self, monkeypatch):
        """All provided fields should be inserted correctly."""
        mock_db = MagicMock()
        monkeypatch.setattr("app.audit.get_db", lambda: mock_db)
        log_audit(
            user_id=1,
            username="testuser",
            action="delete",
            resource_type="knowledge_base",
            resource_id="42",
            detail={"reason": "user_request"},
            ip_address="192.168.1.1",
        )
        sql = mock_db.execute.call_args[0][0]
        params = mock_db.execute.call_args[0][1]
        assert "INSERT INTO audit_log" in sql
        assert params[0] == 1
        assert params[1] == "testuser"
        assert params[2] == "delete"
        assert params[3] == "knowledge_base"
        assert params[4] == "42"
        assert json.loads(params[5]) == {"reason": "user_request"}
        assert params[6] == "192.168.1.1"
        mock_db.commit.assert_called_once()

    def test_default_empty_strings(self, monkeypatch):
        """Omitting optional fields should use empty defaults."""
        mock_db = MagicMock()
        monkeypatch.setattr("app.audit.get_db", lambda: mock_db)
        log_audit(user_id=0, username="admin", action="login")
        params = mock_db.execute.call_args[0][1]
        assert params[3] == ""  # resource_type
        assert params[4] == ""  # resource_id
        assert json.loads(params[5]) == {}  # detail (empty dict)
        assert params[6] == ""  # ip_address

    def test_detail_serialized_to_json(self, monkeypatch):
        """The detail dict should be JSON-serialized before insert."""
        mock_db = MagicMock()
        monkeypatch.setattr("app.audit.get_db", lambda: mock_db)
        detail = {"key": "value", "nested": {"a": 1}}
        log_audit(user_id=1, username="u", action="update", detail=detail)
        params = mock_db.execute.call_args[0][1]
        assert json.loads(params[5]) == detail

    def test_system_user(self, monkeypatch):
        """Test with user_id=0 (system/admin user)."""
        mock_db = MagicMock()
        monkeypatch.setattr("app.audit.get_db", lambda: mock_db)
        log_audit(user_id=0, username="system", action="system_startup")
        params = mock_db.execute.call_args[0][1]
        assert params[0] == 0
        assert params[1] == "system"
        assert params[2] == "system_startup"

    def test_db_failure_logged_and_suppressed(self, monkeypatch):
        """If the DB operation fails, the exception should be caught and logged, not raised."""
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("connection lost")
        monkeypatch.setattr("app.audit.get_db", lambda: mock_db)
        # Should not raise
        log_audit(user_id=1, username="test", action="test")
        mock_db.commit.assert_not_called()

    def test_db_none_on_error(self, monkeypatch):
        """If get_db raises, the function should catch it (db is None in finally)."""
        monkeypatch.setattr("app.audit.get_db", MagicMock(side_effect=Exception("no db")))
        # Should not raise
        log_audit(user_id=1, username="test", action="test")

    def test_resource_id_stored_correctly(self, monkeypatch):
        """Resource ID should be stored in the audit log."""
        mock_db = MagicMock()
        monkeypatch.setattr("app.audit.get_db", lambda: mock_db)
        log_audit(user_id=1, username="u", action="view", resource_id="kb-42")
        params = mock_db.execute.call_args[0][1]
        assert params[4] == "kb-42"
