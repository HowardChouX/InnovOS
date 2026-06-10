"""
知识库文件导入管线 — Cherry Studio 模式

流程：上传 → 解析 → 分块 → 嵌入 → 原子替换索引（replaceByExternalId）
"""
import json
import logging
from typing import Any, Optional

from app.algorithm.file_parser import parse_file
from app.algorithm.model_runtime import ModelRuntime

logger = logging.getLogger(__name__)


class KnowledgePipeline:
    """文件导入管线，处理单个知识项的完整导入流程。

    Cherry Studio 模式：
    - 解析文件/文本 → 分块 → 嵌入 → retriever.index_item(base_id, item_id, content)
    - index_item 内部使用 replaceByExternalId 语义：先删旧节点，再插新节点（事务）
    """

    def __init__(self, user_id: int, base_id: str = "default"):
        self.user_id = user_id
        self.base_id = base_id
        self._embedder_config: Optional[dict] = None
        self._reranker_config: Optional[dict] = None

    def _load_model_configs(self):
        """从知识库配置中加载嵌入和重排模型配置。"""
        if self._embedder_config is not None:
            return

        # 1. 知识库级模型配置
        if self.base_id and self.base_id != "default":
            from app.database import get_db
            db = get_db()
            row = db.execute(
                "SELECT embedding_model_id, rerank_model_id FROM knowledge_bases WHERE id=? AND user_id=?",
                (self.base_id, self.user_id),
            ).fetchone()
            db.close()

            if row:
                if row["embedding_model_id"]:
                    cfg = ModelRuntime.resolve_embedding(row["embedding_model_id"])
                    if cfg:
                        self._embedder_config = {
                            "api_key": cfg.api_key,
                            "api_host": cfg.api_host,
                            "model": cfg.model,
                        }
                    else:
                        logger.warning(f"无法解析嵌入模型: {row['embedding_model_id']}")

                if row["rerank_model_id"]:
                    cfg = ModelRuntime.resolve_rerank(row["rerank_model_id"])
                    if cfg:
                        self._reranker_config = {
                            "api_key": cfg.api_key,
                            "api_host": cfg.api_host,
                            "model": cfg.model,
                        }
                    else:
                        logger.warning(f"无法解析重排模型: {row['rerank_model_id']}")

        # 2. 全局系统模型分配
        from app.algorithm.model_resolver import model_resolver

        if self._embedder_config is None:
            cfg = model_resolver.resolve_embedding()
            if cfg:
                self._embedder_config = {
                    "api_key": cfg.api_key,
                    "api_host": cfg.api_host,
                    "model": cfg.model_id,
                }
                logger.info(f"使用全局嵌入模型: {cfg.provider_id}/{cfg.model_id}")

        if self._reranker_config is None:
            cfg = model_resolver.resolve_rerank()
            if cfg:
                self._reranker_config = {
                    "api_key": cfg.api_key,
                    "api_host": cfg.api_host,
                    "model": cfg.model_id,
                }
                logger.info(f"使用全局重排模型: {cfg.provider_id}/{cfg.model_id}")

        # 3. 降级
        if self._embedder_config is None:
            cfg = ModelRuntime.resolve_first_embedding()
            if cfg:
                self._embedder_config = {
                    "api_key": cfg.api_key,
                    "api_host": cfg.api_host,
                    "model": cfg.model,
                }
                logger.info(f"使用降级嵌入模型: {cfg.provider_id}/{cfg.model}")

        if self._reranker_config is None:
            cfg = ModelRuntime.resolve_first_rerank()
            if cfg:
                self._reranker_config = {
                    "api_key": cfg.api_key,
                    "api_host": cfg.api_host,
                    "model": cfg.model,
                }
                logger.info(f"使用降级重排模型: {cfg.provider_id}/{cfg.model}")

    async def process_file(self, file_path: str, file_name: str) -> dict:
        """解析单个文件，返回标题和内容。"""
        parsed = parse_file(file_path)
        return {
            "title": parsed["title"] or file_name,
            "content": parsed["content"],
            "type": parsed["type"],
        }

    async def process_text(self, title: str, content: str, doc_type: str = "text") -> dict:
        """处理文本粘贴。"""
        return {"title": title, "content": content, "type": doc_type}

    async def index_item(self, item_id: str, content: str) -> int:
        """索引知识项内容到向量存储。

        使用 replaceByExternalId 语义：先删除该 item 的所有旧向量节点，再插入新节点。
        返回分块数。失败时异常冒泡 → job 重试 → 标记 failed（与 CherryStudio 一致）。
        """
        from app.algorithm.knowledge.retriever import get_retriever
        self._load_model_configs()
        retriever = get_retriever(
            self.user_id,
            embedder_config=self._embedder_config,
            reranker_config=self._reranker_config,
        )
        return await retriever.index_item(self.base_id, item_id, content)

    async def search(self, query: str, top_k: Optional[int] = None, use_rerank: bool = True,
                     search_mode: Optional[str] = None,
                     hybrid_alpha: Optional[float] = None) -> list[dict]:
        """RAG 检索（按 base_id 过滤，支持重排）。

        top_k/search_mode/hybrid_alpha 为 None 时从全局设置读取默认值。
        """
        # 读取全局 RAG 默认值
        try:
            from app.database import get_db
            db = get_db()
            rows = db.execute(
                "SELECT key, value FROM system_settings WHERE key IN (?, ?, ?, ?, ?)",
                ("search_mode", "hybrid_alpha", "rag_rerank_model", "document_count", "threshold"),
            ).fetchall()
            db.close()
            cfg = {r["key"]: r["value"] for r in rows}
            if search_mode is None:
                search_mode = cfg.get("search_mode") or "hybrid"
            if hybrid_alpha is None:
                try:
                    hybrid_alpha = float(cfg["hybrid_alpha"]) if cfg.get("hybrid_alpha") else 0.3
                except (ValueError, TypeError):
                    hybrid_alpha = 0.3
            if top_k is None:
                try:
                    top_k = int(cfg["document_count"]) if cfg.get("document_count") else 10
                except (ValueError, TypeError):
                    top_k = 10
            if not use_rerank:
                use_rerank = bool(cfg.get("rag_rerank_model"))
            threshold_val: Optional[float] = None
            try:
                if cfg.get("threshold"):
                    threshold_val = float(cfg["threshold"])
            except (ValueError, TypeError):
                pass
        except Exception:
            if search_mode is None:
                search_mode = "hybrid"
            if hybrid_alpha is None:
                hybrid_alpha = 0.3
            if top_k is None:
                top_k = 10

        try:
            from app.algorithm.knowledge.retriever import get_retriever
            self._load_model_configs()
            retriever = get_retriever(
                self.user_id,
                embedder_config=self._embedder_config,
                reranker_config=self._reranker_config,
            )
            if use_rerank and self._reranker_config:
                results = await retriever.search_with_rerank(
                    self.base_id, query, top_k * 2, rerank_top_k=top_k,
                    search_mode=search_mode, hybrid_alpha=hybrid_alpha,
                )
            else:
                results = await retriever.search(
                    self.base_id, query, top_k,
                    search_mode=search_mode, hybrid_alpha=hybrid_alpha,
                )
            # 按阈值过滤
            if threshold_val and threshold_val > 0:
                results = [r for r in results if r.get("score", 0) >= threshold_val]
            return results
        except Exception as e:
            logger.warning(f"检索失败: {e}")
            return []


