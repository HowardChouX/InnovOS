"""
BM25 稀疏检索索引 — 关键词互补语义检索

基于 Local_Pdf_Chat_RAG 移植，适配 pgvector + jieba 中文分词。

原理：
- BM25 (Best Matching 25) 是经典信息检索算法，擅长精确关键词匹配
- 与向量语义检索互补：语义检索理解意图，BM25 匹配关键词
- 中文使用 jieba 分词，英文按空格分
- 混合检索（Hybrid Search）= 语义分数 × α + BM25分数 × (1-α)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from app.database import get_db

logger = logging.getLogger(__name__)

# 混合检索默认权重：0.7 语义 + 0.3 关键词
DEFAULT_HYBRID_ALPHA = 0.7


class BM25Index:
    """单个知识库的 BM25 索引。"""

    def __init__(self):
        self._index: BM25Okapi | None = None
        self._doc_ids: list[str] = []       # chunk_id → vector store id
        self._raw_texts: list[str] = []     # chunk text content

    def build(self, chunks: list[dict]) -> bool:
        """从 chunk 列表构建 BM25 索引。

        Args:
            chunks: [{"id": vector_store_id, "text": chunk_text}, ...]
        """
        if not chunks:
            self.clear()
            return False

        self._doc_ids = [c["id"] for c in chunks]
        self._raw_texts = [c.get("text", "") for c in chunks]
        self._index = BM25Okapi([list(jieba.cut(t)) for t in self._raw_texts])
        logger.info(f"BM25 索引构建完成：{len(chunks)} 个分块")
        return True

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """BM25 检索，返回 top_k 个结果。

        Returns:
            [{"id": vector_store_id, "score": bm25_score, "text": chunk_text}, ...]
        """
        if not self._index:
            return []

        tokenized = list(jieba.cut(query))
        scores = self._index.get_scores(tokenized)
        top_indices = np.argsort(scores)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            results.append({
                "id": self._doc_ids[idx],
                "score": float(scores[idx]),
                "text": self._raw_texts[idx],
            })
        return results

    def clear(self):
        self._index = None
        self._doc_ids = []
        self._raw_texts = []

    @property
    def size(self) -> int:
        return len(self._doc_ids)


class BM25IndexManager:
    """多知识库 BM25 索引管理器 — 按 base_id 分组。"""

    def __init__(self):
        self._indexes: dict[str, BM25Index] = defaultdict(BM25Index)

    def build_base(self, base_id: str, user_id: int) -> int:
        """从数据库读取知识库所有分块，构建 BM25 索引。"""
        db = get_db()
        try:
            rows = db.execute(
                """SELECT id, text FROM knowledge_vectors
                   WHERE base_id = %s AND user_id = %s
                   ORDER BY id""",
                (base_id, user_id),
            ).fetchall()
        finally:
            db.close()

        chunks = [{"id": str(r["id"]), "text": r.get("text", "")} for r in rows]
        if chunks:
            self._indexes[base_id].build(chunks)
        else:
            self._indexes[base_id].clear()
        return len(chunks)

    def search(self, base_id: str, query: str, top_k: int = 10) -> list[dict]:
        """对指定知识库执行 BM25 检索。"""
        return self._indexes[base_id].search(query, top_k)

    def remove_base(self, base_id: str):
        self._indexes.pop(base_id, None)

    def clear(self):
        self._indexes.clear()


def hybrid_merge(
    vector_results: list[dict],
    bm25_results: list[dict],
    alpha: float | None = None,
    top_k: int | None = None,
) -> list[dict]:
    """混合合并语义检索和 BM25 检索结果。

    使用加权分数：语义分数 × alpha + BM25分数 × (1-alpha)

    Args:
        vector_results: 语义检索结果 [{"id", "score", "text", ...}, ...]
        bm25_results: BM25 结果 [{"id", "score", "text"}, ...]
        alpha: 语义检索权重 (0-1)，默认 0.7
        top_k: 返回数量限制

    Returns:
        按混合分数降序排列的结果列表
    """
    if alpha is None:
        alpha = DEFAULT_HYBRID_ALPHA

    merged: dict[str, dict[str, Any]] = {}

    # 1. 语义检索结果（rank-based normalization）
    if vector_results:
        for i, r in enumerate(vector_results):
            doc_id = str(r.get("id", ""))
            if not doc_id:
                continue
            rank_score = 1.0 - (i / max(1, len(vector_results)))
            merged[doc_id] = {
                "id": doc_id,
                "score": alpha * rank_score,
                "text": r.get("text", ""),
                "item_id": r.get("item_id", ""),
                "chunk_index": r.get("chunk_index", 0),
            }

    # 2. BM25 结果（score normalization）
    if bm25_results:
        valid_scores = [r["score"] for r in bm25_results if r.get("score", 0) > 0]
        max_bm25 = max(valid_scores) if valid_scores else 1.0
        for r in bm25_results:
            doc_id = str(r.get("id", ""))
            if not doc_id:
                continue
            norm_score = r.get("score", 0) / max_bm25 if max_bm25 > 0 else 0
            if doc_id in merged:
                merged[doc_id]["score"] += (1 - alpha) * norm_score
            else:
                merged[doc_id] = {
                    "id": doc_id,
                    "score": (1 - alpha) * norm_score,
                    "text": r.get("text", ""),
                }

    # 3. 排序 + 截断
    result = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    if top_k:
        result = result[:top_k]
    return result


def hybrid_merge_docs(
    vector_docs: list[dict],
    bm25_docs: list[dict],
    alpha: float | None = None,
    top_k: int | None = None,
) -> list[dict]:
    """混合合并文档级检索结果（用于 pipeline 输出）。

    与 hybrid_merge 的区别：保留更多原始字段（item_id, chunk_index 等）。
    """
    return hybrid_merge(vector_docs, bm25_docs, alpha=alpha, top_k=top_k)


# 模块级单例
bm25_manager = BM25IndexManager()
