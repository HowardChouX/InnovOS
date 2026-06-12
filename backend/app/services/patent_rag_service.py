"""
专利 RAG 检索服务 — 语义搜索相似专利

复用知识库管线：
  chunker.py → embedder.py → vector_store.py → retriever.py

专利向量使用独立命名空间：user_id=0, base_id='patent:global'
"""
import json
import logging
from typing import Optional

from app.algorithm.knowledge.chunker import chunk_document
from app.algorithm.knowledge.embedder import Embedder
from app.algorithm.knowledge.vector_store import VectorStore

logger = logging.getLogger(__name__)

PATENT_BASE_ID = "patent:global"
PATENT_USER_ID = 0


def _get_embedder_config() -> Optional[dict]:
    """从全局设置读取嵌入模型配置"""
    try:
        from app.database import get_db
        db = get_db()
        row = db.execute(
            "SELECT value FROM system_settings WHERE key='embedding_model'"
        ).fetchone()
        db.close()
        if not row or not row["value"]:
            return None

        model_id = row["value"]
        provider_id, model = model_id.split(":", 1) if ":" in model_id else ("", model_id)

        from app.algorithm.model_runtime import ModelRuntime
        cfg = ModelRuntime.resolve_embedding(model_id)
        if not cfg:
            return None
        return {
            "api_key": cfg.api_key,
            "api_host": cfg.api_host,
            "model": cfg.model,
        }
    except Exception as e:
        logger.warning(f"读取嵌入模型配置失败: {e}")
        return None


class PatentRagService:
    """专利 RAG 检索服务"""

    def __init__(self):
        embedder_config = _get_embedder_config()
        if embedder_config:
            self.embedder = Embedder(
                api_key=embedder_config["api_key"],
                api_host=embedder_config["api_host"],
                model=embedder_config["model"],
            )
        else:
            self.embedder = Embedder()
        self.vector_store = VectorStore(user_id=PATENT_USER_ID)

    async def index_patent(self, patent_id: int, content: str) -> int:
        """索引单个专利文本：分块 → 向量化 → 存储。返回分块数。

        Args:
            patent_id: patents 表中的 ID
            content: 专利全文文本（OCR 提取结果）
        """
        import time
        t0 = time.time()
        item_id = f"patent:{patent_id}"
        logger.info(f"专利索引开始 id={patent_id} len={len(content)}")

        # 分块
        raw_chunks = chunk_document(content, chunk_size=512, chunk_overlap=64)
        if not raw_chunks:
            self.vector_store.replace_by_external_id(PATENT_BASE_ID, item_id, [], [])
            return 0

        chunks = [c["text"] for c in raw_chunks if c.get("text")]
        if not chunks:
            return 0

        t1 = time.time()
        logger.info(f"  分块完成: {len(chunks)} 块 ({((t1-t0)*1000):.0f}ms)")

        # 向量化（批量嵌入）
        logger.info(f"  开始向量化: {len(chunks)} 段文本...")
        all_vectors = await self.embedder.embed(chunks)
        if not all_vectors or len(all_vectors) != len(chunks):
            logger.warning(f"  向量化失败或数量不匹配")
            return 0

        vectors = []
        metadata = []
        for i, vec in enumerate(all_vectors):
            if vec:
                vectors.append(vec)
                metadata.append({"chunk_idx": i, "text": chunks[i][:200], "patent_id": str(patent_id)})

        if not vectors:
            logger.warning(f"  向量化全部失败")
            return 0

        t2 = time.time()
        logger.info(f"  向量化完成: {len(vectors)} 个向量 ({((t2-t1)*1000):.0f}ms)")

        # 存储
        self.vector_store.replace_by_external_id(PATENT_BASE_ID, item_id, vectors, metadata)
        t3 = time.time()
        logger.info(f"  存储完成 ({((t3-t2)*1000):.0f}ms)")

        total = t3 - t0
        logger.info(f"专利 {patent_id} 索引完成: {len(vectors)} 分块, {total:.1f}s")
        return len(vectors)

    async def search(self, query: str, top_k: int = 10) -> list[dict]:
        """语义搜索相似专利"""
        vectors = await self.embedder.embed([query])
        if not vectors or not vectors[0]:
            logger.warning("查询向量化失败")
            return []

        query_vec = vectors[0]
        results = self.vector_store.search(
            base_id=PATENT_BASE_ID,
            query_vector=query_vec,
            top_k=top_k,
        )

        # 补充专利元数据
        enriched = []
        for r in results:
            patent_id_str = None
            for m in [r.get("metadata", {}), r]:
                if isinstance(m, dict):
                    pid = m.get("patent_id")
                    if pid:
                        patent_id_str = pid
                        break

            enriched.append({
                "itemId": r.get("item_id", ""),
                "text": r.get("text", "")[:300],
                "patentId": patent_id_str or "",
                "score": round(r.get("score", 0), 4),
                "chunkIndex": r.get("chunk_index", 0),
            })

        # 按分数降序
        enriched.sort(key=lambda x: x["score"], reverse=True)
        return enriched

    def delete_patent_index(self, patent_id: int):
        """删除专利的向量索引"""
        item_id = f"patent:{patent_id}"
        self.vector_store.delete_by_external_id(item_id)
        logger.info(f"专利 {patent_id} 向量索引已删除")
