"""Regression test: failover_router 中 model_providers.is_enabled 用 = 1 (INTEGER),
不是 = TRUE (BOOLEAN)。

``model_providers.is_enabled`` 列是 INTEGER,而 ``user_model_services.is_enabled``
是 BOOLEAN — 这两条 WHERE 必须区别对待。
"""
from __future__ import annotations

import inspect

from app.services import failover_router as failover_router_module


class TestFailoverRouterIsEnabledLiterals:
    def test_mp_is_enabled_uses_integer_one(self):
        """model_providers.is_enabled 是 INTEGER,WHERE 必须用 1。"""
        src = inspect.getsource(failover_router_module)
        assert "mp.is_enabled = 1" in src, (
            "model_providers.is_enabled 是 INTEGER 列,"
            "WHERE 子句必须用 = 1 而不是 = TRUE (否则 PG 报 DatatypeMismatch)"
        )
        # 防回退:不应该再用 TRUE
        assert "mp.is_enabled = TRUE" not in src

    def test_ums_is_enabled_uses_boolean_true(self):
        """user_model_services.is_enabled 是 BOOLEAN,WHERE 用 = TRUE。"""
        src = inspect.getsource(failover_router_module)
        assert "ums.is_enabled = TRUE" in src, (
            "user_model_services.is_enabled 是 BOOLEAN 列,WHERE 子句必须用 = TRUE"
        )
