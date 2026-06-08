"""
Knowledge Base Service — 完全复现 CherryStudio KnowledgeBaseService

职责：
- 持久化 SQLite 支持的知识库元数据
- 持久化 knowledge_base.status 和 error
- 持久化 knowledge_base.group_id 和 dimensions
- 验证配置 (chunkOverlap < chunkSize, hybridAlpha + hybrid search)
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from app.database import get_db
from app.utils import utc_iso

DEFAULT_CHUNK_SIZE = 1024
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_SEARCH_MODE = "hybrid"


def _validate_config(config: dict) -> dict:
    """验证知识库配置，返回字段错误"""
    field_errors = {}
    if config.get("chunkOverlap", 0) >= config.get("chunkSize", DEFAULT_CHUNK_SIZE):
        field_errors["chunkOverlap"] = ["Chunk overlap must be smaller than chunk size"]
    if config.get("hybridAlpha") is not None and config.get("searchMode") != "hybrid":
        field_errors["hybridAlpha"] = ["Hybrid alpha requires hybrid search mode"]
    return field_errors


class KnowledgeBaseService:
    """知识库服务 — 完全对齐 CherryStudio KnowledgeBaseService"""

    @staticmethod
    def list(page: int = 1, limit: int = 20) -> dict:
        """分页列出知识库"""
        db = get_db()
        offset = (page - 1) * limit

        rows = db.execute("""
            SELECT kb.*, COUNT(ki.id) AS item_count
            FROM knowledge_bases kb
            LEFT JOIN knowledge_items ki ON ki.base_id = kb.id AND ki.status != 'deleting'
            GROUP BY kb.id
            ORDER BY kb.created_at DESC, kb.id DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()

        total = db.execute("SELECT COUNT(*) FROM knowledge_bases").fetchone()[0]
        db.close()

        items = [KnowledgeBaseService._row_to_base(r) for r in rows]
        for i, r in enumerate(rows):
            items[i]["itemCount"] = r["item_count"]

        return {"items": items, "total": total, "page": page}

    @staticmethod
    def get_by_id(base_id: str) -> Optional[dict]:
        """获取单个知识库"""
        db = get_db()
        row = db.execute("SELECT * FROM knowledge_bases WHERE id=?", (base_id,)).fetchone()
        db.close()
        if not row:
            return None
        return KnowledgeBaseService._row_to_base(row)

    @staticmethod
    def create(dto: dict) -> dict:
        """创建知识库"""
        create_config = {
            "chunkSize": dto.get("chunkSize", DEFAULT_CHUNK_SIZE),
            "chunkOverlap": dto.get("chunkOverlap", DEFAULT_CHUNK_OVERLAP),
            "searchMode": dto.get("searchMode", DEFAULT_SEARCH_MODE),
            "hybridAlpha": dto.get("hybridAlpha"),
        }
        field_errors = _validate_config(create_config)
        if field_errors:
            raise ValueError(f"Validation errors: {field_errors}")

        db = get_db()
        base_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        db.execute("""
            INSERT INTO knowledge_bases
            (id, name, group_id, dimensions, embedding_model_id, status, error,
             rerank_model_id, file_processor_id, chunk_size, chunk_overlap, threshold,
             document_count, search_mode, hybrid_alpha, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            base_id, dto["name"].strip(), dto.get("groupId"),
            dto.get("dimensions"), dto.get("embeddingModelId"),
            dto.get("status", "completed"), dto.get("error"),
            dto.get("rerankModelId"), dto.get("fileProcessorId"),
            create_config["chunkSize"], create_config["chunkOverlap"],
            dto.get("threshold"), dto.get("documentCount"),
            create_config["searchMode"], create_config["hybridAlpha"],
            now, now,
        ))
        db.commit()
        row = db.execute("SELECT * FROM knowledge_bases WHERE id=?", (base_id,)).fetchone()
        db.close()
        return KnowledgeBaseService._row_to_base(row)

    @staticmethod
    def update(base_id: str, dto: dict) -> Optional[dict]:
        """更新知识库"""
        existing = KnowledgeBaseService.get_by_id(base_id)
        if not existing:
            return None

        next_config = {
            "chunkSize": dto.get("chunkSize", existing["chunkSize"]),
            "chunkOverlap": dto.get("chunkOverlap", existing["chunkOverlap"]),
            "searchMode": dto.get("searchMode", existing["searchMode"]),
            "hybridAlpha": dto.get("hybridAlpha", existing["hybridAlpha"]),
        }

        if dto.get("searchMode") is not None and dto["searchMode"] != "hybrid" and "hybridAlpha" not in dto:
            next_config["hybridAlpha"] = None

        field_errors = _validate_config(next_config)
        if field_errors:
            raise ValueError(f"Validation errors: {field_errors}")

        updates = {}
        field_map = {
            "name": "name", "groupId": "group_id", "rerankModelId": "rerank_model_id",
            "fileProcessorId": "file_processor_id", "threshold": "threshold",
            "documentCount": "document_count", "status": "status", "error": "error",
            "dimensions": "dimensions", "embeddingModelId": "embedding_model_id",
        }
        for py_field, db_field in field_map.items():
            if py_field in dto:
                updates[db_field] = dto[py_field]

        # 配置字段
        if next_config["chunkSize"] != existing["chunkSize"]:
            updates["chunk_size"] = next_config["chunkSize"]
        if next_config["chunkOverlap"] != existing["chunkOverlap"]:
            updates["chunk_overlap"] = next_config["chunkOverlap"]
        if next_config["searchMode"] != existing["searchMode"]:
            updates["search_mode"] = next_config["searchMode"]
        if next_config["hybridAlpha"] != existing["hybridAlpha"]:
            updates["hybrid_alpha"] = next_config["hybridAlpha"]

        if not updates:
            return existing

        db = get_db()
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        db.execute(
            f"UPDATE knowledge_bases SET {set_clause} WHERE id=?",
            [*updates.values(), base_id],
        )
        db.commit()
        row = db.execute("SELECT * FROM knowledge_bases WHERE id=?", (base_id,)).fetchone()
        db.close()
        return KnowledgeBaseService._row_to_base(row)

    @staticmethod
    def delete(base_id: str) -> bool:
        """删除知识库"""
        db = get_db()
        row = db.execute("SELECT id FROM knowledge_bases WHERE id=?", (base_id,)).fetchone()
        if not row:
            db.close()
            return False

        db.execute("DELETE FROM knowledge_items WHERE base_id=?", (base_id,))
        db.execute("DELETE FROM knowledge_bases WHERE id=?", (base_id,))
        db.commit()
        db.close()
        return True

    @staticmethod
    def _row_to_base(r) -> dict:
        """数据库行转字典"""
        return {
            "id": r["id"],
            "name": r["name"],
            "groupId": r["group_id"],
            "dimensions": r["dimensions"],
            "embeddingModelId": r["embedding_model_id"],
            "status": r["status"],
            "error": r["error"],
            "rerankModelId": r["rerank_model_id"],
            "fileProcessorId": r["file_processor_id"],
            "chunkSize": r["chunk_size"],
            "chunkOverlap": r["chunk_overlap"],
            "threshold": r["threshold"],
            "documentCount": r["document_count"],
            "searchMode": r["search_mode"],
            "hybridAlpha": r["hybrid_alpha"],
            "createdAt": utc_iso(r["created_at"]),
            "updatedAt": utc_iso(r["updated_at"]),
        }
