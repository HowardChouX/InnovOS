"""
Tests for app/algorithm/key_manager.py — API Key Manager with env-based key loading.

NOTE: Provider IDs are UPPERCASE because _load_keys_from_env upper-cases env var names.
The .env file sets AI_SILICON_API_KEY and AI_DEEPSEEK_API_KEY (empty), which affects
test state. Tests explicitly manage env vars to ensure isolation.
"""

from unittest.mock import patch

import pytest

from app.algorithm.key_manager import APIKeyManager


@pytest.fixture
def manager():
    """Return a fresh APIKeyManager for each test."""
    return APIKeyManager()


@pytest.fixture(autouse=True)
def clean_ai_env(monkeypatch):
    """Remove all AI_* env vars before each test to ensure clean state."""
    # The .env file loads AI_SILICON_API_KEY and AI_DEEPSEEK_API_KEY (both empty).
    # Remove them for clean test isolation.
    import os
    for key in list(os.environ.keys()):
        if key.startswith("AI_") and key.endswith("_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        if key.startswith("AI_") and key.endswith("_API_HOST"):
            monkeypatch.delenv(key, raising=False)
        if key.startswith("AI_") and key.endswith("_API_MODEL"):
            monkeypatch.delenv(key, raising=False)
    yield


class TestLoadKeysFromEnv:
    """APIKeyManager._load_keys_from_env() — parsing AI_{ID}_API_KEY env vars."""

    def test_single_key(self, manager, monkeypatch):
        monkeypatch.setenv("AI_SILICON_API_KEY", "sk-silicon-abc")
        result = manager._load_keys_from_env()
        assert "SILICON" in result
        assert len(result["SILICON"]) == 1
        assert result["SILICON"][0]["api_key"] == "sk-silicon-abc"
        assert result["SILICON"][0]["key_index"] == 0

    def test_multiple_keys_same_provider(self, manager, monkeypatch):
        # NOTE: The code expects AI_{PROVIDER}_{N}_API_KEY pattern (index before _API_KEY)
        monkeypatch.setenv("AI_SILICON_1_API_KEY", "sk-silicon-1")
        monkeypatch.setenv("AI_SILICON_2_API_KEY", "sk-silicon-2")
        result = manager._load_keys_from_env()
        assert "SILICON" in result
        assert len(result["SILICON"]) == 2
        keys_by_index = {k["key_index"]: k["api_key"] for k in result["SILICON"]}
        assert keys_by_index[1] == "sk-silicon-1"
        assert keys_by_index[2] == "sk-silicon-2"

    def test_multiple_providers(self, manager, monkeypatch):
        monkeypatch.setenv("AI_SILICON_API_KEY", "sk-silicon")
        monkeypatch.setenv("AI_DEEPSEEK_API_KEY", "sk-deepseek")
        monkeypatch.setenv("AI_OPENAI_API_KEY", "sk-openai")
        result = manager._load_keys_from_env()
        assert set(result.keys()) == {"SILICON", "DEEPSEEK", "OPENAI"}
        assert result["SILICON"][0]["api_key"] == "sk-silicon"
        assert result["DEEPSEEK"][0]["api_key"] == "sk-deepseek"
        assert result["OPENAI"][0]["api_key"] == "sk-openai"

    def test_mixed_indexed_and_non_indexed(self, manager, monkeypatch):
        """Both AI_SILICON_API_KEY and AI_SILICON_1_API_KEY should be separate keys."""
        monkeypatch.setenv("AI_SILICON_API_KEY", "sk-default")
        monkeypatch.setenv("AI_SILICON_1_API_KEY", "sk-indexed")
        result = manager._load_keys_from_env()
        assert len(result["SILICON"]) == 2
        indices = {k["key_index"] for k in result["SILICON"]}
        assert indices == {0, 1}

    def test_ignore_non_ai_vars(self, manager, monkeypatch):
        monkeypatch.setenv("AI_SILICON_API_KEY", "sk-valid")
        monkeypatch.setenv("DATABASE_URL", "postgres://...")
        monkeypatch.setenv("PATH", "/usr/bin")
        result = manager._load_keys_from_env()
        assert "SILICON" in result
        assert len(result) == 1  # Only AI_*_API_KEY vars

    def test_ignore_partial_prefix(self, manager, monkeypatch):
        """Var starting with AI_ but not ending with _API_KEY should be skipped."""
        monkeypatch.setenv("AI_SILICON_API_KEY", "valid")
        monkeypatch.setenv("AI_SOMETHING_ELSE", "skip")
        result = manager._load_keys_from_env()
        assert "SILICON" in result
        assert "SOMETHING" not in result

    def test_env_var_with_host_and_model(self, manager, monkeypatch):
        """API_HOST and API_MODEL env vars should be picked up."""
        monkeypatch.setenv("AI_SILICON_API_KEY", "sk-key")
        monkeypatch.setenv("AI_SILICON_API_HOST", "https://custom.api.com")
        monkeypatch.setenv("AI_SILICON_API_MODEL", "gpt-4")
        result = manager._load_keys_from_env()
        entry = result["SILICON"][0]
        assert entry["api_host"] == "https://custom.api.com"
        assert entry["api_model"] == "gpt-4"

    def test_no_ai_keys_returns_empty(self, manager):
        """When no AI_*_API_KEY vars exist, result should be empty."""
        result = manager._load_keys_from_env()
        assert result == {}

    def test_provider_id_with_underscore(self, manager, monkeypatch):
        """Provider IDs with underscores like 'text_ai' should work."""
        monkeypatch.setenv("AI_TEXT_AI_API_KEY", "sk-text")
        result = manager._load_keys_from_env()
        assert "TEXT_AI" in result
        assert result["TEXT_AI"][0]["api_key"] == "sk-text"
        assert result["TEXT_AI"][0]["id"] == "env_TEXT_AI_0"

    def test_empty_value_in_env(self, manager, monkeypatch):
        """AI_SILICON_API_KEY set but empty should still be included."""
        monkeypatch.setenv("AI_SILICON_API_KEY", "")
        result = manager._load_keys_from_env()
        assert "SILICON" in result
        assert result["SILICON"][0]["api_key"] == ""


class TestGetNextKey:
    """APIKeyManager._get_next_key() / get_key_for_request() — key selection."""

    @pytest.mark.asyncio
    async def test_get_key_for_specified_provider(self, manager, monkeypatch):
        monkeypatch.setenv("AI_OPENAI_API_KEY", "sk-openai")
        monkeypatch.setenv("AI_SILICON_API_KEY", "sk-silicon")
        key = await manager.get_key_for_request(provider_id="OPENAI")
        assert key["api_key"] == "sk-openai"
        assert key["id"] == "env_OPENAI_0"

    @pytest.mark.asyncio
    async def test_no_keys_raises(self, manager, monkeypatch):
        """When no AI keys are configured, should raise RuntimeError."""
        with pytest.raises(RuntimeError, match="未配置任何可用的API Key"):
            await manager.get_key_for_request("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_unknown_provider_raises(self, manager, monkeypatch):
        """Requesting a provider that doesn't exist in the cache should raise."""
        monkeypatch.setenv("AI_OPENAI_API_KEY", "sk-openai")
        with pytest.raises(RuntimeError, match="未配置任何可用的API Key"):
            await manager.get_key_for_request("SILICON")

    @pytest.mark.asyncio
    async def test_round_robin_two_keys(self, manager, monkeypatch):
        """Two keys should be returned in alternating order.
        NOTE: Code expects AI_{PROVIDER}_{N}_API_KEY pattern (index before _API_KEY)."""
        monkeypatch.setenv("AI_SILICON_1_API_KEY", "sk-first")
        monkeypatch.setenv("AI_SILICON_2_API_KEY", "sk-second")
        key1 = await manager.get_key_for_request("SILICON")
        key2 = await manager.get_key_for_request("SILICON")
        key3 = await manager.get_key_for_request("SILICON")
        assert key1["api_key"] == "sk-first"
        assert key2["api_key"] == "sk-second"
        assert key3["api_key"] == "sk-first"

    @pytest.mark.asyncio
    async def test_get_all_providers_when_empty_provider_id(self, manager, monkeypatch):
        """Empty provider_id should merge all keys."""
        monkeypatch.setenv("AI_SILICON_API_KEY", "sk-silicon")
        monkeypatch.setenv("AI_DEEPSEEK_API_KEY", "sk-deepseek")
        key = await manager.get_key_for_request(provider_id="")
        assert key["api_key"] in ("sk-silicon", "sk-deepseek")


class TestKeyCache:
    """APIKeyManager cache refresh logic."""

    def test_cache_refresh_on_each_call(self, manager, monkeypatch):
        """_get_next_key calls _refresh_keys_cache which reloads from env."""
        monkeypatch.setenv("AI_SILICON_API_KEY", "sk-original")
        key1 = manager._get_next_key("SILICON")
        assert key1["api_key"] == "sk-original"

        monkeypatch.setenv("AI_SILICON_API_KEY", "sk-updated")
        key2 = manager._get_next_key("SILICON")
        assert key2["api_key"] == "sk-updated"

    def test_cache_empty_after_clear(self, manager, monkeypatch):
        """Clearing all AI vars should make cache empty on refresh."""
        monkeypatch.setenv("AI_SILICON_API_KEY", "sk-temp")
        manager._get_next_key("SILICON")  # loads into cache
        assert "SILICON" in manager._keys_cache

        monkeypatch.delenv("AI_SILICON_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            manager._get_next_key("SILICON")


class TestEdgeCases:
    """Edge cases for APIKeyManager."""

    def test_key_entry_structure(self, manager, monkeypatch):
        """Each key entry should have all expected fields."""
        monkeypatch.setenv("AI_SILICON_API_KEY", "sk-test")
        result = manager._load_keys_from_env()
        entry = result["SILICON"][0]
        assert "api_key" in entry
        assert "api_host" in entry
        assert "api_model" in entry
        assert "key_index" in entry
        assert "id" in entry
        assert entry["id"] == "env_SILICON_0"

    def test_multiple_providers_independent_indexes(self, manager, monkeypatch):
        """Each provider's round-robin index should be independent."""
        monkeypatch.setenv("AI_SILICON_1_API_KEY", "sk-s1")
        monkeypatch.setenv("AI_SILICON_2_API_KEY", "sk-s2")
        monkeypatch.setenv("AI_DEEPSEEK_1_API_KEY", "sk-d1")
        monkeypatch.setenv("AI_DEEPSEEK_2_API_KEY", "sk-d2")

        assert manager._get_next_key("SILICON")["api_key"] == "sk-s1"
        assert manager._get_next_key("DEEPSEEK")["api_key"] == "sk-d1"
        assert manager._get_next_key("SILICON")["api_key"] == "sk-s2"
        assert manager._get_next_key("DEEPSEEK")["api_key"] == "sk-d2"
        assert manager._get_next_key("SILICON")["api_key"] == "sk-s1"
