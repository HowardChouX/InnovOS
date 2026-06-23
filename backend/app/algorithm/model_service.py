"""
统一模型服务管理 — 供应商管理

每个供应商条目包含：API 地址、模型、轮询配置。
API 密钥来自环境变量，不存储在数据库中。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, cast

from app.algorithm.model_registry import model_registry
from app.algorithm.providers_registry import (
    BUILTIN_PROVIDERS,
    get_model_id,
    infer_capabilities,
    normalize_model,
)
from app.database import get_db

# ── 环境变量辅助函数（可供其他模块导入） ────────────────────


def _get_provider_api_key(provider_id: str) -> str | None:
    """从环境变量读取供应商 API Key。

    格式: AI_{PROVIDER_ID}_API_KEY (大写, 下划线分隔)
    """
    env_key = f"AI_{provider_id.upper()}_API_KEY"
    return os.getenv(env_key) or None


def _has_provider_api_key(provider_id: str) -> bool:
    """检查环境变量中是否存在该供应商的 API Key。"""
    return _get_provider_api_key(provider_id) is not None


# ── 供应商字段校验 ──────────────────────────────────────

ALLOWED_MODEL_PROVIDER_FIELDS = {
    "name",
    "protocol",
    "api_host",
    "api_model",
    "models",
    "is_enabled",
    "max_rpm",
}


def _validate_columns(fields: list[str], allowed: set[str]) -> None:
    for f in fields:
        if f not in allowed:
            raise ValueError(f"Invalid column: {f}")


logger = logging.getLogger(__name__)


class ModelService:
    """统一模型服务管理器。"""

    def list_all(self) -> list[dict]:
        """获取所有已配置的供应商。"""
        db = get_db()
        rows = db.execute("SELECT * FROM model_providers ORDER BY id ASC").fetchall()
        db.close()
        return [self._row_to_dict(r) for r in rows]

    def get(self, provider_id: str) -> dict | None:
        db = get_db()
        row = db.execute("SELECT * FROM model_providers WHERE provider_id=?", (provider_id,)).fetchone()
        db.close()
        return self._row_to_dict(row) if row else None

    def add(self, data: dict) -> dict:
        db = get_db()
        cursor = db.execute(
            """INSERT INTO model_providers
               (provider_id, name, protocol, api_host, api_model, models, max_rpm, is_enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (
                data["provider_id"],
                data["name"],
                data.get("protocol", "openai"),
                data["api_host"],
                data.get("api_model", ""),
                json.dumps(data.get("models", [])),
                data.get("max_rpm", 60),
                1 if data.get("is_enabled", True) else 0,
            ),
        )
        db.commit()
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError(f"INSERT failed for provider {data.get('provider_id')}")
        inserted_id = row["id"]
        row = db.execute("SELECT * FROM model_providers WHERE id=?", (inserted_id,)).fetchone()
        db.close()
        return self._row_to_dict(row)

    def update(self, provider_id: str, data: dict) -> dict | None:
        db = get_db()
        row = db.execute("SELECT * FROM model_providers WHERE provider_id=?", (provider_id,)).fetchone()
        if not row:
            db.close()
            return None

        updates, params = [], []
        for field in ["name", "protocol", "api_host", "api_model"]:
            if field in data and data[field] is not None:
                updates.append(f"{field}=?")
                params.append(data[field])
        if "models" in data:
            updates.append("models=?")
            params.append(json.dumps(data["models"]))
        if "is_enabled" in data:
            updates.append("is_enabled=?")
            params.append(1 if data["is_enabled"] else 0)
        if "max_rpm" in data:
            updates.append("max_rpm=?")
            params.append(data["max_rpm"])
        # API Key 不再通过 UI 更新，密钥来自环境变量

        if updates:
            params.append(provider_id)
            _validate_columns([u.split("=")[0].strip() for u in updates], ALLOWED_MODEL_PROVIDER_FIELDS)
            db.execute(f"UPDATE model_providers SET {', '.join(updates)} WHERE provider_id=?", params)
            db.commit()

        row = db.execute("SELECT * FROM model_providers WHERE provider_id=?", (provider_id,)).fetchone()
        db.close()
        return self._row_to_dict(row)

    def delete(self, provider_id: str) -> bool:
        db = get_db()
        db.execute("DELETE FROM model_providers WHERE provider_id=?", (provider_id,))
        db.commit()
        db.close()
        return True

    def toggle(self, provider_id: str) -> dict | None:
        """启用/禁用切换。"""
        db = get_db()
        row = db.execute("SELECT is_enabled FROM model_providers WHERE provider_id=?", (provider_id,)).fetchone()
        if not row:
            db.close()
            return None
        new_val = 0 if row["is_enabled"] else 1
        db.execute("UPDATE model_providers SET is_enabled=? WHERE provider_id=?", (new_val, provider_id))
        db.commit()
        row = db.execute("SELECT * FROM model_providers WHERE provider_id=?", (provider_id,)).fetchone()
        db.close()
        return self._row_to_dict(row)

    async def check_connection(self, provider_id: str, model: str | None = None) -> dict:
        """检查连接（测试延迟）。"""
        db = get_db()
        row = db.execute(
            "SELECT api_host, api_model, models FROM model_providers WHERE provider_id=?",
            (provider_id,),
        ).fetchone()
        db.close()

        if not row:
            builtin = BUILTIN_PROVIDERS.get(provider_id)
            if not builtin:
                return {"status": "error", "message": "供应商不存在"}
            return {"status": "error", "message": "未配置 API Key"}

        api_key = _get_provider_api_key(provider_id)
        if not api_key:
            return {"status": "error", "message": "未配置 API Key（请在环境变量中设置）"}

        # 确定测试模型：优先使用客户端传来的模型
        test_model = model or row["api_model"] or ""
        if not test_model:
            models_raw = self._parse_models(row)
            models = [normalize_model(m) for m in models_raw]
            test_model = get_model_id(models[0]) if models else "deepseek-chat"

        try:
            from app.algorithm.model_runtime import ModelRuntime

            return ModelRuntime.test_connection(provider_id, test_model, api_key_override=api_key)
        except Exception as e:
            return {"status": "error", "message": str(e)[:100]}

    async def detect_models(self, provider_id: str) -> dict:
        """从供应商 /v1/models 端点获取可用模型列表。

        API 密钥从环境变量读取，不再需要 api_key_override 参数。
        """
        db = get_db()
        row = db.execute(
            "SELECT api_host FROM model_providers WHERE provider_id=?",
            (provider_id,),
        ).fetchone()
        db.close()

        if not row:
            builtin_raw = BUILTIN_PROVIDERS.get(provider_id)
            if not builtin_raw:
                return {"models": []}
            builtin = cast(dict[str, Any], builtin_raw)
            api_host = builtin["api_host"]
        else:
            api_host = row["api_host"]

        api_key = _get_provider_api_key(provider_id)
        if not api_key:
            return {"models": []}

        try:
            import httpx

            async with httpx.AsyncClient(timeout=15) as client:
                base = api_host.rstrip("/")
                models_url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
                resp = await client.get(
                    models_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code != 200:
                    logger.warning("detect_models %s: HTTP %d %s", provider_id, resp.status_code, resp.text[:200])
                    return {"models": [], "error": f"HTTP {resp.status_code}"}
                data = resp.json()
                model_ids = sorted(m["id"] for m in data.get("data", []) if m.get("id"))
                return {"models": model_registry.enrich_models(provider_id, model_ids)}
        except Exception as e:
            logger.warning("detect_models %s failed: %s", provider_id, e)
            return {"models": [], "error": str(e)[:100]}

    def list_builtin(self) -> list[dict]:
        """内置供应商 + 已配置的供应商合并列表。"""
        configured_all = {p["providerId"]: p for p in self.list_all()}
        result = []

        # 1. 内置供应商
        for pid, raw_info in BUILTIN_PROVIDERS.items():
            info = cast(dict[str, Any], raw_info)
            c = configured_all.pop(pid, None)  # pop 掉已处理的
            result.append(
                {
                    "providerId": info["id"],
                    "name": info["name"],
                    "protocol": info["protocol"],
                    "apiHost": info["api_host"],
                    "models": c["models"] if c else [],
                    "website": info.get("website", ""),
                    "keyUrl": info.get("key_url", ""),
                    "category": info.get("category", "other"),
                    "isConfigured": c is not None,
                    "isEnabled": c["isEnabled"] if c else False,
                    "hasApiKey": c["hasApiKey"] if c else False,
                    "apiKeyMasked": "",  # 不再暴露密钥
                    "apiModel": c["apiModel"] if c else "",
                    "requestCount": c.get("requestCount", 0) if c else 0,
                    "priority": c.get("priority", 0) if c else 0,
                }
            )

        # 2. 自定义供应商（不在内置列表中的已配置提供商）
        for _pid, c in configured_all.items():
            result.append(
                {
                    "providerId": c["providerId"],
                    "name": c["name"],
                    "protocol": c["protocol"],
                    "apiHost": c["apiHost"],
                    "models": c["models"],
                    "category": "custom",
                    "isConfigured": True,
                    "isEnabled": c["isEnabled"],
                    "hasApiKey": c["hasApiKey"],
                    "apiKeyMasked": "",
                    "apiModel": c.get("apiModel", ""),
                    "requestCount": c.get("requestCount", 0),
                    "priority": c.get("priority", 0),
                }
            )

        return result

    def reconcile_models(self, provider_id: str, detected_models: list) -> dict | None:
        """比较 API 发现的模型 vs 已存储模型，返回差异。

        调用方应先 call `detect_models()` (async), 再传入其结果。

        匹配 CherryStudio buildModelListSyncPreview() 逻辑。
        返回 { added: [...], removed: [...], unchanged: [...] }
        或 None (provider 不存在)。
        """
        db = get_db()
        row = db.execute("SELECT models FROM model_providers WHERE provider_id=?", (provider_id,)).fetchone()
        db.close()
        if not row:
            return None

        stored_raw = self._parse_models(row)
        stored_ids = set()
        for m in stored_raw:
            mid = get_model_id(m)
            if mid:
                stored_ids.add(mid)

        detected_ids = {get_model_id(m) for m in detected_models}

        added = sorted(detected_ids - stored_ids)
        removed = sorted(stored_ids - detected_ids)
        unchanged = sorted(stored_ids & detected_ids)

        enriched_added = model_registry.enrich_models(provider_id, added)

        return {
            "added": enriched_added,
            "removed": [{"id": mid} for mid in removed],
            "unchanged": [{"id": mid} for mid in unchanged],
        }

    def reconcile_apply(self, provider_id: str, to_add: list[str], to_remove: list[str]) -> dict | None:
        """应用 reconcile diff: 添加/删除模型。"""
        db = get_db()
        row = db.execute("SELECT models FROM model_providers WHERE provider_id=?", (provider_id,)).fetchone()
        if not row:
            db.close()
            return None

        stored_raw = self._parse_models(row)
        stored_by_id: dict[str, dict] = {}
        for m in stored_raw:
            mid = get_model_id(m)
            if mid:
                stored_by_id[mid] = normalize_model(m)

        for rid in to_remove:
            stored_by_id.pop(rid, None)

        to_add_enriched = model_registry.enrich_models(provider_id, to_add)
        for entry in to_add_enriched:
            sid = entry.get("id")
            if sid:
                stored_by_id[sid] = entry

        new_models = list(stored_by_id.values())
        db.execute("UPDATE model_providers SET models=? WHERE provider_id=?", (json.dumps(new_models), provider_id))
        db.commit()
        self._sync_models_table(db, provider_id, new_models)
        row = db.execute("SELECT * FROM model_providers WHERE provider_id=?", (provider_id,)).fetchone()
        db.close()
        return self._row_to_dict(row)

    def _sync_models_table(self, db, provider_id: str, models: list[dict]):
        """同步 models 表与 JSON 列数据。"""
        db.execute("DELETE FROM models WHERE provider_id=?", (provider_id,))
        for entry in models:
            mid = get_model_id(entry)
            if not mid:
                continue
            caps = json.dumps(entry.get("capabilities", infer_capabilities(mid)))
            db.execute(
                """INSERT INTO models (provider_id, model_id, capabilities)
                   VALUES (?, ?, ?) ON CONFLICT (provider_id, model_id)
                   DO UPDATE SET capabilities=excluded.capabilities""",
                (provider_id, mid, caps),
            )

    @staticmethod
    def _parse_models(row) -> list:
        """解析 models 列：兼容 PostgreSQL（已 parsing 为 list）和 JSON 字符串。"""
        val = row["models"]
        if isinstance(val, list):
            return val
        return json.loads(val) if val else []

    def _enrich_model(self, provider_id: str, entry) -> dict:
        """对单个模型条目做 registry enrichment + 正则兜底。"""
        model_id = get_model_id(entry)
        info = model_registry.get_model_info(model_id, provider_id)
        caps = info.get("capabilities", infer_capabilities(model_id))
        result = {"id": model_id, "capabilities": caps}
        ep = info.get("endpointTypes")
        if ep:
            result["endpointTypes"] = ep
        return result

    async def batch_check_models(self, provider_id: str, model_ids: list[str]) -> dict:
        """批量检查指定的模型连接状态。"""

        async def _check(mid: str) -> dict:
            try:
                result = await self.check_connection(provider_id, mid)
                return {
                    "modelId": mid,
                    "status": result.get("status", "error"),
                    "latency": result.get("latency"),
                    "error": result.get("message") if result.get("status") == "error" else None,
                }
            except Exception as e:
                return {"modelId": mid, "status": "error", "latency": None, "error": str(e)}

        tasks = [_check(mid) for mid in model_ids]
        results = await asyncio.gather(*tasks)
        results.sort(key=lambda r: model_ids.index(r["modelId"]))
        return {"providerId": provider_id, "models": results}

    def _row_to_dict(self, row) -> dict:
        provider_id = row["provider_id"]
        raw_models = self._parse_models(row)

        return {
            "id": row["id"],
            "providerId": provider_id,
            "name": row["name"],
            "protocol": row["protocol"],
            "apiHost": row["api_host"],
            "hasApiKey": _has_provider_api_key(provider_id),
            "apiKeyMasked": "",  # 不再暴露密钥
            "apiModel": row["api_model"],
            "models": [self._enrich_model(provider_id, m) for m in raw_models],
            "maxRpm": row["max_rpm"],
            "currentRpm": row["current_rpm"],
            "requestCount": row["request_count"],
            "isEnabled": bool(row["is_enabled"]),
            "lastUsedAt": row["last_used_at"],
            "createdAt": row["created_at"],
        }


model_service = ModelService()
