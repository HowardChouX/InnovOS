"""
Pytest 配置 — 为所有测试自动隔离数据库依赖。

策略：
- monkeypatch 替换 app.database.get_db() / init_db()，避免需要 PostgreSQL
- 提供 model_registry fixture（加载一次，全局共享）
- 提供 mock_db fixture 返回可控的 fake 数据
- 提供 client fixture 用于 API 测试
"""
import os

# 在 app.core.config.settings 实例化前注入测试用环境变量。
# 这些 setdefault 不会覆盖 .env 里已有的值 —— 但 conftest 是测试专属入口，
# 所以这里用 强制赋值 让测试 100% 不命中真实 QQ SMTP,避免每次测试都把
# 退信推回用户邮箱。
os.environ.setdefault("INNOVOS_OTP_PEPPER", "test-pepper")
# 强制把 SMTP 指到本地 Mailpit(1025);即使本地没有 Mailpit,soft-fail
# 也会让 Python 端吞错,不会发真实邮件。
os.environ["SMTP_HOST"] = "localhost"
os.environ["SMTP_PORT"] = "1025"
os.environ["SMTP_USER"] = ""
os.environ["SMTP_PASSWORD"] = ""
os.environ["SMTP_FROM_EMAIL"] = "noreply@innovos.local"
os.environ["SMTP_SSL"] = "false"
os.environ["SMTP_TLS"] = "false"
os.environ["EMAIL_OTP_SOFT_FAIL"] = "true"

import sys
import json
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── 全局 Mock 数据库 ──
# Originally a sync generator with `yield`; converted to a no-yield
# autouse function in 2026-07-31 (model-service refactor) to work
# around pytest-asyncio 1.4.0's "did not yield a value" error in
# auto mode. The monkeypatch state is auto-restored by pytest
# after each test, so yield is not needed.
@pytest.fixture(autouse=True)
def auto_mock_db(monkeypatch, request):
    # NOTE: do NOT skip when DATABASE_URL is set — that defeats the
    # purpose of this autouse mock. Always apply the mock for tests.
    monkeypatch.setattr("app.database.init_db", lambda: None)
    mock_conn = MagicMock()
    mock_get_db = lambda: mock_conn
    monkeypatch.setattr("app.database.get_db", mock_get_db)
    # app.database has no Database class; guard with try/except for forward compat
    try:
        monkeypatch.setattr("app.database.Database", MagicMock)
    except AttributeError:
        pass
    # 预导入可能引用 get_db 的模块，确保 monkeypatch 生效
    # 注意:有些模块做 `from app.database import get_db`,需要直接 patch 该模块
    import app.api.models
    monkeypatch.setattr("app.api.models.get_db", mock_get_db)
    # 新增:2026-07-31 model-service refactor — services modules import get_db directly
    # Patch every module that imports get_db at module level. For modules
    # that import it lazily (e.g. inside a function), we use a sentinel
    # approach via sys.modules monkey-patching at the call site — easier
    # to just skip those.
    for mod_name in [
        "app.services.provider_health_service",
        "app.services.usage_logger",
        "app.services.failover_router",
        "app.services.usage_log_cleanup",
    ]:
        try:
            mod = __import__(mod_name, fromlist=["get_db"])
            monkeypatch.setattr(mod, "get_db", mock_get_db)
        except (ImportError, AttributeError):
            pass
    # Mock 环境变量读取 API Key（密钥不再来自 crypto 模块）
    # NOTE: 2026-07-31 model-service refactor removed _get_provider_api_key
    # (replaced with ApiKeyService.lease_key). Skip patching it.
    try:
        monkeypatch.setattr("app.algorithm.model_service._get_provider_api_key", lambda pid: f"env_key_{pid}" if pid else "")
    except AttributeError:
        pass
    # Return the mock_conn as a fixture value (for tests that request it)
    # — but since we removed yield, we attach to the request instead.
    request.node._auto_mock_db_conn = mock_conn
    return mock_conn


