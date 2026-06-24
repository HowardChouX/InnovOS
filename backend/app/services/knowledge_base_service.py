"""
Knowledge Base Service — 完全复现 CherryStudio KnowledgeBaseService

职责：
- 持久化知识库元数据（PostgreSQL）
- 持久化 knowledge_base.status 和 error
- 持久化 knowledge_base.group_id 和 dimensions
- 验证配置 (chunkOverlap < chunkSize, hybridAlpha + hybrid search)
"""

import logging
import os
import shutil
import uuid
from datetime import datetime, timezone

from app.database import get_db
from app.utils import utc_iso

logger = logging.getLogger(__name__)

ALLOWED_KB_FIELDS = {
    "name",
    "group_id",
    "rerank_model_id",
    "file_processor_id",
    "threshold",
    "document_count",
    "status",
    "error",
    "dimensions",
    "embedding_model_id",
    "chunk_size",
    "chunk_overlap",
    "search_mode",
    "hybrid_alpha",
    "updated_at",
}

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


def _validate_model_id(val: str | None, key: str) -> None:
    """校验模型 ID 格式 — 禁止双冒号。"""
    if val and "::" in val:
        raise ValueError(
            f"Validation errors: {{'{key}': ['Model ID must use single colon (e.g. provider:model), got {val!r}']}}"
        )


def _get_base_upload_dir(user_id: int, base_id: str) -> str | None:
    """获取知识库文件上传目录路径"""
    uploads_root = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "uploads",
        str(user_id),
        base_id,
    )
    return uploads_root if os.path.exists(uploads_root) else None


def _cleanup_base_files(user_id: int, base_id: str) -> None:
    """清理知识库关联的上传文件"""
    from app.services.file_storage_service import file_storage

    # S3 cleanup
    if file_storage.enabled:
        try:
            prefix = f"knowledge/{user_id}/"
            deleted = file_storage.delete_by_prefix(prefix)
            logger.info(f"Cleaned up S3 files for base {base_id}: {deleted}")
        except Exception as e:
            logger.warning(f"S3 cleanup failed for base {base_id}: {e}")

    # Local filesystem cleanup
    upload_dir = _get_base_upload_dir(user_id, base_id)
    if upload_dir and os.path.exists(upload_dir):
        try:
            shutil.rmtree(upload_dir)
            logger.info(f"Cleaned up local files for base {base_id}")
        except Exception as e:
            logger.warning(f"Local cleanup failed for base {base_id}: {e}")


