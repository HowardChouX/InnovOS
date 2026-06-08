"""
知识库服务 — 参考 CherryStudio KnowledgeBaseService / KnowledgeItemService

提供 SQLite 支持的知识库和知识项数据持久化。
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from app.database import get_db
from app.utils import utc_iso
from app.models.knowledge import (
    KnowledgeBase,
    KnowledgeBaseStatus,
    KnowledgeBaseErrorCode,
    KnowledgeSearchMode,
    KnowledgeItem,
    KnowledgeItemType,
    KnowledgeItemStatus,
    KnowledgeItemDataUnion,
    FileItemData,
    UrlItemData,
    NoteItemData,
    DirectoryItemData,
)


class KnowledgeBaseService:
    """
    知识库服务 — 对齐 CherryStudio KnowledgeBaseService
    
    职责：
    - 持久化 SQLite 支持的知识库元数据
    - 持久化 knowledge_base.status 和 error
    - 持久化 knowledge_base.group_id 和 dimensions
    - 验证 item type / data 一致性
    """

    @staticmethod
    def list_bases(user_id: int, page: int = 1, limit: int = 20) -> dict:
        """列出用户的知识库"""
        db = get_db()
        offset = (page - 1) * limit

        # 查询知识库 + 关联 itemCount
        rows = db.execute(
            """
            SELECT
                kb.*,
                COUNT(ki.id) as item_count
            FROM knowledge_bases kb
            LEFT JOIN knowledge_items ki
                ON ki.base_id = kb.id AND ki.status != 'deleting'
            WHERE kb.user_id = ?
            GROUP BY kb.id
            ORDER BY kb.updated_at DESC, kb.id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ).fetchall()

        total = db.execute(
            "SELECT COUNT(*) FROM knowledge_bases WHERE user_id=?",
            (user_id,),
        ).fetchone()[0]
        db.close()

        items = [KnowledgeBaseService._row_to_base(r) for r in rows]
        for i, r in enumerate(rows):
            items[i]["itemCount"] = r["item_count"]

        return {"items": items, "total": total, "page": page}

    @staticmethod
    def get_by_id(user_id: int, base_id: str) -> Optional[dict]:
        """获取单个知识库"""
        db = get_db()
        row = db.execute(
            "SELECT * FROM knowledge_bases WHERE id=? AND user_id=?",
            (base_id, user_id),
        ).fetchone()
        db.close()
        if not row:
            return None
        return KnowledgeBaseService._row_to_base(row)

    @staticmethod
    def create_base(user_id: int, data: dict) -> dict:
        """创建知识库"""
        db = get_db()
        base_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        cursor = db.execute(
            """
            INSERT INTO knowledge_bases
            (id, user_id, name, group_id, dimensions, embedding_model_id, status, error,
             rerank_model_id, file_processor_id, chunk_size, chunk_overlap, threshold,
             document_count, search_mode, hybrid_alpha, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                base_id, user_id, data["name"].strip(), data.get("group_id") or None,
                data.get("dimensions"), data.get("embedding_model_id"), data.get("status", "completed"),
                data.get("error"), data.get("rerank_model_id"), data.get("file_processor_id"),
                data.get("chunk_size", 1024), data.get("chunk_overlap", 200),
                data.get("threshold"), data.get("document_count"),
                data.get("search_mode", "hybrid"), data.get("hybrid_alpha"), now, now,
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM knowledge_bases WHERE id=?", (base_id,)).fetchone()
        db.close()
        return KnowledgeBaseService._row_to_base(row)

    @staticmethod
    def update_base(user_id: int, base_id: str, data: dict) -> Optional[dict]:
        """更新知识库"""
        db = get_db()
        row = db.execute(
            "SELECT * FROM knowledge_bases WHERE id=? AND user_id=?",
            (base_id, user_id),
        ).fetchone()
        if not row:
            db.close()
            return None

        updates = []
        params = []
        field_map = {
            "name": "name", "group_id": "group_id",
            "rerank_model_id": "rerank_model_id", "file_processor_id": "file_processor_id",
            "chunk_size": "chunk_size", "chunk_overlap": "chunk_overlap",
            "threshold": "threshold", "document_count": "document_count",
            "search_mode": "search_mode", "hybrid_alpha": "hybrid_alpha",
            "status": "status", "error": "error",
            "dimensions": "dimensions", "embedding_model_id": "embedding_model_id",
        }
        for py_field, db_field in field_map.items():
            val = data.get(py_field)
            if val is not None:
                updates.append(f"{db_field}=?")
                params.append(val)

        if updates:
            updates.append("updated_at=datetime('now')")
            params.append(base_id)
            params.append(user_id)
            db.execute(
                f"UPDATE knowledge_bases SET {', '.join(updates)} WHERE id=? AND user_id=?",
                params,
            )
            db.commit()

        row = db.execute("SELECT * FROM knowledge_bases WHERE id=?", (base_id,)).fetchone()
        db.close()
        return KnowledgeBaseService._row_to_base(row)

    @staticmethod
    def delete_base(user_id: int, base_id: str) -> bool:
        """删除知识库"""
        db = get_db()
        row = db.execute(
            "SELECT id FROM knowledge_bases WHERE id=? AND user_id=?",
            (base_id, user_id),
        ).fetchone()
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


class KnowledgeItemService:
    """
    知识项服务 — 对齐 CherryStudio KnowledgeItemService
    
    职责：
    - 持久化 knowledge_item.status 和 error
    - 协调容器项状态从子项状态
    - 验证 item type / data 一致性
    """

    @staticmethod
    def list_items(
        user_id: int,
        base_id: str,
        page: int = 1,
        limit: int = 20,
        item_type: str = "",
        group_id: str = "",
    ) -> Optional[dict]:
        """列出知识库中的知识项"""
        db = get_db()
        # 验证 base 存在且属于该用户
        base = db.execute(
            "SELECT id FROM knowledge_bases WHERE id=? AND user_id=?",
            (base_id, user_id),
        ).fetchone()
        if not base:
            db.close()
            return None

        offset = (page - 1) * limit
        params = [base_id]
        where = "base_id = ? AND status != 'deleting'"
        if item_type:
            where += " AND type = ?"
            params.append(item_type)
        if group_id:
            if group_id == "null":
                where += " AND group_id IS NULL"
            else:
                where += " AND group_id = ?"
                params.append(group_id)

        total = db.execute(
            f"SELECT COUNT(*) FROM knowledge_items WHERE {where}",
            params,
        ).fetchone()[0]

        rows = db.execute(
            f"SELECT * FROM knowledge_items WHERE {where} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        db.close()

        return {
            "items": [KnowledgeItemService._row_to_item(r) for r in rows],
            "total": total,
            "page": page,
        }

    @staticmethod
    def get_by_id(user_id: int, item_id: str) -> Optional[dict]:
        """获取单个知识项"""
        db = get_db()
        row = db.execute(
            """
            SELECT ki.* FROM knowledge_items ki
            JOIN knowledge_bases kb ON kb.id = ki.base_id
            WHERE ki.id=? AND kb.user_id=?
            """,
            (item_id, user_id),
        ).fetchone()
        db.close()
        if not row:
            return None
        return KnowledgeItemService._row_to_item(row)

    @staticmethod
    def create_item(user_id: int, base_id: str, data: dict) -> Optional[dict]:
        """创建知识项"""
        db = get_db()
        base = db.execute(
            "SELECT id FROM knowledge_bases WHERE id=? AND user_id=?",
            (base_id, user_id),
        ).fetchone()
        if not base:
            db.close()
            return None

        item_id = str(uuid.uuid4())
        data_json = json.dumps(data.get("data", {}))
        now = datetime.now(timezone.utc).isoformat()

        cursor = db.execute(
            """
            INSERT INTO knowledge_items
            (id, base_id, group_id, type, data, status, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id, base_id, data.get("group_id") or None, data["type"],
                data_json, data.get("status", "idle"), data.get("error"), now, now,
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM knowledge_items WHERE id=?", (item_id,)).fetchone()
        db.close()
        return KnowledgeItemService._row_to_item(row)

    @staticmethod
    def update_status(user_id: int, item_id: str, status: str, error: str = "") -> Optional[dict]:
        """更新知识项状态"""
        db = get_db()
        row = db.execute(
            """
            SELECT ki.* FROM knowledge_items ki
            JOIN knowledge_bases kb ON kb.id = ki.base_id
            WHERE ki.id=? AND kb.user_id=?
            """,
            (item_id, user_id),
        ).fetchone()
        if not row:
            db.close()
            return None

        err = error.strip() if status == "failed" else None
        db.execute(
            "UPDATE knowledge_items SET status=?, error=?, updated_at=datetime('now') WHERE id=?",
            (status, err, item_id),
        )
        db.commit()
        row = db.execute("SELECT * FROM knowledge_items WHERE id=?", (item_id,)).fetchone()
        db.close()
        return KnowledgeItemService._row_to_item(row)

    @staticmethod
    def delete_item(user_id: int, item_id: str) -> bool:
        """删除知识项"""
        db = get_db()
        row = db.execute(
            """
            SELECT ki.id, ki.base_id FROM knowledge_items ki
            JOIN knowledge_bases kb ON kb.id = ki.base_id
            WHERE ki.id=? AND kb.user_id=?
            """,
            (item_id, user_id),
        ).fetchone()
        if not row:
            db.close()
            return False
        db.execute("DELETE FROM knowledge_items WHERE id=?", (item_id,))
        db.commit()
        db.close()
        return True

    @staticmethod
    def delete_items_by_base(user_id: int, base_id: str, item_ids: list[str]) -> bool:
        """批量删除知识项"""
        db = get_db()
        base = db.execute(
            "SELECT id FROM knowledge_bases WHERE id=? AND user_id=?",
            (base_id, user_id),
        ).fetchone()
        if not base:
            db.close()
            return False
        placeholders = ",".join("?" for _ in item_ids)
        db.execute(
            f"DELETE FROM knowledge_items WHERE base_id=? AND id IN ({placeholders})",
            [base_id, *item_ids],
        )
        db.commit()
        db.close()
        return True

    @staticmethod
    def _row_to_item(r) -> dict:
        """数据库行转字典"""
        data = r["data"]
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                data = {}
        return {
            "id": r["id"],
            "baseId": r["base_id"],
            "groupId": r["group_id"],
            "type": r["type"],
            "data": data if isinstance(data, dict) else {},
            "status": r["status"],
            "error": r["error"],
            "createdAt": utc_iso(r["created_at"]),
            "updatedAt": utc_iso(r["updated_at"]),
        }
