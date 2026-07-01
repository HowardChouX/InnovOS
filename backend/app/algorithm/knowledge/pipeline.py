"""
知识库文件导入管线 — Cherry Studio 模式

流程：上传 → 解析 → 分块 → 嵌入 → 原子替换索引（replaceByExternalId）
"""

import json
import logging

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
        self._embedder_config: dict | None = None
        self._reranker_config: dict | None = None
        self._chunk_config: dict | None = None

    def _load_chunk_config(self) -> dict:
        """加载知识库级 / 全局级分块参数。"""
        if self._chunk_config is not None:
            return self._chunk_config

        chunk_size: int | None = None
        chunk_overlap: int | None = None

        # 1. 知识库级配置
        if self.base_id and self.base_id != "default":
            from app.database import get_db

            db = get_db()
            try:
                row = db.execute(
                    "SELECT chunk_size, chunk_overlap FROM knowledge_bases WHERE id=? AND user_id=?",
                    (self.base_id, self.user_id),
                ).fetchone()
            finally:
                db.close()
            if row and row["chunk_size"]:
                try:
                    chunk_size = int(row["chunk_size"])
                except (ValueError, TypeError):
                    pass
            if row and row["chunk_overlap"]:
                try:
                    chunk_overlap = int(row["chunk_overlap"])
                except (ValueError, TypeError):
                    pass

        # 2. 全局默认值
        if chunk_size is None or chunk_overlap is None:
            try:
                from app.database import get_db

                db = get_db()
                rows = db.execute(
                    "SELECT key, value FROM system_settings WHERE key IN (?, ?)",
                    ("chunk_size", "chunk_overlap"),
                ).fetchall()
                db.close()
                cfg = {r["key"]: r["value"] for r in rows}
                if chunk_size is None:
                    chunk_size = int(cfg.get("chunk_size", 512))
                if chunk_overlap is None:
                    chunk_overlap = int(cfg.get("chunk_overlap", 64))
            except Exception:
                pass

        chunk_size = chunk_size or 512
        chunk_overlap = chunk_overlap or 64
        self._chunk_config = {"chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
        return self._chunk_config

    def _load_model_configs(self):
        """从知识库配置中加载嵌入和重排模型配置。"""
        if self._embedder_config is not None:
            return

        # 1. 知识库级模型配置
        if self.base_id and self.base_id != "default":
            from app.database import get_db

            db = get_db()
            try:
                row = db.execute(
                    "SELECT embedding_model_id, rerank_model_id FROM knowledge_bases WHERE id=? AND user_id=?",
                    (self.base_id, self.user_id),
                ).fetchone()
            finally:
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
        chunk_cfg = self._load_chunk_config()
        retriever = get_retriever(
            self.user_id,
            embedder_config=self._embedder_config,
            reranker_config=self._reranker_config,
        )
        result = await retriever.index_item(
            self.base_id, item_id, content,
            chunk_size=chunk_cfg["chunk_size"],
            chunk_overlap=chunk_cfg["chunk_overlap"],
        )

        # 后台重建 BM25 索引（异步，不阻塞）
        import asyncio
        try:
            asyncio.create_task(self._rebuild_bm25())
        except Exception:
            pass

        return result

    async def _rebuild_bm25(self):
        """后台重建 BM25 关键词索引。"""
        try:
            from app.algorithm.knowledge.bm25_index import bm25_manager
            bm25_manager.build_base(self.base_id, self.user_id)
        except Exception as e:
            logger.warning(f"BM25 重建失败（非致命）: {e}")

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        use_rerank: bool = True,
        search_mode: str | None = None,
        hybrid_alpha: float | None = None,
    ) -> list[dict]:
        """RAG 检索（按 base_id 过滤，支持重排）。

        top_k/search_mode/hybrid_alpha 为 None 时从全局设置读取默认值。
        """
        # 读取全局 RAG 默认值
        threshold_val: float | None = None
        try:
            from app.database import get_db

            db = get_db()
            try:
                rows = db.execute(
                    "SELECT key, value FROM system_settings WHERE key IN (?, ?, ?, ?, ?)",
                    ("search_mode", "hybrid_alpha", "rag_rerank_model", "document_count", "threshold"),
                ).fetchall()
            finally:
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
            try:
                if cfg.get("threshold"):
                    threshold_val = float(cfg["threshold"])
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse threshold value: {e}")
        except Exception as e:
            logger.warning(f"知识库管道异常: {e}")
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

            # 1. 语义向量检索
            if use_rerank and self._reranker_config:
                results = await retriever.search_with_rerank(
                    self.base_id,
                    query,
                    top_k * 2,
                    rerank_top_k=top_k,
                    search_mode=search_mode,
                    hybrid_alpha=hybrid_alpha,
                )
            else:
                results = await retriever.search(
                    self.base_id,
                    query,
                    top_k,
                    search_mode=search_mode,
                    hybrid_alpha=hybrid_alpha,
                )

            # 2. BM25 关键词检索 + 混合合并
            try:
                from app.algorithm.knowledge.bm25_index import bm25_manager, hybrid_merge

                bm25_docs = bm25_manager.search(self.base_id, query, top_k=top_k)
                if bm25_docs:
                    results = hybrid_merge(
                        results, bm25_docs, alpha=hybrid_alpha, top_k=top_k
                    )
                    logger.debug(f"BM25 混合完成：{len(results)} 条结果")
            except Exception:
                pass  # BM25 不可用时静默降级

            # 按阈值过滤
            if threshold_val and threshold_val > 0:
                results = [r for r in results if r.get("score", 0) >= threshold_val]
            return results
        except Exception as e:
            logger.warning(f"检索失败: {e}")
            return []


# 获取指定供应商的嵌入模型 API 配置
def get_embedding_api_config(provider_id: str = "") -> dict:
    """⚠️ 未使用 — 嵌入配置已在 _load_model_configs 中解析。保留用于向后兼容。"""
    from app.algorithm.model_service import _get_provider_api_key
    from app.database import get_db

    db = get_db()
    try:
        if provider_id:
            row = db.execute(
                "SELECT api_host, api_model, models FROM model_providers WHERE provider_id=? AND is_enabled=1",
                (provider_id,),
            ).fetchone()
        else:
            row = db.execute(
                "SELECT api_host, api_model, models FROM model_providers WHERE is_enabled=1 LIMIT 1",
            ).fetchone()
    finally:
        db.close()

    if not row:
        return {}

    pid = provider_id or row.get("provider_id", "")
    api_key = _get_provider_api_key(pid)
    if not api_key:
        return {}

    api_host = row["api_host"]

    models_raw = (
        row["models"] if isinstance(row["models"], list) else (json.loads(row["models"]) if row["models"] else [])
    )
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
