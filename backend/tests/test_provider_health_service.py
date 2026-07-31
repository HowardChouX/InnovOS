"""Unit tests for the circuit-breaker state machine (uses autouse MagicMock)."""
from __future__ import annotations

import pytest
from app.services import provider_health_service as mod


async def test_record_success_runs_sql(auto_mock_db):
    mod.record_success(provider_id="p1")
    # MagicMock auto-creates the .execute attribute; the SQL is the
    # first positional arg of the first call.
    assert auto_mock_db.execute.called
    sql = auto_mock_db.execute.call_args_list[0][0][0]
    assert "consecutive_failures = 0" in sql or "consecutive_failures=0" in sql
    assert auto_mock_db.commit.called


async def test_record_failure_includes_threshold_and_cooldown(auto_mock_db):
    mod.record_failure(
        provider_id="p1",
        error_code="provider_5xx",
        failure_threshold=3,
        cooldown_seconds=300,
    )
    sql = auto_mock_db.execute.call_args_list[0][0][0]
    assert ">= 3" in sql
    assert "300" in sql


async def test_record_failure_returns_int_count(auto_mock_db):
    # db.execute(...).fetchone() chain — set on the execute return value
    auto_mock_db.execute.return_value.fetchone.return_value = {"consecutive_failures": 5}
    n = mod.record_failure(
        provider_id="p1", error_code="x", failure_threshold=3, cooldown_seconds=60
    )
    assert n == 5


async def test_is_available_no_row_returns_true(auto_mock_db):
    auto_mock_db.execute.return_value.fetchone.return_value = None
    assert mod.is_available(provider_id="p1") is True


async def test_reset_clears_cooldown(auto_mock_db):
    mod.reset(provider_id="p1")
    sql = auto_mock_db.execute.call_args_list[0][0][0]
    assert "is_healthy = TRUE" in sql or "is_healthy=TRUE" in sql
    assert "cooldown_until = NULL" in sql or "cooldown_until=NULL" in sql
