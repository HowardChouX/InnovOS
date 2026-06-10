"""
Pytest 配置 — 为所有测试自动隔离数据库依赖。

策略：
- monkeypatch 替换 app.database.get_db() / init_db()，避免需要 PostgreSQL
- 提供 model_registry fixture（加载一次，全局共享）
- 提供 mock_db fixture 返回可控的 fake 数据
- 提供 client fixture 用于 API 测试
"""
import os
import sys
import json
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── 全局 Mock 数据库 ──
@pytest.fixture(autouse=True)
def auto_mock_db(monkeypatch):
    if os.getenv("DATABASE_URL", "").startswith("postgresql"):
        return
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
    import app.api.models
    monkeypatch.setattr("app.api.models.get_db", mock_get_db)
    monkeypatch.setattr("app.algorithm.crypto.decrypt_key", lambda x: f"decrypted_{x}" if x else "")
    yield mock_conn


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
