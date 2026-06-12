"""
专利语义检索引擎 — 复用知识库 Embedder 做向量检索
"""
import json
import logging
import time
from typing import Any

import numpy as np

from app.database import get_db
from app.algorithm.knowledge.embedder import Embedder

logger = logging.getLogger(__name__)


class PatentSearchEngine:
    """专利语义检索 — 复用 Embedder 进行向量化搜索"""

    def __init__(self):
        self._embedder: Embedder | None = None
        self._patent_cache: list[dict] | None = None
        self._cache_time = 0
        self._cache_ttl = 60

    def _get_embedder(self) -> Embedder | None:
        if self._embedder is not None:
            return self._embedder
        try:
            from app.algorithm.model_resolver import model_resolver
            from app.algorithm.model_runtime import ModelRuntime
            cfg = model_resolver.resolve_embedding()
            if cfg:
                self._embedder = Embedder(api_key=cfg.api_key, api_host=cfg.api_host, model=cfg.model_id)
            else:
                cfg2 = ModelRuntime.resolve_first_embedding()
                if cfg2:
                    self._embedder = Embedder(api_key=cfg2.api_key, api_host=cfg2.api_host, model=cfg2.model)
            return self._embedder
        except Exception as e:
            logger.warning(f"Embedder init failed: {e}")
        return None

    def _load_patents(self) -> list[dict]:
        now = time.time()
        if self._patent_cache and (now - self._cache_time) < self._cache_ttl:
            return self._patent_cache
        db = get_db()
        rows = db.execute("SELECT id, title, abstract, patent_number, relevance_score FROM patents ORDER BY relevance_score DESC").fetchall()
        db.close()
        self._patent_cache = [dict(r) for r in rows]
        self._cache_time = now
        logger.info(f"Loaded {len(self._patent_cache)} patents")
        return self._patent_cache

    async def search(self, query: str, top_k: int = 10, min_score: float = 0.0) -> list[dict]:
        embedder = self._get_embedder()
        if not embedder:
            return self._fallback_search(query, top_k)

        patents = self._load_patents()
        if not patents:
            return []

        texts = [f"{p['title']} {p.get('abstract', '')}"[:1000] for p in patents]

        batch_start = time.time()
        try:
            embeddings = await embedder.embed(texts)
        except Exception as e:
            logger.warning(f"Embed failed: {e}, fallback to LIKE")
            return self._fallback_search(query, top_k)

        if not embeddings or len(embeddings) != len(texts):
            return self._fallback_search(query, top_k)

        logger.info(f"Embedded {len(texts)} patents in {time.time()-batch_start:.1f}s")

        try:
            query_emb = await embedder.embed([query])
        except Exception as e:
            logger.warning(f"Query embed failed: {e}")
            return self._fallback_search(query, top_k)

        if not query_emb or len(query_emb) == 0:
            return self._fallback_search(query, top_k)

        patent_vecs = np.array(embeddings)
        q_vec = np.array(query_emb[0])
        patent_norm = np.linalg.norm(patent_vecs, axis=1, keepdims=True)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return self._fallback_search(query, top_k)
        patent_norm = np.where(patent_norm == 0, 1, patent_norm)
        similarities = (patent_vecs @ q_vec) / (patent_norm.flatten() * q_norm)

        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for i in top_indices:
            score = float(similarities[i])
            if score < min_score:
                continue
            p = patents[i]
            results.append({
                "title": p["title"],
                "abstract": p.get("abstract", ""),
                "patent_number": p.get("patent_number", ""),
                "relevance": round(score * 100),
                "score": round(score, 4),
            })

        return results

    def _fallback_search(self, query: str, top_k: int = 10) -> list[dict]:
        keywords = [w.strip() for w in query.replace("，", " ").replace("、", " ").split() if len(w.strip()) > 1]
        keywords = keywords[:5]
        if not keywords:
            return []

        db = get_db()
        or_conds = []
        params = []
        for kw in keywords:
            like = f"%{kw}%"
            or_conds.append("(title LIKE ? OR abstract LIKE ?)")
            params.extend([like, like])

        sql = f"SELECT * FROM patents WHERE {' OR '.join(or_conds)} ORDER BY relevance_score DESC LIMIT {top_k}"
        rows = db.execute(sql, params).fetchall()
        db.close()

        return [
            {
                "title": r["title"],
                "abstract": r.get("abstract", ""),
                "patent_number": r.get("patent_number", ""),
                "relevance": r.get("relevance_score", 0),
            }
            for r in rows
        ]
