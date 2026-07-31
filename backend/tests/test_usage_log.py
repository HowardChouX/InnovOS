"""Tests for the usage logger (model_call_log writer)."""
from __future__ import annotations

import pytest
from app.services import usage_logger as mod


async def test_record_call_writes_expected_columns(auto_mock_db):
    mod.record_call(
        user_id=7,
        provider_id="p1",
        model_id="m1",
        purpose="chat",
        input_tokens=10,
        output_tokens=20,
        latency_ms=123,
        status_code=200,
        is_success=True,
        failover_from_provider=None,
        failover_attempt=1,
    )
    sql = auto_mock_db.execute.call_args_list[0][0][0]
    assert "INSERT INTO model_call_log" in sql
    assert "user_id" in sql
    assert "provider_id" in sql
    assert "failover_from_provider" in sql
    assert auto_mock_db.commit.called


async def test_record_call_swallows_exceptions(monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(mod, "get_db", boom)
    mod.record_call(
        user_id=1, provider_id="p", model_id="m", purpose="chat",
        input_tokens=0, output_tokens=0, latency_ms=0,
        status_code=500, is_success=False, failover_from_provider=None,
        failover_attempt=1,
    )
