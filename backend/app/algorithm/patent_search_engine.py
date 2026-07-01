"""
专利语义检索引擎 — 上传时自动嵌入，检索时语义搜索

嵌入模型获取逻辑（与 knowledge pipeline 一致）：
1. 全局系统嵌入模型分配（model_resolver.resolve_embedding）
2. 降级：从所有已配置的 embedding Key 中选第一个可用
"""

import json
import logging

from app.database import get_db

logger = logging.getLogger(__name__)


def _get_embedder_config():
    """获取嵌入模型配置（从全局设置 → 首模型降级）"""
    try:
        from app.algorithm.model_resolver import model_resolver

        s = model_resolver.get_assigned_settings()
        embed_model = s.get("embedding_model") or ""
        if embed_model and ":" in embed_model:
            resolved = model_resolver.resolve(embed_model)
            if resolved:
                return {
                    "api_key": resolved.api_key,
                    "api_host": resolved.api_host,
                    "model": resolved.model_id,
                }

        # 降级：选第一个可用 embedding key
        from app.algorithm.model_runtime import ModelRuntime

        cfg = ModelRuntime.resolve_first_embedding()
        if cfg:
            return {
                "api_key": cfg.api_key,
                "api_host": cfg.api_host,
                "model": cfg.model,
            }
    except Exception as e:
        logger.warning(f"获取嵌入模型配置失败: {e}")
    return None


PATENT_VECTOR_DIM = 4000  # halfvec HNSW 索引限制 4000 维


def init_patent_vectors_table():
    """确保 patent_vectors 表存在"""
    from app.database import get_db

    db = get_db()
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS patent_vectors (
            patent_id INTEGER PRIMARY KEY REFERENCES patents(id) ON DELETE CASCADE,
            embedding halfvec({PATENT_VECTOR_DIM}),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        )
    """)
    db.commit()
    db.close()


class PatentSearchEngine:
    """专利语义检索引擎"""

    def __init__(self):
        from app.algorithm.knowledge.embedder import Embedder

        cfg = _get_embedder_config()
        if cfg:
            self.embedder = Embedder(
                api_key=cfg["api_key"],
                api_host=cfg["api_host"],
                model=cfg["model"],
            )
        else:
            self.embedder = None
            logger.warning("嵌入模型未配置，向量搜索不可用。需在「模型服务」中添加 embedding API Key")

    async def embed_text(self, text: str) -> list[float]:
        """单条文本向量化"""
        if not self.embedder:
            raise RuntimeError("嵌入模型未配置，请在模型服务中配置嵌入模型")
        results = await self.embedder.embed([text])
        return results[0] if results else []

    async def index_patent(
        self, patent_id: int, title: str, abstract: str, claims: str = "", description: str = ""
    ) -> bool:
        """对单个专利生成向量并存储（title + abstract + claims + description）"""
        text = "。".join(filter(None, [title, abstract, claims, description])).strip()
        if not text.strip():
            return False
        return await self._store_vector(patent_id, text)

    async def index_patent_with_content(self, patent_id: int, full_text: str) -> bool:
        """对单个专利全文生成向量（PDF 上传用）"""
        return await self._store_vector(patent_id, full_text)

    async def _store_vector(self, patent_id: int, text: str) -> bool:
        """嵌入并存储向量到数据库"""
        if not text.strip():
            return False
        vector = await self.embed_text(text)
        if not vector:
            return False
        vector = vector[:PATENT_VECTOR_DIM]
        db = get_db()
        try:
            vector_json = json.dumps(vector)
            db.execute(
                """INSERT INTO patent_vectors (patent_id, embedding, updated_at)
                   VALUES (%s, %s, to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
                   ON CONFLICT (patent_id)
                   DO UPDATE SET embedding=excluded.embedding, updated_at=excluded.updated_at""",
                (patent_id, vector_json),
            )
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"索引专利 {patent_id} 失败: {e}")
            return False
        finally:
            db.close()

    async def delete_patent(self, patent_id: int):
        """删除专利向量"""
        db = get_db()
        try:
            db.execute("DELETE FROM patent_vectors WHERE patent_id=%s", (patent_id,))
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"删除专利向量 {patent_id} 失败: {e}")
        finally:
            db.close()

    async def _vector_search(self, query: str, top_k: int = 5) -> list[dict]:
        """单次向量搜索"""
        q_vec = await self.embed_text(query)
        if not q_vec:
            return []

        q_vec = q_vec[:PATENT_VECTOR_DIM]
        q_json = json.dumps(q_vec)

        db = get_db()
        try:
            rows = db.execute(
                f"""SELECT p.id, p.title, p.abstract, p.description, p.patent_number, p.applicants,
                           1 - (pv.embedding <=> %s::halfvec({PATENT_VECTOR_DIM})) AS relevance
                   FROM patent_vectors pv
                   JOIN patents p ON p.id = pv.patent_id
                   WHERE pv.embedding IS NOT NULL
                   ORDER BY pv.embedding <=> %s::halfvec({PATENT_VECTOR_DIM})
                   LIMIT %s""",
                (q_json, q_json, top_k),
            ).fetchall()
            return rows
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
        finally:
            db.close()

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """语义搜索专利 — 直接用原始查询进行向量搜索"""
        if not query.strip():
            return []
        return await self._vector_search(query, top_k=top_k)

    async def backfill(self) -> int:
        """回填所有未嵌入的专利，使用 title + abstract + claims + description"""
        db = get_db()
        try:
            rows = db.execute(
                """SELECT p.id, p.title, p.abstract, p.claims, p.description FROM patents p
                   LEFT JOIN patent_vectors pv ON p.id = pv.patent_id
                   WHERE pv.patent_id IS NULL"""
            ).fetchall()
        except Exception:
            return 0
        finally:
            db.close()

        count = 0
        for row in rows:
            title = row["title"] or ""
            abstract = row["abstract"] or ""
            claims = row["claims"] or ""
            description = row["description"] or ""
            text = "。".join(filter(None, [title, abstract, claims, description])).strip()
            if not text.strip():
                continue
            vector = await self.embed_text(text)
            if not vector:
                continue
            vector = vector[:PATENT_VECTOR_DIM]
            db2 = get_db()
            try:
                db2.execute(
                    """INSERT INTO patent_vectors (patent_id, embedding, updated_at)
                       VALUES (%s, %s, to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
                       ON CONFLICT (patent_id)
                       DO UPDATE SET embedding=excluded.embedding, updated_at=excluded.updated_at""",
                    (row["id"], json.dumps(vector)),
                )
                db2.commit()
                count += 1
            except Exception as e:
                db2.rollback()
                logger.warning(f"回填专利 {row['id']} 失败: {e}")
            finally:
                db2.close()
        return count


# ── Module-level singleton ──────────────────────────────

_patent_search_engine: "PatentSearchEngine | None" = None


def get_patent_search_engine() -> PatentSearchEngine:
    """获取 PatentSearchEngine 单例（避免每次请求重建 _get_embedder_config）"""
    global _patent_search_engine
    if _patent_search_engine is None:
        _patent_search_engine = PatentSearchEngine()
    return _patent_search_engine
