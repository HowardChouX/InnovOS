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
from typing import Optional

from app.algorithm.providers_registry import (
    CAPABILITY_EMBEDDING,
    CAPABILITY_RERANK,
    infer_capabilities,
    normalize_model,
    get_model_id,
    get_model_capabilities,
)
from app.algorithm.model_registry import model_registry

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
    def resolve_embedding(embedding_model_id: str) -> Optional[ModelConfig]:
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
    def resolve_rerank(rerank_model_id: str) -> Optional[ModelConfig]:
        """解析重排模型的 API 配置。"""
        provider_id, model = ModelRuntime.parse_model_id(rerank_model_id)
        if not model:
            logger.warning("resolve_rerank: 空的 model_id")
            return None
        return ModelRuntime._resolve(provider_id, model)

    @staticmethod
    def resolve_first_embedding() -> Optional[ModelConfig]:
        """从所有启用的 Provider 中找到第一个嵌入模型配置。

        降级方案：当知识库未指定 embedding_model_id 时使用。
        """
        from app.database import get_db
        from app.algorithm.crypto import decrypt_key

        db = get_db()
        rows = db.execute(
            "SELECT provider_id, api_host, api_key_encrypted, models FROM model_providers "
            "WHERE is_enabled=1 AND api_key_encrypted IS NOT NULL "
            "ORDER BY id ASC"
        ).fetchall()
        db.close()

        for r in rows:
            models_raw = r["models"] if isinstance(r["models"], list) else (json.loads(r["models"]) if r["models"] else [])
            for m in models_raw:
                entry = normalize_model(m)
                if CAPABILITY_EMBEDDING in entry["capabilities"]:
                    api_key = decrypt_key(r["api_key_encrypted"]) if r["api_key_encrypted"] else ""
                    if api_key:
                        return ModelConfig(
                            api_key=api_key,
                            api_host=r["api_host"],
                            model=get_model_id(m),
                            provider_id=r["provider_id"],
                        )

        logger.warning("resolve_first_embedding: 未找到启用的嵌入模型供应商")
        return None

    @staticmethod
    def resolve_first_rerank() -> Optional[ModelConfig]:
        """从所有启用的 Provider 中找到第一个重排模型配置。"""
        from app.database import get_db
        from app.algorithm.crypto import decrypt_key

        db = get_db()
        rows = db.execute(
            "SELECT provider_id, api_host, api_key_encrypted, models FROM model_providers "
            "WHERE is_enabled=1 AND api_key_encrypted IS NOT NULL "
            "ORDER BY id ASC"
        ).fetchall()
        db.close()

        for r in rows:
            models_raw = r["models"] if isinstance(r["models"], list) else (json.loads(r["models"]) if r["models"] else [])
            for m in models_raw:
                entry = normalize_model(m)
                if CAPABILITY_RERANK in entry["capabilities"]:
                    api_key = decrypt_key(r["api_key_encrypted"]) if r["api_key_encrypted"] else ""
                    if api_key:
                        return ModelConfig(
                            api_key=api_key,
                            api_host=r["api_host"],
                            model=get_model_id(m),
                            provider_id=r["provider_id"],
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
    def test_connection(provider_id: str, model: str) -> dict:
        """检查模型连接（根据模型能力自动选择测试方式）。

        替代 ModelService.check_connection 中的模型类型判断逻辑。
        """
        from app.database import get_db
        from app.algorithm.crypto import decrypt_key

        db = get_db()
        row = db.execute(
            "SELECT api_host, api_key_encrypted, models FROM model_providers WHERE provider_id=? AND is_enabled=1",
            (provider_id,),
        ).fetchone()
        db.close()

        if not row or not row["api_key_encrypted"]:
            return {"status": "error", "message": "供应商未配置或未启用"}

        api_key = decrypt_key(row["api_key_encrypted"])
        api_host = row["api_host"]

        # 1) 在供应商的模型列表中查找该模型的能力定义
        models = row["models"] if isinstance(row["models"], list) else (json.loads(row["models"]) if row["models"] else [])
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
        """测试嵌入模型。"""
        import time
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=ModelRuntime.ensure_v1_url(api_host))
        start = time.time()
        resp = client.embeddings.create(model=model, input="test")
        latency = (time.time() - start) * 1000
        dim = len(resp.data[0].embedding) if resp.data else 0
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
        except Exception:
            pass
        else:
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
                except Exception:
                    pass

        return {"status": "error", "message": f"重排 API 连接失败: 不支持的端点或协议"}

    @staticmethod
    def _test_chat(api_key: str, api_host: str, model: str) -> dict:
        """测试聊天模型。"""
        import time
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=ModelRuntime.ensure_v1_url(api_host))
        start = time.time()
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        latency = (time.time() - start) * 1000
        return {"status": "ok", "latency_ms": round(latency, 1), "model": model, "type": "chat"}

    @staticmethod
    def _resolve(provider_id: str, model: str) -> Optional[ModelConfig]:
        """内部方法：按 provider_id 和 model 查找配置。"""
        from app.database import get_db
        from app.algorithm.crypto import decrypt_key

        db = get_db()

        if provider_id:
            row = db.execute(
                "SELECT api_host, api_key_encrypted FROM model_providers "
                "WHERE provider_id=? AND is_enabled=1",
                (provider_id,),
            ).fetchone()
            db.close()
            if not row:
                logger.warning(f"resolve: provider '{provider_id}' 不存在或未启用")
                return None
            api_key = decrypt_key(row["api_key_encrypted"]) if row["api_key_encrypted"] else ""
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
            "SELECT provider_id, api_host, api_key_encrypted, models FROM model_providers "
            "WHERE is_enabled=1 AND api_key_encrypted IS NOT NULL "
            "ORDER BY id ASC"
        ).fetchall()
        db.close()

        for r in rows:
            models_raw = r["models"] if isinstance(r["models"], list) else (json.loads(r["models"]) if r["models"] else [])
            # 标准化每个模型条目后按 id 比较
            if not models_raw:
                api_key = decrypt_key(r["api_key_encrypted"]) if r["api_key_encrypted"] else ""
                if api_key:
                    return ModelConfig(
                        api_key=api_key,
                        api_host=r["api_host"],
                        model=model,
                        provider_id=r["provider_id"],
                    )
            else:
                for m in models_raw:
                    if get_model_id(m) == model:
                        api_key = decrypt_key(r["api_key_encrypted"]) if r["api_key_encrypted"] else ""
                        if api_key:
                            return ModelConfig(
                                api_key=api_key,
                                api_host=r["api_host"],
                                model=model,
                                provider_id=r["provider_id"],
                            )

        logger.warning(f"resolve: 模型 '{model}' 未在任何启用的供应商中找到")
        return None


model_runtime = ModelRuntime()
