"""Unit tests for the circuit-breaker state machine.

The project's conftest.py installs an autouse `auto_mock_db` fixture
that monkeypatches `app.database.get_db` with a MagicMock. Our tests
must be `async def` to coexist with pytest-asyncio's `auto` mode.
"""
from __future__ import annotations

import pytest
from app.services import provider_health_service as mod


async def test_record_success_runs_sql(auto_mock_db):
    mod.record_success(provider_id="p1")
    sqls = " ".join(c[0] for c in auto_mock_db.cursor.executed)
    assert "consecutive_failures = 0" in sqls or "consecutive_failures=0" in sqls
    assert auto_mock_db.commit.called


async def test_record_failure_includes_threshold_and_cooldown(auto_mock_db):
    mod.record_failure(
        provider_id="p1",
        error_code="provider_5xx",
        failure_threshold=3,
        cooldown_seconds=300,
    )
    sqls = " ".join(c[0] for c in auto_mock_db.cursor.executed)
    assert ">= 3" in sqls
    assert "300" in sqls


async def test_record_failure_returns_int_count(auto_mock_db):
    auto_mock_db.cursor.fetchone.return_value = {"consecutive_failures": 5}
    n = mod.record_failure(
        provider_id="p1", error_code="x", failure_threshold=3, cooldown_seconds=60
    )
    assert n == 5


async def test_is_available_no_row_returns_true(auto_mock_db):
    auto_mock_db.cursor.fetchone.return_value = None
    assert mod.is_available(provider_id="p1") is True


async def test_reset_clears_cooldown(auto_mock_db):
    mod.reset(provider_id="p1")
    sqls = " ".join(c[0] for c in auto_mock_db.cursor.executed)
    assert "is_healthy = TRUE" in sqls or "is_healthy=TRUE" in sqls
    assert "cooldown_until = NULL" in sqls or "cooldown_until=NULL" in sqls
