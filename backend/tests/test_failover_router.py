"""Tests for the per-user failover queue walker."""
from __future__ import annotations

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
    monkeypatch.setattr(mod, "_load_queue", lambda user_id: [])
    monkeypatch.setattr(mod, "load_api_key_cipher", lambda: _FakeCipher())
    router = mod.FailoverRouter()
    with pytest.raises(mod.NoProvidersConfiguredError):
        await router.call(user_id=1, purpose="chat", messages=[])


async def test_first_entry_succeeds(monkeypatch, auto_mock_db):
    monkeypatch.setattr(mod, "_load_queue", lambda user_id: [
        {"provider_id": "p1", "api_host": "https://a", "api_model": "m1",
         "api_key_ciphertext": b"", "api_key_nonce": b"", "encryption_version": 1,
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
    monkeypatch.setattr(mod, "_load_queue", lambda user_id: [
        {"provider_id": "p1", "api_host": "https://a", "api_model": "m1",
         "api_key_ciphertext": b"", "api_key_nonce": b"", "encryption_version": 1,
         "is_healthy": True, "cooldown_until": None},
        {"provider_id": "p2", "api_host": "https://b", "api_model": "m2",
         "api_key_ciphertext": b"", "api_key_nonce": b"", "encryption_version": 1,
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
    monkeypatch.setattr(mod, "_load_queue", lambda user_id: [
        {"provider_id": "p1", "api_host": "https://a", "api_model": "m1",
         "api_key_ciphertext": b"", "api_key_nonce": b"", "encryption_version": 1,
         "is_healthy": True, "cooldown_until": None},
        {"provider_id": "p2", "api_host": "https://b", "api_model": "m2",
         "api_key_ciphertext": b"", "api_key_nonce": b"", "encryption_version": 1,
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