# 获取指定供应商的嵌入模型 API 配置
def get_embedding_api_config(provider_id: str = "") -> dict:
    """从已配置的模型服务中获取嵌入模型 API 配置。"""
    from app.database import get_db

    db = get_db()
    if provider_id:
        row = db.execute(
            "SELECT api_host, api_key_encrypted, api_model, models FROM model_providers WHERE provider_id=? AND is_enabled=1",
            (provider_id,),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT api_host, api_key_encrypted, api_model, models FROM model_providers WHERE is_enabled=1 AND api_key_encrypted IS NOT NULL LIMIT 1",
        ).fetchone()
    db.close()

    if not row:
        return {}

    api_host = row["api_host"]
    api_key = row["api_key_encrypted"] if row["api_key_encrypted"] else ""

    models_raw = row["models"] if isinstance(row["models"], list) else (json.loads(row["models"]) if row["models"] else [])
    embed_keywords = ["embedding", "embed", "bge", "e5-", "text-embedding"]
    embed_model = ""
    for m in models_raw:
        ml = m.lower()
        if any(k in ml for k in embed_keywords):
            embed_model = m
            break
    if not embed_model:
        embed_model = row["api_model"] or "BAAI/bge-large-zh-v1.5"

    return {"api_key": api_key, "api_host": api_host, "model": embed_model}
