"""
向量存储 — 基于 numpy 的余弦相似度检索（借鉴 CherryStudio vectorstore/）

MVP 使用 numpy 实现，后期可迁移至 LibSQL 向量扩展。
"""
from __future__ import annotations
import math

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore
    _HAS_NUMPY = False


class VectorStore:
    """基于 numpy 的向量存储，支持余弦相似度 Top-K 检索。"""

    def __init__(self):
        self.vectors = None  # np.ndarray or list[list[float]]
        self.metadata: list[dict] = []

    def add(self, vectors: list[list[float]], metadata: list[dict]):
        """添加向量及其元数据。"""
        if not vectors:
            return

        if _HAS_NUMPY:
            new = np.array(vectors, dtype=np.float32)
            if self.vectors is None:
                self.vectors = new
            else:
                self.vectors = np.vstack([self.vectors, new])
        else:
            if self.vectors is None:
                self.vectors = [list(v) for v in vectors]
            else:
                self.vectors.extend([list(v) for v in vectors])

        self.metadata.extend(metadata)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict]:
        """余弦相似度 Top-K 检索。"""
        if self.vectors is None or len(self.metadata) == 0:
            return []

        if _HAS_NUMPY:
            return self._search_numpy(query_vector, top_k)
        return self._search_pure(query_vector, top_k)

    def _search_numpy(self, query_vector: list[float], top_k: int) -> list[dict]:
        query = np.array(query_vector, dtype=np.float32)
        norms = np.linalg.norm(self.vectors, axis=1)
        q_norm = np.linalg.norm(query)
        if q_norm == 0 or np.all(norms == 0):
            return []
        similarities = np.dot(self.vectors, query) / (norms * q_norm)
        k = min(top_k, len(similarities))
        top_indices = np.argsort(similarities)[-k:][::-1]
        return [
            {**self.metadata[i], "score": float(similarities[i])}
            for i in top_indices
        ]

    def _search_pure(self, query_vector: list[float], top_k: int) -> list[dict]:
        """纯 Python 余弦相似度（无 numpy 时的降级方案）。"""
        q_norm = math.sqrt(sum(x * x for x in query_vector))
        if q_norm == 0:
            return []

        scores = []
        for i, vec in enumerate(self.vectors):
            v_norm = math.sqrt(sum(x * x for x in vec))
            if v_norm == 0:
                scores.append((i, 0.0))
                continue
            dot = sum(a * b for a, b in zip(vec, query_vector))
            scores.append((i, dot / (v_norm * q_norm)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [
            {**self.metadata[i], "score": score}
            for i, score in scores[:top_k]
        ]

    def count(self) -> int:
        return len(self.metadata)

    def clear(self):
        self.vectors = None
        self.metadata.clear()