# ── FastAPI TestClient fixture ──
@pytest.fixture(scope="module")
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import models as models_router
    from app.auth import get_current_user

    test_app = FastAPI()
    test_app.include_router(models_router.router)
    test_app.dependency_overrides[get_current_user] = lambda: {"user_id": 1, "username": "test"}

    with TestClient(test_app) as c:
        yield c


# ── 模型注册表 fixture ──
@pytest.fixture(scope="session")
def registry():
    from app.algorithm.model_registry import model_registry
    model_registry.load()
    return model_registry


# ── 通用测试数据 ──
@pytest.fixture
def sample_provider_rows():
    return [
        {
            "id": 1, "provider_id": "silicon", "name": "SiliconFlow",
            "protocol": "openai", "api_host": "https://api.siliconflow.cn",
            "api_key_encrypted": "key_silicon",
            "models": json.dumps([
                {"id": "deepseek-ai/DeepSeek-V3", "capabilities": ["chat"]},
                {"id": "BAAI/bge-large-zh-v1.5", "capabilities": ["embedding"]},
                {"id": "BAAI/bge-reranker-v2-m3", "capabilities": ["rerank"]},
            ]),
            "is_enabled": 1, "priority": 1, "max_rpm": 60, "current_rpm": 0, "request_count": 0,
        },
        {
            "id": 2, "provider_id": "openai", "name": "OpenAI",
            "protocol": "openai", "api_host": "https://api.openai.com",
            "api_key_encrypted": "key_openai",
            "models": json.dumps([
                {"id": "gpt-4o", "capabilities": ["chat"]},
                {"id": "text-embedding-3-small", "capabilities": ["embedding"]},
                {"id": "text-embedding-3-large", "capabilities": ["embedding"]},
            ]),
            "is_enabled": 1, "priority": 2, "max_rpm": 500, "current_rpm": 10, "request_count": 100,
        },
        {
            "id": 3, "provider_id": "disabled_provider", "name": "Disabled",
            "protocol": "openai", "api_host": "https://api.example.com",
            "api_key_encrypted": "key_disabled",
            "models": json.dumps([{"id": "some-model", "capabilities": ["chat"]}]),
            "is_enabled": 0, "priority": 3,
        },
    ]


# ── SQL 捕获 Mock （用于 TDD 验证） ──
class CaptureCursor:
    """Mock cursor that records every SQL statement + params executed."""
    def __init__(self):
        self.history: list[tuple[str, object]] = []
        self.rowcount = 0
        self._fetchone_result: object = None
        self._fetchall_result: list[object] = []
        self._fetchone_queue: list[object] = []

    def add_fetchone_result(self, value: object):
        self._fetchone_queue.append(value)

    def execute(self, sql: str, params: object = None):
        self.history.append((sql, params))
        return self

    def fetchone(self):
        if self._fetchone_queue:
            return self._fetchone_queue.pop(0)
        return self._fetchone_result

    def fetchall(self):
        return self._fetchall_result

    def __getitem__(self, key: str):
        return None


class MockDB:
    """Mock Database wrapper that captures all SQL for assertion."""
    def __init__(self):
        self.cursor = CaptureCursor()
        self.all_sql: list[str] = []

    def execute(self, sql: str, params: object = None):
        self.all_sql.append(sql)
        return self.cursor.execute(sql, params)

    def commit(self): pass
    def rollback(self): pass
    def close(self): pass
    def closed(self) -> bool: return False


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def mock_db_all_providers(monkeypatch, sample_provider_rows):
    mock_conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = sample_provider_rows
    mock_conn.execute.return_value = cursor
    monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
    # models.py 使用 from app.database import get_db（本地引用），需要单独 patch
    monkeypatch.setattr("app.api.models.get_db", lambda: mock_conn)
    return mock_conn


# ── OTP 测试基础设施 ──
@pytest.fixture(autouse=True)
def _otp_pepper():
    """INNOVOS_OTP_PEPPER 已在 conftest 模块顶部注入（os.environ.setdefault），

    此 fixture 仅作为文档标记存在：所有测试自动获得 'test-pepper' 值，
    无需各测试文件单独设置。"""
    yield
