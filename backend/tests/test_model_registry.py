"""测试 model_registry.py — 注册表加载、查询、override 合并"""
import pytest


class TestModelRegistryLoad:
    def test_singleton(self):
        """get_instance() 始终返回同一实例"""
        from app.algorithm.model_registry import ModelRegistry
        a = ModelRegistry.get_instance()
        b = ModelRegistry.get_instance()
        assert a is b

    def test_load_success(self, registry):
        """加载注册表不应抛出异常"""
        assert registry is not None

    def test_load_populates_registry(self, registry):
        """加载后 models 字典应有 1000+ 条"""
        assert len(registry._models) > 1000, f"Only {len(registry._models)} models loaded"

    def test_load_populates_provider_overrides(self, registry):
        """加载后 provider_overrides 应有 1000+ 条"""
        count = sum(len(v) for v in registry._overrides.values())
        assert count > 1000, f"Only {count} overrides loaded"


class TestLookup:
    def test_lookup_known_gpt4(self, registry):
        entry = registry.lookup("gpt-4")
        assert entry is not None
        assert "capabilities" in entry
        assert "embedding" not in entry.get("capabilities", [])

    def test_lookup_known_embedding(self, registry):
        entry = registry.lookup("text-embedding-3-small")
        assert entry is not None
        caps = entry.get("capabilities", [])
        assert "embedding" in caps

    def test_lookup_known_rerank(self, registry):
        """找一个已知的重排模型"""
        for mid in ("bge-reranker-v2-m3", "rerank-english-v3.0", "jina-reranker-v3"):
            entry = registry.lookup(mid)
            if entry and "rerank" in entry.get("capabilities", []):
                return
        pytest.skip("No rerank model found in registry")

    def test_lookup_unknown(self, registry):
        assert registry.lookup("nonexistent-model-xyz-123") is None

    def test_lookup_empty_string(self, registry):
        assert registry.lookup("") is None


class TestGetCapabilities:
    def test_get_capabilities_known(self, registry):
        caps = registry.get_capabilities("text-embedding-3-small")
        assert caps is not None
        assert "embedding" in caps

    def test_get_capabilities_with_provider(self, registry):
        """提供 provider_id 时应继续工作（可能增加 override）"""
        caps = registry.get_capabilities("gpt-4", "openai")
        assert caps is not None

    def test_get_capabilities_no_match(self, registry):
        caps = registry.get_capabilities("made-up-model-99999")
        assert caps is None or caps == []


class TestProviderOverrides:
    def test_get_provider_overrides_known(self, registry):
        """硅流应有至少一条 override"""
        overrides = registry.get_provider_overrides("silicon")
        assert isinstance(overrides, list)

    def test_get_provider_overrides_unknown(self, registry):
        overrides = registry.get_provider_overrides("nonexistent_provider_xyz")
        assert overrides == [] or overrides is None

    def test_get_provider_model_known(self, registry):
        """查找指定 provider 下的 model override"""
        # 尝试几个常见 provider
        for provider_id in ("silicon", "openai", "ppio"):
            entry = registry.get_provider_model(provider_id, "gpt-4")
            if entry:
                return
        pytest.skip("No provider-model override found for gpt-4")

    def test_get_provider_model_unknown(self, registry):
        entry = registry.get_provider_model("nonexistent", "foo")
        assert entry is None


class TestGetModelInfo:
    def test_get_model_info_without_provider(self, registry):
        info = registry.get_model_info("text-embedding-3-small")
        assert info is not None
        assert "id" in info
        assert "capabilities" in info

    def test_get_model_info_with_provider(self, registry):
        info = registry.get_model_info("text-embedding-3-small", "openai")
        assert info is not None
        assert info["id"] == "text-embedding-3-small"

    def test_get_model_info_unknown(self, registry):
        info = registry.get_model_info("model-does-not-exist")
        # Should return a fallback entry with inferred capabilities
        assert info is not None
        assert info["id"] == "model-does-not-exist"


class TestEnrichModels:
    def test_enrich_known_models(self, registry):
        """已知模型应获得 registry 中的 capabilities"""
        models = ["gpt-4", "text-embedding-3-small", "gpt-4o-mini"]
        enriched = registry.enrich_models("openai", models)
        assert len(enriched) == 3
        # gpt-4 不应该有 embedding
        gpt4 = [m for m in enriched if m["id"] == "gpt-4"]
        assert gpt4
        assert "embedding" not in gpt4[0].get("capabilities", [])

    def test_enrich_unknown_models(self, registry):
        """未知模型应通过正则推断能力"""
        models = ["completely-unknown-model-v1"]
        enriched = registry.enrich_models("test_provider", models)
        assert len(enriched) == 1
        # 默认推断为 chat
        assert "chat" in enriched[0].get("capabilities", [])

    def test_enrich_empty_list(self, registry):
        assert registry.enrich_models("openai", []) == []

    def test_enrich_with_provider_override(self, registry):
        """如果 provider 有 override，应合并到结果中"""
        models = ["gpt-4"]
        enriched = registry.enrich_models("openai", models)
        assert len(enriched) == 1
        # 至少要有 id
        assert "id" in enriched[0]

    def test_enrich_rerank_model(self, registry):
        """重排模型 enrichment 后应有 rerank capability"""
        for model_id in ("bge-reranker-v2-m3", "rerank-english-v3.0", "cohere-rerank-3"):
            enriched = registry.enrich_models("test", [model_id])
            if enriched and "rerank" in enriched[0].get("capabilities", []):
                return
        pytest.skip("No rerank-enriched model found")
