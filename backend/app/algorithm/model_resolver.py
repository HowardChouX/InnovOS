"""
模型解析服务 — 读取全局模型分配 → 解析 Provider API 配置

借鉴 Cherry Studio AiService.buildAgentParamsFor() 模式：
  1. 读 Preference（我们的 system_settings）获取分配模型
  2. 解析 "providerId:modelId" → provider + model
  3. 查 model_providers 表获取 api_key 和 api_host
  4. 返回完整 API 调用配置

使用方：
  - ai_client.chat_completion() — LLM 调用
  - knowledge pipeline — 嵌入/重排
  - 后续 patent knowledge base — 嵌入
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ResolvedModelConfig:
    """解析后的 API 调用配置"""
    provider_id: str
    model_id: str          # API 调用时用的 model 名
    api_key: str
    api_host: str


class ModelResolver:
    """模型配置解析器"""

    @staticmethod
    def get_assigned_settings() -> dict:
        """从 system_settings 表读取全局模型分配"""
        from app.database import get_db
        db = get_db()
        rows = db.execute(
            "SELECT key, value FROM system_settings WHERE key IN ('chat_model','embedding_model','rerank_model')"
        ).fetchall()
        db.close()
        result = {"chat_model": None, "embedding_model": None, "rerank_model": None}
        for r in rows:
            result[r["key"]] = r["value"]
        return result

    @staticmethod
    def parse_composite_id(composite_id: str) -> tuple[str, str]:
        """解析 'providerId:modelId' 格式为 (provider_id, model_id)"""
        if not composite_id:
            return "", ""
        if ":" in composite_id:
            parts = composite_id.split(":", 1)
            return parts[0], parts[1]
        return "", composite_id

    @classmethod
    def resolve_chat(cls) -> Optional[ResolvedModelConfig]:
        """解析全局分配的聊天模型配置"""
        settings = cls.get_assigned_settings()
        composite = settings.get("chat_model")
        if not composite:
            logger.warning("resolve_chat: 未配置聊天模型")
            return None
        return cls.resolve(composite)

    @classmethod
    def resolve_embedding(cls) -> Optional[ResolvedModelConfig]:
        """解析全局分配的嵌入模型配置"""
        settings = cls.get_assigned_settings()
        composite = settings.get("embedding_model")
        if not composite:
            logger.warning("resolve_embedding: 未配置嵌入模型")
            return None
        return cls.resolve(composite)

    @classmethod
    def resolve_rerank(cls) -> Optional[ResolvedModelConfig]:
        """解析全局分配的重排模型配置"""
        settings = cls.get_assigned_settings()
        composite = settings.get("rerank_model")
        if not composite:
            logger.warning("resolve_rerank: 未配置重排模型")
            return None
        return cls.resolve(composite)

    @classmethod
    def resolve(cls, composite_id: str) -> Optional[ResolvedModelConfig]:
        """解析 'providerId:modelId' → API 配置（公开方法）

        1. 解析 providerId:modelId
        2. 查 model_providers 表获取 api_key_encrypted + api_host
        3. 解密 api_key
        4. 返回 ResolvedModelConfig
        """
        from app.database import get_db
        from app.algorithm.crypto import decrypt_key

        provider_id, model_id = cls.parse_composite_id(composite_id)
        if not provider_id or not model_id:
            logger.warning(f"_resolve: 无效的模型 ID 格式: {composite_id}")
            return None

        db = get_db()
        row = db.execute(
            "SELECT api_host, api_key_encrypted FROM model_providers WHERE provider_id=? AND is_enabled=1",
            (provider_id,),
        ).fetchone()
        db.close()

        if not row:
            logger.warning(f"_resolve: provider '{provider_id}' 不存在或未启用")
            return None

        if not row["api_key_encrypted"]:
            logger.warning(f"_resolve: provider '{provider_id}' 未配置 API Key")
            return None

        try:
            api_key = decrypt_key(row["api_key_encrypted"])
        except Exception as e:
            logger.error(f"_resolve: API Key 解密失败: {e}")
            return None

        return ResolvedModelConfig(
            provider_id=provider_id,
            model_id=model_id,
            api_key=api_key,
            api_host=row["api_host"],
        )


# Singleton
model_resolver = ModelResolver()
