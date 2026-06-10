"""
Knowledge Item Service — 完全复现 CherryStudio KnowledgeItemService

职责：
- 持久化 knowledge_item.status 和 error
- 协调容器项状态从子项状态
- 验证 item type / data 一致性
- 子树操作 (递归 CTE)
- 容器状态协调
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from app.database import get_db
from app.utils import utc_iso

CONTAINER_CHILD_FAILURE_ERROR = "One or more child items failed"


class KnowledgeItemService:
    """知识项服务 — 完全对齐 CherryStudio KnowledgeItemService"""

    @staticmethod
    def list(user_id: int, base_id: str, page: int = 1, limit: int = 20, type: str = None, groupId: str = None) -> dict:
        """分页列出知识项"""
        db = get_db()
        # Verify the base belongs to user
        base = db.execute(
            "SELECT id FROM knowledge_bases WHERE id=? AND user_id=?", (base_id, user_id)
        ).fetchone()
        if not base:
            raise ValueError("知识库不存在")

        offset = (page - 1) * limit
        conditions = ["base_id = ?", "status != 'deleting'"]
        params = [base_id]

        if type is not None:
            conditions.append("type = ?")
            params.append(type)
        if groupId is not None:
            if groupId == "null":
                conditions.append("group_id IS NULL")
            else:
                conditions.append("group_id = ?")
                params.append(groupId)

        where = " AND ".join(conditions)
        total = db.execute(f"SELECT COUNT(*) FROM knowledge_items WHERE {where}", params).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM knowledge_items WHERE {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        db.close()
        return {"items": [KnowledgeItemService._row_to_item(r) for r in rows], "total": total, "page": page}

    @staticmethod
    def get_by_id(user_id: int, item_id: str) -> Optional[dict]:
        """获取单个知识项"""
        db = get_db()
        row = db.execute(
            """SELECT ki.* FROM knowledge_items ki
               JOIN knowledge_bases kb ON kb.id = ki.base_id
               WHERE ki.id=? AND kb.user_id=?""",
            (item_id, user_id),
        ).fetchone()
        db.close()
        if not row:
            return None
        return KnowledgeItemService._row_to_item(row)

    @staticmethod
    def get_items_by_base_id(user_id: int, base_id: str, groupId: str = None) -> list[dict]:
        """获取知识库下的所有知识项（非分页）"""
        db = get_db()
        # Verify the base belongs to user
        base = db.execute(
            "SELECT id FROM knowledge_bases WHERE id=? AND user_id=?", (base_id, user_id)
        ).fetchone()
        if not base:
            raise ValueError("知识库不存在")

        conditions = ["base_id = ?", "status != 'deleting'"]
        params = [base_id]
        if groupId is not None:
            if groupId == "null":
                conditions.append("group_id IS NULL")
            else:
                conditions.append("group_id = ?")
                params.append(groupId)
        where = " AND ".join(conditions)
        rows = db.execute(f"SELECT * FROM knowledge_items WHERE {where} ORDER BY created_at, id", params).fetchall()
        db.close()
        return [KnowledgeItemService._row_to_item(r) for r in rows]

    @staticmethod
    def get_root_items_by_base_id(user_id: int, base_id: str) -> list[dict]:
        """获取知识库的根项"""
        return KnowledgeItemService.get_items_by_base_id(user_id, base_id, groupId="null")

    @staticmethod
    def get_outermostSelectedItem_ids(user_id: int, base_id: str, item_ids: list[str]) -> list[str]:
        """获取最外层选中的项 ID（排除子项）"""
        selected_ids = list(dict.fromkeys(item_ids))
        selected_id_set = set(selected_ids)

        descendants_selected = set()
        for item_id in selected_ids:
            descendants = KnowledgeItemService.get_subtree_items(user_id, base_id, [item_id])
            for desc in descendants:
                if desc["id"] in selected_id_set:
                    descendants_selected.add(desc["id"])

        return [iid for iid in selected_ids if iid not in descendants_selected]

    @staticmethod
    def get_deleting_root_groups(user_id: int) -> list[dict]:
        """获取正在删除的根组（用于崩溃恢复）"""
        db = get_db()
        rows = db.execute("""
            SELECT child.base_id AS baseId, child.id AS id
            FROM knowledge_items child
            LEFT JOIN knowledge_items parent
                ON parent.base_id = child.base_id AND parent.id = child.group_id
            JOIN knowledge_bases kb ON kb.id = child.base_id
            WHERE child.status = 'deleting'
                AND kb.user_id = ?
                AND (child.group_id IS NULL OR parent.id IS NULL OR parent.status != 'deleting')
            ORDER BY child.base_id, child.id
        """, (user_id,)).fetchall()
        db.close()

        root_ids_by_base = {}
        for row in rows:
            base_id = row["baseId"]
            if base_id not in root_ids_by_base:
                root_ids_by_base[base_id] = []
            root_ids_by_base[base_id].append(row["id"])

        return [{"baseId": bid, "rootItemIds": rids} for bid, rids in root_ids_by_base.items()]

    @staticmethod
    def create(user_id: int, base_id: str, item: dict) -> Optional[dict]:
        """创建知识项"""
        db = get_db()
        # Verify base ownership
        base = db.execute(
            "SELECT id FROM knowledge_bases WHERE id=? AND user_id=?", (base_id, user_id)
        ).fetchone()
        if not base:
            raise ValueError("知识库不存在或无权访问")

        item_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        data_json = json.dumps(item.get("data", {}))
        cursor = db.execute(
            """INSERT INTO knowledge_items
               (id, base_id, group_id, type, data, status, error, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, base_id, item.get("groupId") or None, item["type"],
             data_json, item.get("status", "idle"), item.get("error"), now, now),
        )
        db.commit()
        row = db.execute("SELECT * FROM knowledge_items WHERE id=?", (item_id,)).fetchone()
        db.close()
        if not row:
            return None
        return KnowledgeItemService._row_to_item(row)

    @staticmethod
    def set_subtree_status(user_id: int, base_id: str, root_ids: list[str], status: str, error: str = None) -> list[str]:
        """递归设置子树状态（使用递归 CTE）"""
        unique_root_ids = list(dict.fromkeys(root_ids))
        if not unique_root_ids:
            return []

        db = get_db()
        # Verify the base belongs to user
        base = db.execute(
            "SELECT id FROM knowledge_bases WHERE id=? AND user_id=?", (base_id, user_id)
        ).fetchone()
        if not base:
            raise ValueError("知识库不存在")

        placeholders = ",".join("?" for _ in unique_root_ids)

        now = datetime.now(timezone.utc).isoformat()

        # 递归 CTE 查找子树
        rows = db.execute(f"""
            WITH RECURSIVE subtree AS (
                SELECT id FROM knowledge_items
                WHERE base_id = ? AND id IN ({placeholders})
                UNION ALL
                SELECT child.id FROM knowledge_items child
                INNER JOIN subtree parent ON child.group_id = parent.id
                WHERE child.base_id = ?
            )
            UPDATE knowledge_items
            SET status = ?, error = ?, updated_at = ?
            WHERE base_id = ? AND id IN (SELECT DISTINCT id FROM subtree)
                {'AND status != ?' if status == 'failed' else ''}
            RETURNING id, group_id AS groupId
        """, [base_id, *unique_root_ids, base_id, status, error or None, now, base_id] +
              (["deleting"] if status == "failed" else [])).fetchall()
        db.commit()

        updated_ids = [r["id"] for r in rows]
        updated_id_set = set(updated_ids)

        if status == "failed":
            parent_ids = [r["groupId"] for r in rows if r["groupId"] and r["groupId"] not in updated_id_set]
            KnowledgeItemService._reconcile_containers(user_id, base_id, parent_ids)

        db.close()
        return updated_ids

    @staticmethod
    def delete_items_by_ids(user_id: int, base_id: str, item_ids: list[str]) -> None:
        """批量删除知识项"""
        unique_ids = list(dict.fromkeys(item_ids))
        if not unique_ids:
            return

        db = get_db()
        # Verify the base belongs to user
        base = db.execute(
            "SELECT id FROM knowledge_bases WHERE id=? AND user_id=?", (base_id, user_id)
        ).fetchone()
        if not base:
            raise ValueError("知识库不存在")

        placeholders = ",".join("?" for _ in unique_ids)

        # 获取父 ID 用于协调
        target_rows = db.execute(
            f"SELECT group_id FROM knowledge_items WHERE base_id = ? AND id IN ({placeholders})",
            [base_id, *unique_ids],
        ).fetchall()
        group_ids = [r["group_id"] for r in target_rows]

        # 删除
        db.execute(
            f"DELETE FROM knowledge_items WHERE base_id = ? AND id IN ({placeholders})",
            [base_id, *unique_ids],
        )
        db.commit()
        db.close()

        # 协调容器状态
        KnowledgeItemService._reconcile_containers(user_id, base_id, group_ids)

    @staticmethod
    def get_subtree_items(user_id: int, base_id: str, root_ids: list[str], include_roots: bool = False, leaf_only: bool = False) -> list[dict]:
        """获取子树项（递归 CTE）"""
        unique_ids = list(dict.fromkeys(root_ids))
        if not unique_ids:
            return []

        db = get_db()
        # Verify the base belongs to user
        base = db.execute(
            "SELECT id FROM knowledge_bases WHERE id=? AND user_id=?", (base_id, user_id)
        ).fetchone()
        if not base:
            raise ValueError("知识库不存在")

        placeholders = ",".join("?" for _ in unique_ids)
        leaf_filter = "AND item.type IN ('file', 'url', 'note')" if leaf_only else ""
        root_filter = "" if include_roots else f"AND item.id NOT IN ({placeholders})"

        rows = db.execute(f"""
            WITH RECURSIVE subtree AS (
                SELECT id, type FROM knowledge_items
                WHERE base_id = ? AND id IN ({placeholders})
                UNION ALL
                SELECT child.id, child.type FROM knowledge_items child
                INNER JOIN subtree parent ON child.group_id = parent.id
                WHERE child.base_id = ?
            )
            SELECT DISTINCT item.*
            FROM subtree
            INNER JOIN knowledge_items item ON item.id = subtree.id AND item.base_id = ?
            WHERE 1=1 {root_filter} {leaf_filter}
        """, [base_id, *unique_ids, base_id, base_id] +
              (unique_ids if not include_roots else [])).fetchall()
        db.close()
        return [KnowledgeItemService._row_to_item(r) for r in rows]

    @staticmethod
    def update_status(user_id: int, item_id: str, status: str, error: str = None) -> Optional[dict]:
        """更新知识项状态"""
        db = get_db()
        existing = db.execute(
            """SELECT ki.* FROM knowledge_items ki
               JOIN knowledge_bases kb ON kb.id = ki.base_id
               WHERE ki.id=? AND kb.user_id=?""",
            (item_id, user_id),
        ).fetchone()
        if not existing:
            db.close()
            return None

        # deleting 状态不可逆
        if existing["status"] == "deleting" and status != "deleting":
            db.close()
            return KnowledgeItemService._row_to_item(existing)

        err = error.strip() if status == "failed" else None
        if status == "failed" and not err:
            err = CONTAINER_CHILD_FAILURE_ERROR

        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "UPDATE knowledge_items SET status=?, error=?, updated_at=? WHERE id=?",
            (status, err, now, item_id),
        )
        db.commit()

        row = db.execute(
            """SELECT ki.* FROM knowledge_items ki
               JOIN knowledge_bases kb ON kb.id = ki.base_id
               WHERE ki.id=? AND kb.user_id=?""",
            (item_id, user_id),
        ).fetchone()
        db.close()

        # 协调容器状态
        start_containers = []
        if status == "failed" and row["type"] == "directory":
            start_containers = [existing["group_id"]]
        else:
            start_containers = [row["id"], existing["group_id"]]

        KnowledgeItemService._reconcile_containers(user_id, row["base_id"], start_containers)
        return KnowledgeItemService._row_to_item(row)

    @staticmethod
    def reindex(user_id: int, item_id: str) -> Optional[dict]:
        """重置知识项状态为 idle 以便重新索引"""
        db = get_db()
        existing = db.execute(
            """SELECT ki.* FROM knowledge_items ki
               JOIN knowledge_bases kb ON kb.id = ki.base_id
               WHERE ki.id=? AND kb.user_id=?""",
            (item_id, user_id),
        ).fetchone()
        if not existing:
            db.close()
            return None

        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "UPDATE knowledge_items SET status=?, error=?, updated_at=? WHERE id=?",
            ("idle", None, now, item_id),
        )
        db.commit()
        row = db.execute(
            """SELECT ki.* FROM knowledge_items ki
               JOIN knowledge_bases kb ON kb.id = ki.base_id
               WHERE ki.id=? AND kb.user_id=?""",
            (item_id, user_id),
        ).fetchone()
        db.close()
        return KnowledgeItemService._row_to_item(row)

    @staticmethod
    def delete(user_id: int, item_id: str) -> bool:
        """删除单个知识项"""
        db = get_db()
        existing = db.execute(
            """SELECT ki.* FROM knowledge_items ki
               JOIN knowledge_bases kb ON kb.id = ki.base_id
               WHERE ki.id=? AND kb.user_id=?""",
            (item_id, user_id),
        ).fetchone()
        if not existing:
            db.close()
            return False

        db.execute("DELETE FROM knowledge_items WHERE id=?", (item_id,))
        db.commit()
        base_id = existing["base_id"]
        group_id = existing["group_id"]
        db.close()

        # 协调容器状态
        KnowledgeItemService._reconcile_containers(user_id, base_id, [group_id])
        return True

    @staticmethod
    def _reconcile_containers(user_id: int, base_id: str, start_container_ids: list) -> None:
        """协调容器状态（从子项状态推导）"""
        db = get_db()
        queue = list(dict.fromkeys([cid for cid in start_container_ids if cid]))
        visited = set()

        while queue:
            container_id = queue.pop(0)
            if not container_id or container_id in visited:
                continue
            visited.add(container_id)

            container = db.execute(
                "SELECT * FROM knowledge_items WHERE base_id=? AND id=?",
                (base_id, container_id),
            ).fetchone()

            if not container or container["type"] != "directory" or container["status"] == "deleting":
                continue

            if container["status"] == "preparing":
                if container["group_id"]:
                    queue.append(container["group_id"])
                continue

            stats = db.execute("""
                SELECT
                    SUM(CASE WHEN status NOT IN ('completed', 'failed', 'deleting') THEN 1 ELSE 0 END) AS activecount,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failedcount
                FROM knowledge_items WHERE base_id=? AND group_id=?
            """, (base_id, container_id)).fetchone()

            active_count = stats["activecount"] or 0
            failed_count = stats["failedcount"] or 0

            if active_count > 0:
                now = datetime.now(timezone.utc).isoformat()
                db.execute(
                    "UPDATE knowledge_items SET status='processing', error=NULL, updated_at=? WHERE base_id=? AND id=?",
                    (now, base_id, container_id),
                )
                db.commit()
                if container["group_id"]:
                    queue.append(container["group_id"])
                continue

            next_status = "failed" if failed_count > 0 else "completed"
            next_error = CONTAINER_CHILD_FAILURE_ERROR if next_status == "failed" else None
            now = datetime.now(timezone.utc).isoformat()
            db.execute(
                "UPDATE knowledge_items SET status=?, error=?, updated_at=? WHERE base_id=? AND id=?",
                (next_status, next_error, now, base_id, container_id),
            )
            db.commit()

            if container["group_id"]:
                queue.append(container["group_id"])

        db.close()

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


# 兼容旧接口
class KnowledgeItemServiceCompat:
    """兼容旧接口的包装器"""
    @staticmethod
    def list_items(user_id, base_id, page=1, limit=20, item_type="", group_id=""):
        return KnowledgeItemService.list(user_id, base_id, page, limit, item_type or None, group_id or None)

    @staticmethod
    def get_by_id(user_id, item_id):
        return KnowledgeItemService.get_by_id(user_id, item_id)

    @staticmethod
    def create_item(user_id, base_id, data):
        return KnowledgeItemService.create(user_id, base_id, data)

    @staticmethod
    def update_status(user_id, item_id, status, error=""):
        return KnowledgeItemService.update_status(user_id, item_id, status, error)

    @staticmethod
    def delete_item(user_id, item_id):
        return KnowledgeItemService.delete(user_id, item_id)

    @staticmethod
    def delete_items_by_base(user_id, base_id, item_ids):
        KnowledgeItemService.delete_items_by_ids(user_id, base_id, item_ids)
        return True
