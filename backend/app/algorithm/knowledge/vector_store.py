"""
向量存储 — Cherry Studio 模式：base_id + item_id 关联 knowledge_items

使用 pgvector（PostgreSQL）或 BLOB（SQLite）持久化向量。
兼容原有 VectorStore 接口，新增 replaceByExternalId 语义。
"""
from __future__ import annotations
import json
import logging
import re
from typing import Optional

from app.database import get_db

logger = logging.getLogger(__name__)


class VectorStore:
    """持久化向量存储 — Cherry Studio replaceByExternalId 语义。

    核心方法：
    - replace_by_external_id(base_id, item_id, vectors, metadata)
        原子替换：先删除该 item 的所有旧向量节点，再插入新节点（事务保证）。
        传空 vectors 表示清除该 item 的所有向量。
    - search(base_id, query_vector, top_k) — 按 base_id 过滤检索
    - delete_by_external_id(item_id) — 删除某个 item 的所有向量
    """

    def __init__(self, user_id: int, dimensions: int = 1024):
        self.user_id = user_id
        self.dimensions = dimensions

    def replace_by_external_id(
        self,
        base_id: str,
        item_id: str,
        vectors: list[list[float]],
        metadata: list[dict],
    ):
        """原子替换：先删除该 item 的所有旧节点，再插入新节点。"""
        if not vectors:
            # 空节点 = 清除该 item 的所有向量
            self.delete_by_external_id(item_id)
            return

        db = get_db()
        try:
            # 1. 删除该 item 的所有旧向量
            db.execute(
                "DELETE FROM knowledge_vectors WHERE item_id = ?",
                (item_id,),
            )

            # 2. 插入新向量
            for vec, meta in zip(vectors, metadata):
                vec_json = json.dumps(vec)
                db.execute(
                    """INSERT INTO knowledge_vectors
                       (user_id, base_id, item_id, chunk_index, text, embedding)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        self.user_id,
                        base_id,
                        item_id,
                        meta.get("chunk_idx", 0),
                        meta.get("text", ""),
                        vec_json,
                    ),
                )
            db.commit()
            logger.debug(f"已替换 item={item_id} 的向量: {len(vectors)} 个分块")
        except Exception:
            db.rollback()
            logger.exception("向量替换失败")
            raise
        finally:
            db.close()

    def search(
        self,
        base_id: str,
        query_vector: list[float],
        top_k: int = 5,
        query_text: Optional[str] = None,
        mode: str = "vector",
        alpha: float = 0.0,
    ) -> list[dict]:
        """按 base_id 过滤的 Top-K 检索。

        Args:
            base_id: 知识库 ID
            query_vector: 查询向量
            top_k: 返回数量
            query_text: 原始查询文本（混合模式需要）
            mode: 'vector' 纯向量检索, 'hybrid' 混合检索（向量 + 关键词）
            alpha: 混合模式中关键词得分的权重（0 = 纯向量, 1 = 纯关键词）
        """
        db = get_db()
        try:
            if self._is_sqlite():
                return self._search_sqlite(base_id, query_vector, top_k, query_text, mode, alpha)
            else:
                return self._search_pg(base_id, query_vector, top_k, query_text, mode, alpha)
        except Exception:
            logger.exception("向量检索失败")
            return []
        finally:
            db.close()

    def _is_sqlite(self) -> bool:
        from app.database import is_postgres
        return not is_postgres()

    def _search_sqlite(
        self,
        base_id: str,
        query_vector: list[float],
        top_k: int,
        query_text: Optional[str] = None,
        mode: str = "vector",
        alpha: float = 0.0,
    ) -> list[dict]:
        """SQLite 环境下用 Python 计算余弦相似度，可选混合检索（余弦 + 关键词 BM25）。"""
        import numpy as np

        db = get_db()
        rows = db.execute(
            "SELECT id, item_id, chunk_index, text, embedding FROM knowledge_vectors WHERE base_id = ?",
            (base_id,),
        ).fetchall()
        db.close()

        if not rows:
            return []

        q = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []

        # 预处理：查询关键词（混合模式用）
        query_keywords: set[str] = set()
        if mode == "hybrid" and alpha > 0 and query_text:
            query_keywords = set(
                w.lower()
                for w in re.split(r"[^\w]+", query_text)
                if w.strip() and len(w.strip()) > 1
            )

        results = []
        for r in rows:
            try:
                vec = np.array(json.loads(r["embedding"]), dtype=np.float32)
                v_norm = np.linalg.norm(vec)
                if v_norm == 0:
                    continue
                cosine_score = float(np.dot(q, vec) / (q_norm * v_norm))

                entry: dict = {
                    "id": r["id"],
                    "item_id": r["item_id"],
                    "chunk_index": r["chunk_index"],
                    "text": r["text"],
                    "score": cosine_score,
                }

                if query_keywords and r["text"]:
                    # TF-like BM25 分数：关键词在文本中的匹配比例
                    chunk_words = set(
                        w.lower()
                        for w in re.split(r"[^\w]+", r["text"])
                        if w.strip()
                    )
                    matches = len(query_keywords & chunk_words)
                    bm25_score = matches / len(query_keywords) if query_keywords else 0.0
                    entry["score"] = (1 - alpha) * cosine_score + alpha * bm25_score

                results.append(entry)
            except Exception:
                continue

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _search_pg(
        self,
        base_id: str,
        query_vector: list[float],
        top_k: int,
        query_text: Optional[str] = None,
        mode: str = "vector",
        alpha: float = 0.0,
    ) -> list[dict]:
        """PostgreSQL + pgvector 环境下用 <=> 算子，可选混合检索（余弦 + ts_rank 全文检索）。"""
        vec_json = json.dumps(query_vector)
        db = get_db()

        if mode == "hybrid" and alpha > 0 and query_text:
            # 混合检索：余弦相似度 + PostgreSQL 全文检索 ts_rank
            rows = db.execute(
                """SELECT id, item_id, chunk_index, text,
                          1 - (embedding <=> ?::vector) AS cosine_score,
                          ts_rank(to_tsvector('simple', COALESCE(text, '')), plainto_tsquery('simple', ?)) AS text_score
                    FROM knowledge_vectors
                    WHERE base_id = ?
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> ?::vector
                    LIMIT ?""",
                (vec_json, query_text, base_id, vec_json, top_k * 2),
            ).fetchall()
            db.close()

            if not rows:
                return []

            # 计算最大 text_score 用于归一化
            text_scores = [r["text_score"] or 0.0 for r in rows]
            max_text_score = max(text_scores) if text_scores else 1.0

            results = []
            for r in rows:
                cosine_score = r["cosine_score"]
                text_score = (r["text_score"] or 0.0) / max_text_score if max_text_score > 0 else 0.0
                blended = (1 - alpha) * cosine_score + alpha * text_score
                results.append({
                    "id": r["id"],
                    "item_id": r["item_id"],
                    "chunk_index": r["chunk_index"],
                    "text": r["text"],
                    "score": blended,
                })

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]
        else:
            # 纯向量检索
            rows = db.execute(
                """SELECT id, item_id, chunk_index, text,
                          1 - (embedding <=> ?::vector) AS score
                    FROM knowledge_vectors
                    WHERE base_id = ?
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> ?::vector
                    LIMIT ?""",
                (vec_json, base_id, vec_json, top_k),
            ).fetchall()
            db.close()
            return [dict(r) for r in rows]

    def count(self, base_id: Optional[str] = None) -> int:
        db = get_db()
        try:
            if base_id:
                row = db.execute(
                    "SELECT COUNT(*) AS cnt FROM knowledge_vectors WHERE base_id = ?",
                    (base_id,),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT COUNT(*) AS cnt FROM knowledge_vectors WHERE user_id = ?",
                    (self.user_id,),
                ).fetchone()
            return row["cnt"] if row else 0
        finally:
            db.close()

    def clear(self, base_id: Optional[str] = None):
        """清空向量。"""
        db = get_db()
        try:
            if base_id:
                db.execute(
                    "DELETE FROM knowledge_vectors WHERE base_id = ?",
                    (base_id,),
                )
            else:
                db.execute(
                    "DELETE FROM knowledge_vectors WHERE user_id = ?",
                    (self.user_id,),
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_by_external_id(self, item_id: str):
        """删除某个 knowledge_item 的所有向量节点。"""
        db = get_db()
        try:
            db.execute(
                "DELETE FROM knowledge_vectors WHERE item_id = ?",
                (item_id,),
            )
            db.commit()
            logger.debug(f"已删除 item={item_id} 的向量")
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_by_external_ids(self, item_ids: list[str]):
        """批量删除多个 knowledge_item 的向量节点。"""
        if not item_ids:
            return
        db = get_db()
        try:
            placeholders = ",".join("?" for _ in item_ids)
            db.execute(
                f"DELETE FROM knowledge_vectors WHERE item_id IN ({placeholders})",
                tuple(item_ids),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
