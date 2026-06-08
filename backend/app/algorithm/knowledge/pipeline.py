"""
知识库文件导入管线 — 借鉴 CherryStudio KnowledgeOrchestrationService

流程：上传 → 解析 → 分块 → 嵌入 → 存储向量
"""
import json
import logging
from typing import Any
from app.database import get_db
from app.algorithm.knowledge.chunker import chunk_document
from app.algorithm.file_parser import parse_file

logger = logging.getLogger(__name__)


class KnowledgePipeline:
    """文件导入管线，处理单个文件的完整导入流程。"""

    def __init__(self, user_id: int, base_id: str = "default"):
        self.user_id = user_id
        self.base_id = base_id

    async def process_file(self, file_path: str, file_name: str) -> dict:
        """处理单个文件：解析 → 存储 → 分块 → 嵌入 → 索引。"""
        parsed = parse_file(file_path)
        doc_id = await self._save_document(parsed["title"] or file_name, parsed["content"], parsed["type"], file_name)
        return {"doc_id": doc_id, "title": parsed["title"] or file_name, "type": parsed["type"]}

    async def process_text(self, title: str, content: str, doc_type: str = "text") -> dict:
        """处理文本粘贴。"""
        doc_id = await self._save_document(title, content, doc_type, "")
        return {"doc_id": doc_id, "title": title, "type": doc_type}

    async def _save_document(self, title: str, content: str, doc_type: str, source: str) -> int:
        db = get_db()
        base_id_val = int(self.base_id) if self.base_id and str(self.base_id).isdigit() else 0
        cursor = db.execute(
            """INSERT INTO knowledge_docs (title, content, category, tags, source, doc_type, user_id, base_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title[:200], content, "知识库", json.dumps([]), source, doc_type, self.user_id, base_id_val),
        )
        db.commit()
        doc_id = cursor.lastrowid
        db.close()

        # 异步索引到向量存储
        try:
            from app.algorithm.knowledge.retriever import get_retriever
            retriever = get_retriever(self.user_id)
            await retriever.index_document(doc_id, content)
        except Exception as e:
            logger.warning(f"向量索引失败: {e}")

        return doc_id

    async def search(self, query: str, top_k: int = 10) -> list[dict]:
        """RAG 检索。"""
        try:
            from app.algorithm.knowledge.retriever import get_retriever
            retriever = get_retriever(self.user_id)
            results = await retriever.search(query, top_k)
            return results
        except Exception as e:
            logger.warning(f"检索失败: {e}")
            return []


# 获取指定供应商的嵌入模型 API 配置
def get_embedding_api_config(provider_id: str = "") -> dict:
    """从已配置的模型服务中获取嵌入模型 API 配置。
    
    返回格式：
    { "api_key": "sk-xxx", "api_host": "https://api.siliconflow.cn", "model": "BAAI/bge-large-zh-v1.5" }
    """
    from app.database import get_db
    from app.algorithm.crypto import decrypt_key

    db = get_db()
    if provider_id:
        row = db.execute(
            "SELECT api_host, api_key_encrypted, api_model, models FROM model_providers WHERE provider_id=? AND is_enabled=1",
            (provider_id,),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT api_host, api_key_encrypted, api_model, models FROM model_providers WHERE is_enabled=1 AND api_key_encrypted IS NOT NULL LIMIT 1",
        ).fetchone()
    db.close()

    if not row:
        return {}

    api_host = row["api_host"]
    api_key = decrypt_key(row["api_key_encrypted"]) if row["api_key_encrypted"] else ""

    # 从 models 中找嵌入模型
    models = json.loads(row["models"]) if row["models"] else []
    embed_keywords = ["embedding", "embed", "bge", "e5-", "text-embedding"]
    embed_model = ""
    for m in models:
        ml = m.lower()
        if any(k in ml for k in embed_keywords):
            embed_model = m
            break
    if not embed_model:
        embed_model = row["api_model"] or "BAAI/bge-large-zh-v1.5"

    return {"api_key": api_key, "api_host": api_host, "model": embed_model}
