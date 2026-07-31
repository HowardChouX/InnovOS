"""Tests for the model_call_log retention sweep."""
from __future__ import annotations

import pytest
from app.services import usage_log_cleanup as mod


async def test_run_deletes_old_rows(auto_mock_db):
    auto_mock_db.execute.return_value.rowcount = 42
    deleted = mod.run()
    assert deleted == 42
    sql = auto_mock_db.execute.call_args_list[0][0][0]
    params = auto_mock_db.execute.call_args_list[0][0][1]
    assert "DELETE FROM model_call_log" in sql
    assert "90" in params


async def test_run_respects_env_override(monkeypatch, auto_mock_db):
    monkeypatch.setenv("MODEL_CALL_LOG_RETENTION_DAYS", "30")
    auto_mock_db.execute.return_value.rowcount = 7
    deleted = mod.run()
    assert deleted == 7
    params = auto_mock_db.execute.call_args_list[0][0][1]
    assert "30" in params


async def test_retention_days_falls_back_to_90(monkeypatch):
    monkeypatch.delenv("MODEL_CALL_LOG_RETENTION_DAYS", raising=False)
    monkeypatch.setenv("MODEL_CALL_LOG_RETENTION_DAYS", "garbage")
    assert mod._retention_days() == 90
