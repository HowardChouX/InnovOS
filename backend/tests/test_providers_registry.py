"""测试 providers_registry.py — 能力推断与归一化"""
import pytest
from app.algorithm.providers_registry import (
    CAPABILITY_CHAT,
    CAPABILITY_EMBEDDING,
    CAPABILITY_RERANK,
    CAPABILITY_REASONING,
    CAPABILITY_IMAGE_GENERATION,
    infer_capabilities,
    normalize_model,
    get_model_id,
    get_model_capabilities,
    get_provider_info,
    list_all_builtin,
    BUILTIN_PROVIDERS,
)


class TestCapabilityConstants:
    def test_constants_exist(self):
        assert CAPABILITY_CHAT == "chat"
        assert CAPABILITY_EMBEDDING == "embedding"
        assert CAPABILITY_RERANK == "rerank"
        assert CAPABILITY_REASONING == "reasoning"
        assert CAPABILITY_IMAGE_GENERATION == "image-generation"


class TestInferCapabilities:
    """遵循 Cherry Studio 的逻辑：RERANK_REGEX 优先于 EMBEDDING_REGEX"""

    @pytest.mark.parametrize("model_id", [
        "BAAI/bge-reranker-v2-m3",
        "rerank-english-v3.0",
        "cross-encoder/ms-marco-MiniLM",
        "bge-reranker-base",
        "bce-reranker-base_v1",
        "cohere-rerank-3",
    ])
    def test_rerank_models(self, model_id):
        caps = infer_capabilities(model_id)
        assert CAPABILITY_RERANK in caps
        assert CAPABILITY_EMBEDDING not in caps  # rerank 优先

    @pytest.mark.parametrize("model_id", [
        "BAAI/bge-large-zh-v1.5",
        "bge-m3",
        "bce-embedding-base_v1",
        "text-embedding-3-small",
        "text-embedding-ada-002",
        "e5-large-v2",
        "multilingual-e5-large",
        "gte-large-en",
        "jina-embeddings-v3",
        "voyage-2",
        "uae-large-v1",
        "LLM2Vec",
        "retrieval-model",
    ])
    def test_embedding_models(self, model_id):
        caps = infer_capabilities(model_id)
        assert CAPABILITY_EMBEDDING in caps
        assert CAPABILITY_CHAT not in caps

    @pytest.mark.parametrize("model_id", [
        "gpt-4o",
        "gpt-4o-mini",
        "claude-3-opus",
        "deepseek-chat",
        "Qwen/Qwen2.5-72B-Instruct",
        "glm-4-plus",
        "moonshot-v1-8k",
    ])
    def test_chat_models(self, model_id):
        caps = infer_capabilities(model_id)
        assert CAPABILITY_CHAT in caps
        assert CAPABILITY_EMBEDDING not in caps
        assert CAPABILITY_RERANK not in caps

    @pytest.mark.parametrize("model_id", [
        "deepseek-r1-671b",
        "o1-preview",
        "o3-mini",
        "reasoner-small",
    ])
    def test_reasoning_models(self, model_id):
        caps = infer_capabilities(model_id)
        assert CAPABILITY_CHAT in caps
        assert CAPABILITY_REASONING in caps

    def test_empty_string(self):
        caps = infer_capabilities("")
        assert caps == [CAPABILITY_CHAT]


class TestNormalizeModel:
    def test_string_input(self):
        result = normalize_model("gpt-4o")
        assert result["id"] == "gpt-4o"
        assert CAPABILITY_CHAT in result["capabilities"]

    def test_dict_input_with_capabilities(self):
        result = normalize_model({"id": "gpt-4o", "capabilities": ["chat"]})
        assert result["id"] == "gpt-4o"
        assert result["capabilities"] == ["chat"]

    def test_dict_input_without_capabilities(self):
        """dict 缺少 capabilities 时应自动推断"""
        result = normalize_model({"id": "BAAI/bge-large-zh-v1.5"})
        assert result["id"] == "BAAI/bge-large-zh-v1.5"
        assert CAPABILITY_EMBEDDING in result["capabilities"]

    def test_embedding_string_normalize(self):
        result = normalize_model("text-embedding-3-small")
        assert CAPABILITY_EMBEDDING in result["capabilities"]

    def test_rerank_string_normalize(self):
        result = normalize_model("rerank-english-v3.0")
        assert CAPABILITY_RERANK in result["capabilities"]

    def test_old_format_list(self):
        models = ["gpt-4", "text-embedding-3-small", "rerank-model"]
        normalized = [normalize_model(m) for m in models]
        assert normalized[0]["capabilities"] == ["chat"]
        assert normalized[1]["capabilities"] == ["embedding"]
        assert normalized[2]["capabilities"] == ["rerank"]


class TestGetModelId:
    def test_from_string(self):
        assert get_model_id("gpt-4") == "gpt-4"

    def test_from_dict(self):
        assert get_model_id({"id": "gpt-4", "capabilities": ["chat"]}) == "gpt-4"

    def test_from_dict_no_id(self):
        assert get_model_id({"name": "foo"}) == ""

    def test_from_int(self):
        assert get_model_id(123) == "123"


class TestGetModelCapabilities:
    def test_from_string(self):
        caps = get_model_capabilities("text-embedding-3-small")
        assert CAPABILITY_EMBEDDING in caps

    def test_from_dict(self):
        caps = get_model_capabilities({"id": "gpt-4", "capabilities": ["chat"]})
        assert caps == ["chat"]


class TestBuiltinProviders:
    def test_all_providers_have_required_keys(self):
        required = {"id", "name", "protocol", "api_host", "models"}
        for pid, provider in BUILTIN_PROVIDERS.items():
            missing = required - set(provider.keys())
            assert not missing, f"{pid} missing: {missing}"

    def test_protocol_is_openai_or_anthropic(self):
        for pid, provider in BUILTIN_PROVIDERS.items():
            assert provider["protocol"] in ("openai", "anthropic"), f"{pid}"

    def test_ollama_has_empty_models(self):
        assert BUILTIN_PROVIDERS["ollama"]["models"] == []

    def test_silicon_has_embedding_model(self):
        silicon = BUILTIN_PROVIDERS["silicon"]
        models = silicon["models"]
        has_embedding = any(
            CAPABILITY_EMBEDDING in m.get("capabilities", [])
            for m in models
        )
        assert has_embedding, "SiliconFlow should have an embedding model"

    def test_openai_has_embedding_model(self):
        openai = BUILTIN_PROVIDERS["openai"]
        models = openai["models"]
        has_embedding = any(
            CAPABILITY_EMBEDDING in m.get("capabilities", [])
            for m in models
        )
        assert has_embedding, "OpenAI should have an embedding model"

    def test_get_provider_info(self):
        info = get_provider_info("openai")
        assert info is not None
        assert info["name"] == "OpenAI"

    def test_get_provider_info_unknown(self):
        assert get_provider_info("nonexistent") is None

    def test_list_all_builtin_count(self):
        providers = list_all_builtin()
        assert len(providers) >= 7
        all_ids = [p["id"] for p in providers]
        assert "openai" in all_ids
        assert "silicon" in all_ids

    def test_builtin_ids_match_keys(self):
        for key, provider in BUILTIN_PROVIDERS.items():
            assert provider["id"] == key, f"Key '{key}' != provider.id '{provider['id']}'"
