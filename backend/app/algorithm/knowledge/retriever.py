"""
RAG 检索管线 — Cherry Studio 模式

整合 chunker、embedder、reranker、vector_store。
每个 knowledge_item 通过 replaceByExternalId 原子索引/替换向量节点。
"""
from __future__ import annotations
import logging
from typing import Optional

from app.algorithm.knowledge.chunker import chunk_document
from app.algorithm.knowledge.embedder import Embedder
from app.algorithm.knowledge.vector_store import VectorStore

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """RAG 检索管线 — 管理知识项索引和向量检索。"""

    def __init__(
        self,
        user_id: int,
        embedder_config: Optional[dict] = None,
        reranker_config: Optional[dict] = None,
    ):
        self.user_id = user_id
        self.chunker = chunk_document

        # 嵌入器
        if embedder_config:
            self.embedder = Embedder(
                api_key=embedder_config.get("api_key", ""),
                api_host=embedder_config.get("api_host", ""),
                model=embedder_config.get("model", "BAAI/bge-large-zh-v1.5"),
            )
        else:
            self.embedder = Embedder()

        # 重排器配置（按需创建）
        self._reranker_config = reranker_config or {}
        self._reranker = None

        # 向量存储
        self.vector_store = VectorStore(user_id=self.user_id)

    async def index_item(self, base_id: str, item_id: str, content: str, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None) -> int:
        """索引单个知识项：分块 → 向量化 → 原子替换存储。返回分块数。

        使用 replaceByExternalId 语义：先删除该 item 的所有旧向量节点，再插入新节点。
        """
        import time
        t0 = time.time()
        content_len = len(content)
        logger.info(f"索引开始 item={item_id} 内容长度={content_len}")

        # 从全局设置读取分块参数
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
                chunk_size = chunk_size or 512
                chunk_overlap = chunk_overlap or 64

        chunks = self.chunker(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        t1 = time.time()
        logger.info(f"  分块完成: {len(chunks)} 块 ({((t1-t0)*1000):.0f}ms)")
        if not chunks:
            self.vector_store.replace_by_external_id(base_id, item_id, [], [])
            logger.info(f"  空内容，已清除向量")
            return 0

        texts = [c["text"] for c in chunks]
        logger.info(f"  开始向量化: {len(texts)} 段文本...")
        vectors = await self.embedder.embed(texts)
        t2 = time.time()
        logger.info(f"  向量化完成: {len(vectors)} 个向量, 维度={len(vectors[0]) if vectors else 0} ({((t2-t1)*1000):.0f}ms)")

        metadata = [
            {"chunk_idx": c["index"], "text": c["text"]}
            for c in chunks
        ]
        self.vector_store.replace_by_external_id(base_id, item_id, vectors, metadata)
        t3 = time.time()
        logger.info(f"  向量写入完成 ({((t3-t2)*1000):.0f}ms)")
        logger.info(f"知识项 {item_id} 索引完成: {len(chunks)} 个分块, 总耗时 {((t3-t0)*1000):.0f}ms")
        return len(chunks)

    async def search(
        self,
        base_id: str,
        query: str,
        top_k: int = 5,
        search_mode: str = "vector",
        hybrid_alpha: float = 0.3,
    ) -> list[dict]:
        """按 base_id 检索与查询最相关的文档片段。

        Args:
            base_id: 知识库 ID
            query: 查询文本
            top_k: 返回数量
            search_mode: 'vector' 纯向量检索, 'hybrid' 混合检索（向量 + 关键词）
            hybrid_alpha: 混合模式中关键词得分的权重（0 = 纯向量, 1 = 纯关键词）
        """
        if self.vector_store.count(base_id) == 0:
            return []

        query_vector = (await self.embedder.embed([query]))[0]
        results = self.vector_store.search(
            base_id,
            query_vector,
            top_k,
            query_text=query,
            mode=search_mode,
            alpha=hybrid_alpha,
        )
        return results

    def is_indexed(self, item_id: str) -> bool:
        """检查知识项是否已索引。"""
        return self.vector_store.count() > 0  # 简化检查

    @property
    def reranker(self):
        """懒加载重排器。"""
        if self._reranker is None and self._reranker_config:
            from app.algorithm.knowledge.reranker import Reranker

            self._reranker = Reranker(
                api_key=self._reranker_config.get("api_key", ""),
                api_host=self._reranker_config.get("api_host", ""),
                model=self._reranker_config.get("model", "BAAI/bge-reranker-v2-m3"),
            )
        return self._reranker

    async def search_with_rerank(
        self,
        base_id: str,
        query: str,
        top_k: int = 10,
        rerank_top_k: int = 5,
        search_mode: str = "vector",
        hybrid_alpha: float = 0.3,
    ) -> list[dict]:
        """检索 + 重排。"""
        results = await self.search(
            base_id, query, top_k,
            search_mode=search_mode,
            hybrid_alpha=hybrid_alpha,
        )
        if not results or not self.reranker:
            return results

        documents = [r["text"] for r in results]
        reranked = await self.reranker.rerank(query, documents, rerank_top_k)
        if not reranked:
            return results

        # 将重排结果映射回原始数据
        mapped = []
        for r in reranked:
            idx = r["index"]
            if idx < len(results):
                mapped.append({
                    **results[idx],
                    "score": r["relevance_score"],
                    "rank": len(mapped) + 1,
                })
        return mapped

    @property
    def total_chunks(self) -> int:
        return self.vector_store.count()


# 全局检索器缓存（主要缓存 embedder/reranker 配置）
_retrievers: dict[int, KnowledgeRetriever] = {}


def get_retriever(
    user_id: int,
    embedder_config: Optional[dict] = None,
    reranker_config: Optional[dict] = None,
) -> KnowledgeRetriever:
    """获取或创建用户的检索器实例。"""
    if user_id not in _retrievers or embedder_config is not None:
        _retrievers[user_id] = KnowledgeRetriever(
            user_id,
            embedder_config=embedder_config,
            reranker_config=reranker_config,
        )
    return _retrievers[user_id]


def rebuild_retriever_from_db(user_id: int):
    """启动时重建检索器。"""
    retriever = get_retriever(user_id)
    count = retriever.vector_store.count()
    if count > 0:
        logger.info(f"用户 {user_id} 已有 {count} 条向量数据")
