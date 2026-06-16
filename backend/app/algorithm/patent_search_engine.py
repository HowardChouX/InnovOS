"""
专利语义检索引擎 — 上传时自动嵌入，检索时语义搜索

嵌入模型获取逻辑（与 knowledge pipeline 一致）：
1. 全局系统嵌入模型分配（model_resolver.resolve_embedding）
2. 降级：从所有已配置的 embedding Key 中选第一个可用
"""
import json
import logging
import numpy as np
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
    from app.database import is_postgres, get_db
    db = get_db()
    if is_postgres():
        db.execute(f"""
            CREATE TABLE IF NOT EXISTS patent_vectors (
                patent_id INTEGER PRIMARY KEY REFERENCES patents(id) ON DELETE CASCADE,
                embedding halfvec({PATENT_VECTOR_DIM}),
                updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
    else:
        db.execute("""
            CREATE TABLE IF NOT EXISTS patent_vectors (
                patent_id INTEGER PRIMARY KEY,
                embedding TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
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

    async def embed_text(self, text: str) -> list[float]:
        """单条文本向量化"""
        if not self.embedder:
            raise RuntimeError("嵌入模型未配置，请在模型服务中配置嵌入模型")
        results = await self.embedder.embed([text])
        return results[0] if results else []

    async def index_patent(self, patent_id: int, title: str, abstract: str, claims: str = "") -> bool:
        """对单个专利生成向量并存储（title + abstract）"""
        text = f"{title}。{abstract}".strip()
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
                   VALUES (?, ?, to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
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
            db.execute("DELETE FROM patent_vectors WHERE patent_id=?", (patent_id,))
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"删除专利向量 {patent_id} 失败: {e}")
        finally:
            db.close()

    async def _expand_query(self, query: str) -> list[str]:
        """用 AI 将短查询扩展为多个技术方向描述"""
        try:
            from app.algorithm.ai_client import chat_completion

            prompt = f"""将以下搜索词扩展为3个相关的技术方向描述，用于专利语义检索。
每个方向要具体描述技术手段，而不是泛泛的方向。
只返回JSON数组，不要其他内容。

搜索词：{query}

示例：
输入："手机散热"
输出：["VC均热板散热技术", "石墨烯散热膜技术", "半导体制冷散热技术"]"""

            result = await chat_completion(
                system_prompt="你是一个专利检索专家。只返回JSON数组。",
                user_prompt=prompt,
                response_format=str,
            )
            if isinstance(result, str):
                import json as _json
                try:
                    result = _json.loads(result)
                except:
                    return [query]
            if isinstance(result, list) and len(result) > 0:
                return [query] + result
            return [query]
        except Exception as e:
            logger.warning(f"查询扩展失败: {e}")
            return [query]
        except Exception as e:
            logger.warning(f"查询扩展失败: {e}")
            return [query]

    async def _vector_search(self, query: str, top_k: int = 5) -> list[dict]:
        """单次向量搜索"""
        q_vec = await self.embed_text(query)
        if not q_vec:
            return []

        q_vec = q_vec[:PATENT_VECTOR_DIM]
        q_json = json.dumps(q_vec)

        import psycopg2
        from app.database import DATABASE_URL
        conn = psycopg2.connect(DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute(
                f"""SELECT p.id, p.title, p.abstract, p.description, p.patent_number, p.applicants,
                          1 - (pv.embedding <=> %s::halfvec({PATENT_VECTOR_DIM})) AS relevance
                   FROM patent_vectors pv
                   JOIN patents p ON p.id = pv.patent_id
                   WHERE pv.embedding IS NOT NULL
                   ORDER BY pv.embedding <=> %s::halfvec({PATENT_VECTOR_DIM})
                   LIMIT %s""",
                (q_json, q_json, top_k)
            )
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
        finally:
            conn.close()

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """语义搜索专利 — 查询扩展 + 多查询融合"""
        if not query.strip():
            return []

        # 1. AI 扩展查询
        expanded_queries = await self._expand_query(query)

        # 2. 每个扩展词分别搜索，合并去重取最优
        all_results = {}
        for q in expanded_queries:
            results = await self._vector_search(q, top_k=max(5, top_k))
            for r in results:
                pid = r["id"]
                if pid not in all_results or r["relevance"] > all_results[pid]["relevance"]:
                    all_results[pid] = r

        # 3. 按得分排序取 top-k
        ranked = sorted(all_results.values(), key=lambda x: x["relevance"], reverse=True)
        return ranked[:top_k]

    async def backfill(self) -> int:
        """回填所有未嵌入的专利，使用 title + abstract（更聚焦，提高相似度）"""
        db = get_db()
        try:
            rows = db.execute(
                """SELECT p.id, p.title, p.abstract FROM patents p
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
            text = f"{title}。{abstract}".strip()
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
                       VALUES (?, ?, to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
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
