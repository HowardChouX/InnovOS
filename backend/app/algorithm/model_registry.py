"""
模型注册表服务 — 全量移植 CherryStudio ProviderRegistryService

职责：
1. 加载内置模型注册表 (models.json, 2619 条目)
2. 加载供应商覆盖配置 (provider-models.json, 1444 条目)
3. lookup(model_id) → 基础模型信息（含 capabilities）
4. resolve(provider_id, model_id) → 叠加供应商覆盖后的最终能力
5. enrich_models(provider_id, model_ids) → 批量化 enrichment（API 发现后调用）
6. 正则推断兜底（当注册表无匹配时）

架构（完全对齐 CherryStudio）：
```
API 发现模型 (model IDs)
    → enrichFetchedModels(model_ids, provider_id)
        → 查 models.json 获取 base capabilities
        → 查 provider-models.json 叠加 override (add/remove/force)
        → 未命中则 infer_capabilities() 兜底
    → 返回完整 ModelEntry[] 对象
```
"""
from __future__ import annotations
import json
import logging
import os
from typing import Optional
from app.algorithm.providers_registry import infer_capabilities, CAPABILITY_CHAT

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_MODELS_PATH = os.path.join(_DATA_DIR, "models.json")
_PROVIDER_MODELS_PATH = os.path.join(_DATA_DIR, "provider-models.json")


class ModelRegistry:
    """全量模型注册表（单例模式）。

    参考 CherryStudio ProviderRegistryService + mergePresetModel
    """

    _instance: Optional["ModelRegistry"] = None

    def __init__(self):
        self._models: dict[str, dict] = {}          # model_id → model entry
        self._overrides: dict[str, list[dict]] = {} # provider_id → [overrides]
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self) -> None:
        """加载注册表数据（启动时调用）。"""
        if self._loaded:
            return
        self._load_models()
        self._load_provider_models()
        self._loaded = True
        logger.info(
            f"模型注册表已加载: {len(self._models)} 个模型, "
            f"{len(self._overrides)} 个供应商覆盖"
        )

    def _load_models(self):
        """加载 models.json。"""
        if not os.path.exists(_MODELS_PATH):
            logger.warning(f"模型注册表文件不存在: {_MODELS_PATH}")
            return
        with open(_MODELS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get("models", []):
            mid = entry.get("id", "")
            if mid:
                self._models[mid] = entry
        logger.info(f"  加载 {len(self._models)} 个模型条目")

    def _load_provider_models(self):
        """加载 provider-models.json。"""
        if not os.path.exists(_PROVIDER_MODELS_PATH):
            logger.warning(f"供应商覆盖文件不存在: {_PROVIDER_MODELS_PATH}")
            return
        with open(_PROVIDER_MODELS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get("overrides", []):
            pid = entry.get("providerId", "")
            if pid:
                self._overrides.setdefault(pid, []).append(entry)
        logger.info(f"  加载 {sum(len(v) for v in self._overrides.values())} 个供应商覆盖条目")

    # ── 查询 ──

    def lookup(self, model_id: str) -> Optional[dict]:
        """在注册表中查找模型（精确 ID 匹配）。"""
        if not self._loaded:
            self.load()
        return self._models.get(model_id)

    def get_provider_overrides(self, provider_id: str) -> list[dict]:
        """获取供应商的覆盖配置。"""
        if not self._loaded:
            self.load()
        return self._overrides.get(provider_id, [])

    def get_provider_model(self, provider_id: str, model_id: str) -> Optional[dict]:
        """获取特定供应商下某模型的覆盖配置。"""
        for override in self.get_provider_overrides(provider_id):
            if override.get("modelId") == model_id:
                return override
        return None

    # ── 能力解析（核心） ──

    def get_capabilities(self, model_id: str, provider_id: str | None = None) -> Optional[list[str]]:
        """获取模型的最终能力列表。

        匹配 CherryStudio resolveCapabilities() 逻辑：
        1. 从 models.json 获取 base capabilities
        2. 如果 provider_id 有 override，应用 add/remove/force
        3. 模型不在 registry 但 override 有 force → 用 force
        4. 都未找到则返回 None（调用方使用 infer_capabilities 兜底）
        """
        if not self._loaded:
            self.load()

        # 1. 基础能力
        entry = self._models.get(model_id)
        base_caps = list(entry.get("capabilities", [])) if entry else []

        # 2. 供应商覆盖
        override = self.get_provider_model(provider_id, model_id) if provider_id else None
        if override:
            caps_override = override.get("capabilities", {})
            if "force" in caps_override:
                return list(caps_override["force"])
            if base_caps:
                result = list(base_caps)
                for cap in caps_override.get("add", []):
                    if cap not in result:
                        result.append(cap)
                for cap in caps_override.get("remove", []):
                    if cap in result:
                        result.remove(cap)
                return result
            # 模型不在 registry 但有 override 的 add/remove → 用 override 能力
            if caps_override.get("add"):
                return list(caps_override["add"])

        # 3. 未找到
        if not base_caps:
            return None
        return base_caps

    def get_model_info(self, model_id: str, provider_id: str | None = None) -> dict:
        """获取完整模型信息（合并注册表 + 供应商覆盖）。"""
        if not self._loaded:
            self.load()

        entry = self._models.get(model_id)
        base: dict = dict(entry) if entry else {"id": model_id}

        # 能力
        caps = self.get_capabilities(model_id, provider_id)
        if caps is not None:
            base["capabilities"] = caps
        elif "capabilities" not in base:
            base["capabilities"] = infer_capabilities(model_id)

        # 供应商覆盖（合并额外字段如 apiModelId, endpointTypes, pricing, limits）
        if provider_id:
            override = self.get_provider_model(provider_id, model_id)
            if override:
                for k, v in override.items():
                    if k not in ("modelId", "providerId", "capabilities"):
                        base[k] = v

        return base

    # ── 批量 enrichment（API 发现后调用） ──

    def enrich_models(
        self, provider_id: str, model_ids: list[str]
    ) -> list[dict]:
        """对 API 发现的模型列表做 enrichment。

        匹配 CherryStudio enrichFetchedModels() + mergePresetModel()。
        每个模型返回 {"id": str, "capabilities": list[str], ...}
        """
        result = []
        for mid in model_ids:
            info = self.get_model_info(mid, provider_id)
            result.append({
                "id": info["id"],
                "capabilities": info.get("capabilities", infer_capabilities(mid)),
                "name": info.get("name"),
                "contextWindow": info.get("contextWindow"),
                "maxOutputTokens": info.get("maxOutputTokens"),
                "pricing": info.get("pricing"),
                "endpointTypes": info.get("endpointTypes"),
            })
        return result


# 模块级单例
model_registry = ModelRegistry.get_instance()
