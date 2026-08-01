"""Tests for the per-user failover queue walker."""
from __future__ import annotations

import inspect

import pytest
from app.services import failover_router as mod


class _FakeRow(dict):
    pass


def _row(**kw):
    return _FakeRow(kw)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed: list[tuple] = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        return self

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows=None):
        self.cursor = _FakeCursor(rows or [])

    def execute(self, sql, params=()):
        return self.cursor.execute(sql, params)

    def commit(self):
        pass

    def close(self):
        pass


class _FakeCipher:
    def decrypt(self, *, ciphertext, nonce, encryption_version, provider_id, key_id):
        return f"plain_{provider_id}"


async def test_empty_queue_raises_no_providers(monkeypatch, auto_mock_db):
    monkeypatch.setattr(mod, "_load_queue", lambda user_id, **kw: [])
    monkeypatch.setattr(mod, "load_api_key_cipher", lambda: _FakeCipher())
    router = mod.FailoverRouter()
    with pytest.raises(mod.NoProvidersConfiguredError):
        await router.call(user_id=1, purpose="chat", messages=[])


async def test_first_entry_succeeds(monkeypatch, auto_mock_db):
    monkeypatch.setattr(mod, "_load_queue", lambda user_id, **kw: [
        {"provider_id": "p1", "capability": "chat", "api_host": "https://a", "api_model": "m1",
         "key_id": 1, "api_key_ciphertext": b"", "api_key_nonce": b"", "encryption_version": 1,
         "is_healthy": True, "cooldown_until": None},
    ])
    monkeypatch.setattr(mod, "load_api_key_cipher", lambda: _FakeCipher())
    async def stub(provider_id, model_id, messages, **_):
        return {"content": "hello", "input_tokens": 1, "output_tokens": 2}
    monkeypatch.setattr(mod, "_call_one", stub)
    health = _StubHealth()
    monkeypatch.setattr(mod, "health_svc", health)

    router = mod.FailoverRouter()
    result = await router.call(user_id=1, purpose="chat", messages=[])
    assert result["content"] == "hello"
    assert result["provider_id"] == "p1"
    assert result["failover_attempts"] == 1


async def test_falls_over_to_second_after_failure(monkeypatch, auto_mock_db):
    monkeypatch.setattr(mod, "_load_queue", lambda user_id, **kw: [
        {"provider_id": "p1", "capability": "chat", "api_host": "https://a", "api_model": "m1",
         "key_id": 1, "api_key_ciphertext": b"", "api_key_nonce": b"", "encryption_version": 1,
         "is_healthy": True, "cooldown_until": None},
        {"provider_id": "p2", "capability": "chat", "api_host": "https://b", "api_model": "m2",
         "key_id": 2, "api_key_ciphertext": b"", "api_key_nonce": b"", "encryption_version": 1,
         "is_healthy": True, "cooldown_until": None},
    ])
    monkeypatch.setattr(mod, "load_api_key_cipher", lambda: _FakeCipher())
    async def stub(provider_id, model_id, messages, **_):
        if provider_id == "p1":
            raise RuntimeError("upstream HTTP 503: bad gateway")
        return {"content": "from p2", "input_tokens": 1, "output_tokens": 1}
    monkeypatch.setattr(mod, "_call_one", stub)
    health = _StubHealth()
    monkeypatch.setattr(mod, "health_svc", health)

    router = mod.FailoverRouter()
    result = await router.call(user_id=1, purpose="chat", messages=[])
    assert result["content"] == "from p2"
    assert result["provider_id"] == "p2"
    assert health.failures == [("p1",)]
    assert health.successes == ["p2"]


async def test_max_attempts_caps_retries(monkeypatch, auto_mock_db):
    monkeypatch.setattr(mod, "_load_queue", lambda user_id, **kw: [
        {"provider_id": "p1", "capability": "chat", "api_host": "https://a", "api_model": "m1",
         "key_id": 1, "api_key_ciphertext": b"", "api_key_nonce": b"", "encryption_version": 1,
         "is_healthy": True, "cooldown_until": None},
        {"provider_id": "p2", "capability": "chat", "api_host": "https://b", "api_model": "m2",
         "key_id": 2, "api_key_ciphertext": b"", "api_key_nonce": b"", "encryption_version": 1,
         "is_healthy": True, "cooldown_until": None},
    ])
    monkeypatch.setattr(mod, "load_api_key_cipher", lambda: _FakeCipher())
    async def always_fail(provider_id, model_id, messages, **_):
        raise RuntimeError("upstream HTTP 500: internal server error")
    monkeypatch.setattr(mod, "_call_one", always_fail)
    monkeypatch.setattr(mod, "health_svc", _StubHealth())

    router = mod.FailoverRouter(max_attempts=2)
    with pytest.raises(mod.AllProvidersFailedError):
        await router.call(user_id=1, purpose="chat", messages=[])


