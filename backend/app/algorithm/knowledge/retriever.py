"""
RAG 检索管线 — 整合 chunker、embedder、vector_store

借鉴 CherryStudio 的 KnowledgeOrchestrationService 架构。
"""
from __future__ import annotations
import logging
import json
from app.algorithm.knowledge.chunker import chunk_document
from app.algorithm.knowledge.embedder import Embedder
from app.algorithm.knowledge.vector_store import VectorStore

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """RAG 检索管线 — 管理文档索引和向量检索。"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.chunker = chunk_document
        self.embedder = Embedder()
        self.vector_store = VectorStore()
        self._indexed_doc_ids: set[int] = set()

    async def index_document(self, doc_id: int, content: str) -> int:
        """索引单个文档：分块 → 向量化 → 存储。返回分块数。"""
        chunks = self.chunker(content)
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        vectors = await self.embedder.embed(texts)
        metadata = [
            {"doc_id": doc_id, "chunk_idx": c["index"], "text": c["text"]}
            for c in chunks
        ]
        self.vector_store.add(vectors, metadata)
        self._indexed_doc_ids.add(doc_id)
        logger.info(f"文档 {doc_id} 索引完成: {len(chunks)} 个分块")
        return len(chunks)

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """检索与查询最相关的文档片段。"""
        if self.vector_store.count() == 0:
            return []

        query_vector = (await self.embedder.embed([query]))[0]
        results = self.vector_store.search(query_vector, top_k)
        return results

    def is_indexed(self, doc_id: int) -> bool:
        return doc_id in self._indexed_doc_ids

    @property
    def total_chunks(self) -> int:
        return self.vector_store.count()


# 全局用户检索器缓存（内存中，重启后重建）
_retrievers: dict[int, KnowledgeRetriever] = {}


def get_retriever(user_id: int) -> KnowledgeRetriever:
    """获取或创建用户的检索器实例。"""
    if user_id not in _retrievers:
        _retrievers[user_id] = KnowledgeRetriever(user_id)
    return _retrievers[user_id]


def rebuild_retriever_from_db(user_id: int):
    """从数据库重建检索器（启动时调用）。"""
    from app.database import get_db
    retriever = get_retriever(user_id)
    db = get_db()
    rows = db.execute(
        "SELECT id, content FROM knowledge_docs WHERE user_id=? AND is_active=1",
        (user_id,),
    ).fetchall()
    db.close()

    for row in rows:
        if not retriever.is_indexed(row["id"]):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    continue  # 启动期间跳过，按需索引
                loop.run_until_complete(retriever.index_document(row["id"], row["content"]))
            except Exception:
                pass
