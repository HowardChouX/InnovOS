"""
工作流处理器 — 处理叶子项的实际内容（解析、分块、嵌入、索引）

由 KnowledgeWorkflowService._process_leaf_item 调用。
"""
from __future__ import annotations
import hashlib
import json
import logging
from typing import Optional

from app.algorithm.knowledge.chunker import chunk_document
from app.algorithm.knowledge.embedder import Embedder
from app.algorithm.knowledge.vector_store import VectorStore

logger = logging.getLogger(__name__)


async def process_note(
    user_id: int,
    item_id: str,
    text: str,
    embedder_config: Optional[dict] = None,
) -> int:
    """处理笔记项：分块 → 嵌入 → 存储向量。

    Returns:
        索引的分块数
    """
    if not text or not text.strip():
        return 0

    # 用 item_id 的 hash 作为 doc_id（避免创建 knowledge_docs 条目）
    doc_id = _hash_item_id(item_id)

    chunks = chunk_document(text)
    if not chunks:
        return 0

    texts = [c["text"] for c in chunks]

    if embedder_config:
        embedder = Embedder(
            api_key=embedder_config.get("api_key", ""),
            api_host=embedder_config.get("api_host", ""),
            model=embedder_config.get("model", "BAAI/bge-large-zh-v1.5"),
        )
    else:
        embedder = Embedder()

    vectors = await embedder.embed(texts)

    store = VectorStore(user_id=user_id)
    metadata = [
        {"doc_id": doc_id, "chunk_idx": c["index"], "text": c["text"]}
        for c in chunks
    ]
    store.add(vectors, metadata)

    logger.info(f"笔记 {item_id} 索引完成: {len(chunks)} 个分块, doc_id={doc_id}")
    return len(chunks)


def _hash_item_id(item_id: str) -> int:
    """将 UUID 字符串映射为稳定的正整数用作 doc_id。

    使用 MD5 取前 8 字节转为 int，确保 ≤ 2^31-1。
    """
    h = hashlib.md5(item_id.encode()).digest()
    return int.from_bytes(h[:4], "big") & 0x7FFFFFFF