def test_load_queue_filters_by_capability(monkeypatch):
    """_load_queue must return only rows matching the requested capability."""
    # SQL 层面必须真正按 ums.capability 过滤（不能只靠 Python 侧过滤）
    src = inspect.getsource(mod._load_queue)
    assert "ums.capability = %s" in src, (
        "_load_queue 的 SQL WHERE 子句必须包含 ums.capability = %s"
    )

    all_rows = [
        _row(
            provider_id="deepseek",
            capability="chat",
            api_host="https://api.deepseek.com",
            api_model="deepseek-chat",
            key_id=1,
            api_key_ciphertext=b"enc_chat",
            api_key_nonce=b"nonce_chat",
            encryption_version=1,
            is_healthy=True,
            cooldown_until=None,
        ),
        _row(
            provider_id="deepseek",
            capability="embedding",
            api_host="https://api.deepseek.com",
            api_model="deepseek-embed",
            key_id=1,
            api_key_ciphertext=b"enc_embed",
            api_key_nonce=b"nonce_embed",
            encryption_version=1,
            is_healthy=True,
            cooldown_until=None,
        ),
        _row(
            provider_id="openai",
            capability="chat",
            api_host="https://api.openai.com",
            api_model="gpt-4o",
            key_id=2,
            api_key_ciphertext=b"enc_chat2",
            api_key_nonce=b"nonce_chat2",
            encryption_version=1,
            is_healthy=True,
            cooldown_until=None,
        ),
    ]

    class _FakeFilteringCursor(_FakeCursor):
        def execute(self, sql, params=()):
            self.executed.append((sql, params))
            # Simulate SQL WHERE capability filter by selecting matching rows
            if len(params) >= 2 and isinstance(params[1], str):
                cap = params[1]
                self._rows = [r for r in self._all_rows if r.get("capability") == cap]
            return self
        def __init__(self, rows):
            self._all_rows = rows
            self._rows = rows
            self.executed = []

    class _FakeFilteringConn(_FakeConn):
        def __init__(self, rows):
            self.cursor = _FakeFilteringCursor(rows)
        def execute(self, sql, params=()):
            return self.cursor.execute(sql, params)

    fake_conn = _FakeFilteringConn(all_rows)
    monkeypatch.setattr(mod, "get_db", lambda: fake_conn)
    monkeypatch.setattr(mod, "health_svc", _StubHealth())

    # chat capability: should return 2 rows (deepseek chat + openai chat)
    chat_queue = mod._load_queue(user_id=10, capability="chat")
    assert len(chat_queue) == 2
    assert all(r["capability"] == "chat" for r in chat_queue)
    provider_ids = {r["provider_id"] for r in chat_queue}
    assert provider_ids == {"deepseek", "openai"}

    # embedding capability: should return 1 row (deepseek embedding)
    embed_queue = mod._load_queue(user_id=10, capability="embedding")
    assert len(embed_queue) == 1
    assert embed_queue[0]["provider_id"] == "deepseek"
    assert embed_queue[0]["capability"] == "embedding"

    # Verify SQL was called with the correct capability parameter
    assert len(fake_conn.cursor.executed) == 2
    _sql1, params1 = fake_conn.cursor.executed[0]
    assert params1 == (10, "chat")
    _sql2, params2 = fake_conn.cursor.executed[1]
    assert params2 == (10, "embedding")


class _StubHealth:
    def __init__(self):
        self.failures: list[tuple] = []
        self.successes: list[str] = []

    def record_failure(self, *, provider_id, error_code, failure_threshold, cooldown_seconds):
        self.failures.append((provider_id,))

    def record_success(self, *, provider_id):
        self.successes.append(provider_id)

    def is_available(self, *, provider_id):
        return True