class KnowledgeBaseService:
    """知识库服务 — 完全对齐 CherryStudio KnowledgeBaseService"""

    @staticmethod
    def list(user_id: int, page: int = 1, limit: int = 20) -> dict:
        """分页列出知识库"""
        db = get_db()
        offset = (page - 1) * limit

        rows = db.execute(
            """
            SELECT kb.*, COUNT(ki.id) AS item_count
            FROM knowledge_bases kb
            LEFT JOIN knowledge_items ki ON ki.base_id = kb.id AND ki.status != 'deleting'
            WHERE kb.user_id=?
            GROUP BY kb.id
            ORDER BY kb.created_at DESC, kb.id DESC
            LIMIT ? OFFSET ?
        """,
            (user_id, limit, offset),
        ).fetchall()

        total = db.execute("SELECT COUNT(*) FROM knowledge_bases WHERE user_id=?", (user_id,)).fetchone()[0]
        db.close()

        items = [KnowledgeBaseService._row_to_base(r) for r in rows]
        for i, r in enumerate(rows):
            items[i]["itemCount"] = r["item_count"]

        return {"items": items, "total": total, "page": page}

    @staticmethod
    def get_by_id(user_id: int, base_id: str) -> dict | None:
        """获取单个知识库"""
        db = get_db()
        row = db.execute("SELECT * FROM knowledge_bases WHERE id=? AND user_id=?", (base_id, user_id)).fetchone()
        db.close()
        if not row:
            return None
        return KnowledgeBaseService._row_to_base(row)

    @staticmethod
    def create(user_id: int, dto: dict) -> dict:
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
        _validate_model_id(dto.get("embeddingModelId"), "embeddingModelId")
        _validate_model_id(dto.get("rerankModelId"), "rerankModelId")

        db = get_db()
        base_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        db.execute(
            """
            INSERT INTO knowledge_bases
            (id, user_id, name, group_id, dimensions, embedding_model_id, status, error,
             rerank_model_id, file_processor_id, chunk_size, chunk_overlap, threshold,
             document_count, search_mode, hybrid_alpha, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                base_id,
                user_id,
                dto["name"].strip(),
                dto.get("groupId"),
                dto.get("dimensions"),
                dto.get("embeddingModelId"),
                dto.get("status", "completed"),
                dto.get("error"),
                dto.get("rerankModelId"),
                dto.get("fileProcessorId"),
                create_config["chunkSize"],
                create_config["chunkOverlap"],
                dto.get("threshold"),
                dto.get("documentCount"),
                create_config["searchMode"],
                create_config["hybridAlpha"],
                now,
                now,
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM knowledge_bases WHERE id=?", (base_id,)).fetchone()
        db.close()
        return KnowledgeBaseService._row_to_base(row)

    @staticmethod
    def update(user_id: int, base_id: str, dto: dict) -> dict | None:
        """更新知识库"""
        existing = KnowledgeBaseService.get_by_id(user_id, base_id)
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
        _validate_model_id(dto.get("embeddingModelId"), "embeddingModelId")
        _validate_model_id(dto.get("rerankModelId"), "rerankModelId")

        updates = {}
        field_map = {
            "name": "name",
            "groupId": "group_id",
            "rerankModelId": "rerank_model_id",
            "fileProcessorId": "file_processor_id",
            "threshold": "threshold",
            "documentCount": "document_count",
            "status": "status",
            "error": "error",
            "dimensions": "dimensions",
            "embeddingModelId": "embedding_model_id",
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
        cols = [s.split("=")[0].strip() for s in set_clause.split(", ")]
        for c in cols:
            if c not in ALLOWED_KB_FIELDS:
                raise ValueError(f"Invalid knowledge_bases column: {c}")
        db.execute(
            f"UPDATE knowledge_bases SET {set_clause} WHERE id=? AND user_id=?",
            [*updates.values(), base_id, user_id],
        )
        db.commit()
        row = db.execute("SELECT * FROM knowledge_bases WHERE id=? AND user_id=?", (base_id, user_id)).fetchone()
        db.close()
        return KnowledgeBaseService._row_to_base(row)

    @staticmethod
    def delete(user_id: int, base_id: str) -> bool:
        """删除知识库（清理数据库记录 + 上传文件）"""
        db = get_db()
        try:
            row = db.execute("SELECT id FROM knowledge_bases WHERE id=? AND user_id=?", (base_id, user_id)).fetchone()
            if not row:
                return False

            # Clean up uploaded files from storage
            _cleanup_base_files(user_id, base_id)

            db.execute("DELETE FROM knowledge_vectors WHERE base_id=?", (base_id,))
            db.execute("DELETE FROM knowledge_items WHERE base_id=?", (base_id,))
            db.execute("DELETE FROM knowledge_bases WHERE id=? AND user_id=?", (base_id, user_id))
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def restore(user_id: int, source_base_id: str, new_base_id: str, dto: dict) -> dict:
        """从失败的知识库恢复：读取源配置，创建新知识库记录"""
        db = get_db()
        source = db.execute(
            "SELECT * FROM knowledge_bases WHERE id=? AND user_id=?", (source_base_id, user_id)
        ).fetchone()
        if not source:
            db.close()
            raise ValueError("源知识库不存在")

        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """
            INSERT INTO knowledge_bases
            (id, user_id, name, group_id, dimensions, embedding_model_id, status, error,
             rerank_model_id, file_processor_id, chunk_size, chunk_overlap, threshold,
             document_count, search_mode, hybrid_alpha, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                new_base_id,
                user_id,
                dto["name"].strip(),
                source["group_id"],
                dto.get("dimensions", source["dimensions"]),
                dto.get("embeddingModelId", source["embedding_model_id"]),
                "completed",
                None,
                source["rerank_model_id"],
                source["file_processor_id"],
                source["chunk_size"],
                source["chunk_overlap"],
                source["threshold"],
                source["document_count"],
                source["search_mode"],
                source["hybrid_alpha"],
                now,
                now,
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM knowledge_bases WHERE id=?", (new_base_id,)).fetchone()
        db.close()
        return KnowledgeBaseService._row_to_base(row)

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
