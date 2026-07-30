"""
模型运行时解析 — 根据模型 ID 查找对应的供应商 API 配置

借鉴 CherryStudio:
- RuntimeExecutor.embedMany()
- RuntimeExecutor.rerank()
- parseCompositeModelId()

使用 capability-based 模型类型检测代替关键词匹配。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from app.algorithm.model_registry import model_registry
from app.algorithm.providers_registry import (
    CAPABILITY_EMBEDDING,
    CAPABILITY_RERANK,
    get_model_capabilities,
    get_model_id,
    infer_capabilities,
    normalize_model,
)

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """模型 API 连接配置"""

    api_key: str
    api_host: str
    model: str
    provider_id: str


class ModelRuntime:
    """模型运行时解析服务。

    职责：
    - 根据 embedding_model_id / rerank_model_id 查找对应的 Provider 配置
    - 支持复合格式 "providerId:modelId" 和纯模型名自动查找
    - 返回完整的 API 调用参数 (api_key, api_host, model)
    """

    @staticmethod
    def parse_model_id(model_id: str) -> tuple[str, str]:
        """解析复合模型 ID。

        格式："providerId:modelId" 或纯模型名。
        示例：
          "silicon:BAAI/bge-large-zh-v1.5" → ("silicon", "BAAI/bge-large-zh-v1.5")
          "text-embedding-3-small"         → ("", "text-embedding-3-small")
        容错：自动修正双冒号 "silicon::model" → ("silicon", "model")
        """
        if not model_id:
            return "", ""
        if ":" in model_id:
            parts = model_id.split(":", 1)
            provider = parts[0]
            # 防御：处理双冒号（如 "silicon::model" → provider="silicon", model="model"）
            model = parts[1].lstrip(":")
            return provider, model
        return "", model_id

    @staticmethod
    def resolve_embedding(embedding_model_id: str) -> ModelConfig | None:
        """解析嵌入模型的 API 配置。

        查找逻辑：
        1. 解析 composite model ID
        2. 如果有 provider_id，直接查该供应商
        3. 否则在所有启用的供应商中查找匹配模型
        """
        provider_id, model = ModelRuntime.parse_model_id(embedding_model_id)
        if not model:
            logger.warning("resolve_embedding: 空的 model_id")
            return None
        return ModelRuntime._resolve(provider_id, model)

    @staticmethod
    def resolve_rerank(rerank_model_id: str) -> ModelConfig | None:
        """解析重排模型的 API 配置。"""
        provider_id, model = ModelRuntime.parse_model_id(rerank_model_id)
        if not model:
            logger.warning("resolve_rerank: 空的 model_id")
            return None
        return ModelRuntime._resolve(provider_id, model)

    @staticmethod
    def resolve_first_embedding() -> ModelConfig | None:
        """从所有启用的 Provider 中找到第一个嵌入模型配置。

        降级方案：当知识库未指定 embedding_model_id 时使用。
        API 密钥从环境变量读取。
        """
        from app.algorithm.model_service import _get_provider_api_key
        from app.database import get_db

        db = get_db()
        try:
            rows = db.execute(
                "SELECT provider_id, api_host, models FROM model_providers WHERE is_enabled=1 ORDER BY id ASC"
            ).fetchall()
        finally:
            db.close()

        for r in rows:
            models_raw = (
                r["models"] if isinstance(r["models"], list) else (json.loads(r["models"]) if r["models"] else [])
            )
            for m in models_raw:
                entry = normalize_model(m)
                if CAPABILITY_EMBEDDING in entry["capabilities"]:
                    provider_id = r["provider_id"]
                    api_key = _get_provider_api_key(provider_id)
                    if api_key:
                        return ModelConfig(
                            api_key=api_key,
                            api_host=r["api_host"],
                            model=get_model_id(m),
                            provider_id=provider_id,
                        )

        logger.warning("resolve_first_embedding: 未找到启用的嵌入模型供应商")
        return None

    @staticmethod
    def resolve_first_rerank() -> ModelConfig | None:
        """从所有启用的 Provider 中找到第一个重排模型配置。"""
        from app.algorithm.model_service import _get_provider_api_key
        from app.database import get_db

        db = get_db()
        try:
            rows = db.execute(
                "SELECT provider_id, api_host, models FROM model_providers WHERE is_enabled=1 ORDER BY id ASC"
            ).fetchall()
        finally:
            db.close()

        for r in rows:
            models_raw = (
                r["models"] if isinstance(r["models"], list) else (json.loads(r["models"]) if r["models"] else [])
            )
            for m in models_raw:
                entry = normalize_model(m)
                if CAPABILITY_RERANK in entry["capabilities"]:
                    provider_id = r["provider_id"]
                    api_key = _get_provider_api_key(provider_id)
                    if api_key:
                        return ModelConfig(
                            api_key=api_key,
                            api_host=r["api_host"],
                            model=get_model_id(m),
                            provider_id=provider_id,
                        )

        logger.warning("resolve_first_rerank: 未找到启用的重排模型供应商")
        return None

    @staticmethod
    def ensure_v1_url(host: str) -> str:
        """确保 api_host 末尾有 /v1（OpenAI SDK v2 不再自动追加）。"""
        host = host.rstrip("/")
        if not host.endswith("/v1"):
            host = f"{host}/v1"
        return host

    @staticmethod
    def test_connection(provider_id: str, model: str, api_key_override: str | None = None) -> dict:
        """检查模型连接（根据模型能力自动选择测试方式）。

        Args:
            provider_id: 供应商 ID
            model: 模型名称
            api_key_override: 可选的 API Key 覆盖（用于外部已获取密钥的场景）
        """
        from app.algorithm.model_service import _get_provider_api_key
        from app.database import get_db

        # 如果传入了 api_key_override，直接使用；否则从环境变量读取
        api_key = api_key_override or _get_provider_api_key(provider_id)
        if not api_key:
            return {"status": "error", "message": "供应商未配置或未启用"}

        db = get_db()
        try:
            row = db.execute(
                "SELECT api_host, models FROM model_providers WHERE provider_id=? AND is_enabled=1",
                (provider_id,),
            ).fetchone()
        finally:
            db.close()

        if not row:
            return {"status": "error", "message": "供应商不存在或未启用"}

        api_host = row["api_host"]

        # 1) 在供应商的模型列表中查找该模型的能力定义
        models = (
            row["models"] if isinstance(row["models"], list) else (json.loads(row["models"]) if row["models"] else [])
        )
        target_caps = None
        for m in models:
            if get_model_id(m) == model:
                target_caps = get_model_capabilities(m)
                break

        # 2) 未在存储列表中找到，查注册表
        if target_caps is None:
            reg_caps = model_registry.get_capabilities(model, provider_id)
            if reg_caps is not None:
                target_caps = reg_caps

        # 3) 仍未找到，正则回退
        if target_caps is None:
            target_caps = infer_capabilities(model)

        try:
            if CAPABILITY_EMBEDDING in target_caps:
                return ModelRuntime._test_embedding(api_key, api_host, model)
            elif CAPABILITY_RERANK in target_caps:
                return ModelRuntime._test_rerank(api_key, api_host, model)
            else:
                return ModelRuntime._test_chat(api_key, api_host, model)
        except Exception as e:
            return {"status": "error", "message": str(e)[:100]}

    @staticmethod
    def _test_embedding(api_key: str, api_host: str, model: str) -> dict:
        """测试嵌入模型(通过 AIClientRegistry OpenAICompatibleAdapter)。"""
        import time

        from app.algorithm.client_registry import AIClientRegistry

        adapter = AIClientRegistry.get("openai")
        start = time.time()
        vectors = adapter.embedding(
            api_key=api_key,
            api_host=api_host,
            model_id=model,
            texts=["test"],
            timeout=30.0,
        )
        latency = (time.time() - start) * 1000
        dim = len(vectors[0]) if vectors else 0
        return {"status": "ok", "latency_ms": round(latency, 1), "model": model, "type": "embedding", "dimension": dim}

    @staticmethod
    def _test_rerank(api_key: str, api_host: str, model: str) -> dict:
        """测试重排模型 — 使用正确的重排 API，而非聊天 API。"""
        import time

        import httpx

        start = time.time()
        base = api_host.rstrip("/")
        url = f"{base}/v1/rerank" if not base.endswith("/v1") else f"{base}/rerank"
        body = {
            "model": model,
            "query": "test query",
            "documents": ["test document one", "test document two"],
            "top_n": 1,
        }

        try:
            resp = httpx.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"重排 API 错误 ({e.response.status_code}): {e.response.text[:100]}"}
        except Exception as e:
            return {"status": "error", "message": f"重排 API 连接失败: {e}"}

        if resp.status_code == 200:
            latency = (time.time() - start) * 1000
            return {"status": "ok", "latency_ms": round(latency, 1), "model": model, "type": "rerank"}
        # DashScope uses a different endpoint
        if "dashscope" in api_host or "aliyuncs" in api_host:
            try:
                dashscope_url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank"
                resp2 = httpx.post(
                    dashscope_url,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "input": {"query": "test", "documents": ["doc1", "doc2"]},
                        "parameters": {"top_n": 1},
                    },
                    timeout=30,
                )
                if resp2.status_code == 200:
                    latency = (time.time() - start) * 1000
                    return {"status": "ok", "latency_ms": round(latency, 1), "model": model, "type": "rerank"}
            except Exception as e:
                logger.warning(f"DashScope rerank test connection failed: {e}")

        return {"status": "error", "message": f"重排 API 返回非正常状态: HTTP {resp.status_code}"}

    @staticmethod
    def _test_chat(api_key: str, api_host: str, model: str) -> dict:
        """测试聊天模型(通过 AIClientRegistry OpenAICompatibleAdapter)。"""
        import time

        from app.algorithm.client_registry import AIClientRegistry

        adapter = AIClientRegistry.get("openai")
        start = time.time()
        adapter.chat(
            api_key=api_key,
            api_host=api_host,
            model_id=model,
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.0,
            timeout=30.0,
        )
        latency = (time.time() - start) * 1000
        return {"status": "ok", "latency_ms": round(latency, 1), "model": model, "type": "chat"}

    @staticmethod
    def _resolve(provider_id: str, model: str) -> ModelConfig | None:
        """内部方法：按 provider_id 和 model 查找配置。

        API 密钥从环境变量读取。
        """
        from app.algorithm.model_service import _get_provider_api_key
        from app.database import get_db

        db = get_db()
        try:
            if provider_id:
                row = db.execute(
                    "SELECT api_host FROM model_providers WHERE provider_id=? AND is_enabled=1",
                    (provider_id,),
                ).fetchone()
                if not row:
                    logger.warning(f"resolve: provider '{provider_id}' 不存在或未启用")
                    return None
                api_key = _get_provider_api_key(provider_id)
                if not api_key:
                    logger.warning(f"resolve: provider '{provider_id}' 未配置 API Key")
                    return None
                return ModelConfig(
                    api_key=api_key,
                    api_host=row["api_host"],
                    model=model,
                    provider_id=provider_id,
                )

            rows = db.execute(
                "SELECT provider_id, api_host, models FROM model_providers WHERE is_enabled=1 ORDER BY id ASC"
            ).fetchall()
        finally:
            db.close()

        for r in rows:
            models_raw = (
                r["models"] if isinstance(r["models"], list) else (json.loads(r["models"]) if r["models"] else [])
            )
            pid = r["provider_id"]
            api_key = _get_provider_api_key(pid)
            if not api_key:
                continue
            if not models_raw:
                return ModelConfig(
                    api_key=api_key,
                    api_host=r["api_host"],
                    model=model,
                    provider_id=pid,
                )
            else:
                for m in models_raw:
                    if get_model_id(m) == model:
                        return ModelConfig(
                            api_key=api_key,
                            api_host=r["api_host"],
                            model=model,
                            provider_id=pid,
                        )

        logger.warning(f"resolve: 模型 '{model}' 未在任何启用的供应商中找到")
        return None


model_runtime = ModelRuntime()
