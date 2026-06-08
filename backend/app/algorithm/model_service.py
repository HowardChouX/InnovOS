"""
统一模型服务管理 — 供应商 + Key 池融合

每个供应商条目包含：API 地址、Key、模型、轮询配置。
"""
from __future__ import annotations
import json
import time
import logging
from app.database import get_db
from app.algorithm.crypto import encrypt_key, decrypt_key
from app.algorithm.providers_registry import BUILTIN_PROVIDERS

logger = logging.getLogger(__name__)


class ModelService:
    """统一模型服务管理器。"""

    def list_all(self) -> list[dict]:
        """获取所有已配置的供应商（含 Key 池信息）。"""
        db = get_db()
        rows = db.execute("SELECT * FROM model_providers ORDER BY priority ASC, id ASC").fetchall()
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
               (provider_id, name, protocol, api_host, api_key_encrypted, api_model, models, priority, max_rpm, is_enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["provider_id"],
                data["name"],
                data.get("protocol", "openai"),
                data["api_host"],
                encrypt_key(data["api_key"]) if data.get("api_key") else None,
                data.get("api_model", ""),
                json.dumps(data.get("models", [])),
                data.get("priority", 0),
                data.get("max_rpm", 60),
                1 if data.get("is_enabled", True) else 0,
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM model_providers WHERE id=?", (cursor.lastrowid,)).fetchone()
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
        if "priority" in data:
            updates.append("priority=?")
            params.append(data["priority"])
        if "max_rpm" in data:
            updates.append("max_rpm=?")
            params.append(data["max_rpm"])
        if "api_key" in data and data["api_key"]:
            updates.append("api_key_encrypted=?")
            params.append(encrypt_key(data["api_key"]))

        if updates:
            params.append(provider_id)
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
            "SELECT api_host, api_key_encrypted, api_model, models FROM model_providers WHERE provider_id=?",
            (provider_id,),
        ).fetchone()
        db.close()

        if not row:
            builtin = BUILTIN_PROVIDERS.get(provider_id)
            if not builtin:
                return {"status": "error", "message": "供应商不存在"}
            return {"status": "error", "message": "未配置 API Key"}

        if not row["api_key_encrypted"]:
            return {"status": "error", "message": "未配置 API Key"}

        try:
            api_key = decrypt_key(row["api_key_encrypted"])
        except Exception:
            return {"status": "error", "message": "Key 解密失败"}

        # 确定测试模型：优先使用客户端传来的模型
        test_model = model or row["api_model"] or ""
        if not test_model:
            models = json.loads(row["models"]) if row["models"] else []
            test_model = models[0] if models else "deepseek-chat"

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=row["api_host"])

            # 判断模型类型：嵌入模型用 embedding API 测试
            embed_keywords = ['embedding', 'embed', 'bge', 'e5-', 'text-embedding']
            rerank_keywords = ['rerank', 'reranker', 'bge-rerank']
            model_lower = test_model.lower()

            if any(k in model_lower for k in embed_keywords):
                try:
                    start = time.time()
                    resp = client.embeddings.create(model=test_model, input="test")
                    latency = (time.time() - start) * 1000
                    dim = len(resp.data[0].embedding) if resp.data else 0
                    return {"status": "ok", "latency_ms": round(latency, 1), "model": test_model, "type": "embedding", "dimension": dim}
                except Exception as e2:
                    # embedding 失败时 fallback 到 chat 测试
                    try:
                        start = time.time()
                        client.chat.completions.create(model=test_model, messages=[{"role": "user", "content": "hi"}], max_tokens=1)
                        latency = (time.time() - start) * 1000
                        return {"status": "ok", "latency_ms": round(latency, 1), "model": test_model, "type": "chat (embed fallback)"}
                    except Exception:
                        return {"status": "error", "message": f"embed: {str(e2)[:80]}"}
            elif any(k in model_lower for k in rerank_keywords):
                start = time.time()
                resp = client.chat.completions.create(
                    model=test_model,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1,
                )
                latency = (time.time() - start) * 1000
                return {"status": "ok", "latency_ms": round(latency, 1), "model": test_model, "type": "rerank"}
            else:
                start = time.time()
                client.chat.completions.create(
                    model=test_model,
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                )
                latency = (time.time() - start) * 1000
                return {"status": "ok", "latency_ms": round(latency, 1), "model": test_model, "type": "chat"}
        except Exception as e:
            return {"status": "error", "message": str(e)[:100]}

    async def detect_models(self, provider_id: str, api_key_override: str | None = None) -> dict:
        """从供应商 /v1/models 端点获取可用模型列表。"""
        db = get_db()
        row = db.execute(
            "SELECT api_host, api_key_encrypted FROM model_providers WHERE provider_id=?",
            (provider_id,),
        ).fetchone()
        db.close()

        if not row:
            builtin = BUILTIN_PROVIDERS.get(provider_id)
            if not builtin:
                return {"models": []}
            api_host = builtin["api_host"]
            api_key = api_key_override
        else:
            api_host = row["api_host"]
            if api_key_override:
                api_key = api_key_override
            elif row["api_key_encrypted"]:
                try:
                    api_key = decrypt_key(row["api_key_encrypted"])
                except Exception:
                    api_key = None
            else:
                api_key = None

        if not api_key:
            return {"models": []}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{api_host.rstrip('/')}/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code != 200:
                    return {"models": []}
                data = resp.json()
                models = [m["id"] for m in data.get("data", []) if m.get("id")]
                models.sort()
                return {"models": models}
        except Exception:
            return {"models": []}

    def list_builtin(self) -> list[dict]:
        """内置供应商 + 已配置的供应商合并列表。"""
        configured_all = {p["providerId"]: p for p in self.list_all()}
        result = []

        # 1. 内置供应商
        for pid, info in BUILTIN_PROVIDERS.items():
            c = configured_all.pop(pid, None)  # pop 掉已处理的
            result.append({
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
                "apiKeyMasked": c.get("apiKeyMasked", "") if c else "",
                "apiModel": c["apiModel"] if c else "",
                "requestCount": c.get("requestCount", 0) if c else 0,
                "priority": c.get("priority", 0) if c else 0,
            })

        # 2. 自定义供应商（不在内置列表中的已配置提供商）
        for pid, c in configured_all.items():
            result.append({
                "providerId": c["providerId"],
                "name": c["name"],
                "protocol": c["protocol"],
                "apiHost": c["apiHost"],
                "models": c["models"],
                "category": "custom",
                "isConfigured": True,
                "isEnabled": c["isEnabled"],
                "hasApiKey": c["hasApiKey"],
                "apiKeyMasked": c.get("apiKeyMasked", ""),
                "apiModel": c.get("apiModel", ""),
                "requestCount": c.get("requestCount", 0),
                "priority": c.get("priority", 0),
            })

        return result

    def _row_to_dict(self, row) -> dict:
        # Key 脱敏
        masked = ""
        try:
            if row["api_key_encrypted"]:
                plain = decrypt_key(row["api_key_encrypted"])
                masked = plain[:7] + "****" if len(plain) > 7 else "****"
        except Exception:
            masked = "****"

        return {
            "id": row["id"],
            "providerId": row["provider_id"],
            "name": row["name"],
            "protocol": row["protocol"],
            "apiHost": row["api_host"],
            "hasApiKey": bool(row["api_key_encrypted"]),
            "apiKeyMasked": masked,
            "apiModel": row["api_model"],
            "models": json.loads(row["models"]) if row["models"] else [],
            "priority": row["priority"],
            "maxRpm": row["max_rpm"],
            "currentRpm": row["current_rpm"],
            "requestCount": row["request_count"],
            "isEnabled": bool(row["is_enabled"]),
            "lastUsedAt": row["last_used_at"],
            "createdAt": row["created_at"],
        }


model_service = ModelService()
