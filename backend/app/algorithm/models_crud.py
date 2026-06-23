"""
独立 models 表 CRUD — 模型配置持久化。

配合 ModelRegistry（registry 数据）一起使用：
- Registry = 全局预设能力（只读）
- Models 表 = 用户覆盖（增删改查）
- 运行时 = Registry 能力 + Models 表覆盖合并
"""

import json
import logging

from app.database import get_db
from app.tables.models import MODELS_TABLE

logger = logging.getLogger(__name__)

ALLOWED_MODELS_FIELDS = {
    "name",
    "capabilities",
    "endpoint_types",
    "context_window",
    "max_output_tokens",
    "max_input_tokens",
    "model_group",
    "is_enabled",
    "metadata",
}


class ModelsCrudService:
    """models 表 CRUD 服务。"""

    def create(
        self,
        provider_id: str,
        model_id: str,
        name: str = "",
        capabilities: list[str] | None = None,
        endpoint_types: list[str] | None = None,
        context_window: int = 0,
        max_output_tokens: int = 0,
        max_input_tokens: int = 0,
        model_group: str = "",
        is_enabled: bool = True,
        metadata: dict | None = None,
    ) -> dict:
        db = get_db()
        db.execute(
            f"""INSERT INTO {MODELS_TABLE}
            (provider_id, model_id, name, capabilities, endpoint_types,
             context_window, max_output_tokens, max_input_tokens, model_group,
             is_enabled, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                provider_id,
                model_id,
                name,
                json.dumps(capabilities or ["chat"]),
                json.dumps(endpoint_types or []),
                context_window,
                max_output_tokens,
                max_input_tokens,
                model_group,
                1 if is_enabled else 0,
                json.dumps(metadata or {}),
            ),
        )
        return self.get(provider_id, model_id)

    def get(self, provider_id: str, model_id: str) -> dict | None:
        db = get_db()
        row = db.execute(
            f"SELECT * FROM {MODELS_TABLE} WHERE provider_id=? AND model_id=?",
            (provider_id, model_id),
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_by_provider(self, provider_id: str, only_enabled: bool = False) -> list[dict]:
        db = get_db()
        sql = f"SELECT * FROM {MODELS_TABLE} WHERE provider_id=?"
        params: list = [provider_id]
        if only_enabled:
            sql += " AND is_enabled=1"
        sql += " ORDER BY model_id"
        rows = db.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update(
        self,
        provider_id: str,
        model_id: str,
        data: dict,
    ) -> dict | None:
        """部分更新模型字段。data 的 key 必须与列名一致。"""
        sets = []
        params = []
        for key, value in data.items():
            if key not in ALLOWED_MODELS_FIELDS:
                raise ValueError(f"Invalid models column: {key}")
            if key in ("capabilities", "endpoint_types", "metadata"):
                value = json.dumps(value)
            sets.append(f"{key}=?")
            params.append(value)
        if not sets:
            return self.get(provider_id, model_id)
        params.extend([provider_id, model_id])
        db = get_db()
        db.execute(
            f"UPDATE {MODELS_TABLE} SET {', '.join(sets)} WHERE provider_id=? AND model_id=?",
            params,
        )
        return self.get(provider_id, model_id)

    def delete(self, provider_id: str, model_id: str) -> bool:
        db = get_db()
        cursor = db.execute(
            f"DELETE FROM {MODELS_TABLE} WHERE provider_id=? AND model_id=?",
            (provider_id, model_id),
        )
        return cursor.rowcount > 0

    def batch_upsert(self, provider_id: str, models: list[dict]) -> list[dict]:
        """批量写入模型行（用于 reconcile 同步）。"""
        results = []
        for m in models:
            mid = m.get("model_id", m.get("id", ""))
            if not mid:
                continue
            existing = self.get(provider_id, mid)
            if existing:
                # 不传 PK 列给 update（它们不在 ALLOWED_MODELS_FIELDS 中）
                update_data = {k: v for k, v in m.items() if k not in ("provider_id", "model_id", "id")}
                self.update(provider_id, mid, update_data)
            else:
                self.create(
                    provider_id=provider_id,
                    model_id=mid,
                    name=m.get("name", ""),
                    capabilities=m.get("capabilities"),
                    endpoint_types=m.get("endpoint_types"),
                    context_window=m.get("context_window", 0),
                    max_output_tokens=m.get("max_output_tokens", 0),
                    max_input_tokens=m.get("max_input_tokens", 0),
                    model_group=m.get("model_group", ""),
                    is_enabled=m.get("is_enabled", True),
                    metadata=m.get("metadata"),
                )
            results.append(self.get(provider_id, mid))
        return results

    def _row_to_dict(self, row) -> dict:
        d = dict(row)
        for field in ("capabilities", "endpoint_types", "metadata"):
            if isinstance(d.get(field), str):
                import contextlib

                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    d[field] = json.loads(d[field])
        return d


# 模块级单例
models_crud = ModelsCrudService()
