"""
API Key管理器

功能：
1. Key池轮询（支持按 Provider 过滤）
2. 并发控制（信号量）
3. 限流检测
4. 自动切换失败Key
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional
from app.database import get_db
from app.algorithm.crypto import encrypt_key, decrypt_key


class APIKeyManager:
    def __init__(self):
        # 并发控制：最多同时5个请求
        self._semaphore = asyncio.Semaphore(5)
        # 当前Key索引（轮询，按 provider 分组）
        self._current_index: dict[str, int] = {}
        # Key缓存（按 provider 分组）
        self._keys_cache: dict[str, list] = {}
        self._cache_updated_at: float = 0
        # 缓存过期时间（秒）
        self._cache_ttl = 30

    async def acquire(self):
        """获取并发许可"""
        await self._semaphore.acquire()

    def release(self):
        """释放并发许可"""
        self._semaphore.release()

    def _refresh_keys_cache(self):
        """刷新Key缓存（按 provider 分组）"""
        now = time.time()
        if now - self._cache_updated_at < self._cache_ttl:
            return

        db = get_db()
        keys = db.execute(
            "SELECT * FROM api_keys WHERE is_active=1 ORDER BY priority ASC, id ASC"
        ).fetchall()
        db.close()

        # 按 provider_id 分组
        grouped: dict[str, list] = {}
        for k in keys:
            d = dict(k)
            pid = d.get("provider_id", "") or ""
            try:
                d["api_key"] = decrypt_key(d["api_key"])
                if pid not in grouped:
                    grouped[pid] = []
                grouped[pid].append(d)
            except Exception:
                continue

        self._keys_cache = grouped
        self._cache_updated_at = now

    def _get_next_key(self, provider_id: str = "") -> dict:
        """获取下一个可用的Key（轮询），支持按 provider 过滤"""
        self._refresh_keys_cache()

        # 获取指定 provider 的 keys，或所有 keys
        if provider_id:
            keys = self._keys_cache.get(provider_id, [])
        else:
            # 合并所有 provider 的 keys
            keys = [k for pool in self._keys_cache.values() for k in pool]

        if keys:
            idx = self._current_index.get(provider_id, 0) % len(keys)
            key = keys[idx]
            self._current_index[provider_id] = idx + 1
            return key

        raise RuntimeError("未配置任何可用的API Key，请在管理后台添加")

    def _check_rate_limit(self, key: dict) -> bool:
        """检查Key是否达到限流"""
        db = get_db()

        # 检查是否需要重置计数
        if key.get("last_reset_at"):
            try:
                last_reset = datetime.fromisoformat(key["last_reset_at"])
                if datetime.now() - last_reset > timedelta(minutes=1):
                    db.execute(
                        "UPDATE api_keys SET current_rpm=0, last_reset_at=datetime('now') WHERE id=?",
                        (key["id"],)
                    )
                    db.commit()
                    key["current_rpm"] = 0
            except (ValueError, TypeError):
                db.execute(
                    "UPDATE api_keys SET current_rpm=0, last_reset_at=datetime('now') WHERE id=?",
                    (key["id"],)
                )
                db.commit()
                key["current_rpm"] = 0

        if key.get("current_rpm", 0) >= key.get("max_rpm", 60):
            db.close()
            return False

        db.close()
        return True

    def record_usage(self, key_id: int):
        """记录Key使用次数"""
        try:
            db = get_db()
            db.execute(
                """UPDATE api_keys
                   SET request_count = request_count + 1,
                       current_rpm = current_rpm + 1,
                       last_used_at = datetime('now'),
                       last_reset_at = CASE
                           WHEN last_reset_at IS NULL OR datetime(last_reset_at) < datetime('now', '-1 minute')
                           THEN datetime('now')
                           ELSE last_reset_at
                       END
                   WHERE id=?""",
                (key_id,)
            )
            db.commit()
            db.close()
        except Exception:
            pass

    def mark_key_failed(self, key_id: int, error_type: str):
        """标记Key失败"""
        try:
            db = get_db()

            if error_type in ("401", "403"):
                db.execute(
                    "UPDATE api_keys SET is_active=0 WHERE id=?",
                    (key_id,)
                )
            elif error_type == "429":
                db.execute(
                    "UPDATE api_keys SET current_rpm=max_rpm WHERE id=?",
                    (key_id,)
                )

            db.commit()
            db.close()
            self._cache_updated_at = 0
        except Exception:
            pass

    async def get_key_for_request(self, provider_id: str = "") -> dict:
        """获取适合当前请求的Key

        Args:
            provider_id: 指定供应商ID，为空则轮询所有可用Key
        """
        for _ in range(min(len(self._keys_cache.get(provider_id, []) or [1]), 10)):
            key = self._get_next_key(provider_id)
            if self._check_rate_limit(key):
                return key

        await asyncio.sleep(1)
        return self._get_next_key(provider_id)

    def get_key_by_id(self, key_id: int) -> Optional[dict]:
        """根据ID获取Key"""
        db = get_db()
        row = db.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchall()
        db.close()
        if not row:
            return None
        result = dict(row[0])
        result["api_key"] = decrypt_key(result["api_key"])
        return result

    def list_keys(self, provider_id: str = None) -> list:
        """获取Key列表，可按 provider_id 过滤"""
        db = get_db()
        if provider_id:
            rows = db.execute(
                "SELECT * FROM api_keys WHERE provider_id=? ORDER BY priority ASC, id ASC",
                (provider_id,)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM api_keys ORDER BY priority ASC, id ASC").fetchall()
        db.close()
        return [dict(r) for r in rows]

    def create_key(self, key_name: str, api_key: str, api_base_url: str = "https://api.deepseek.com",
                   api_model: str = "deepseek-chat", priority: int = 0, max_rpm: int = 60,
                   provider_id: str = "") -> dict:
        """创建新Key"""
        db = get_db()
        encrypted_key = encrypt_key(api_key)
        cursor = db.execute(
            """INSERT INTO api_keys (provider_id, key_name, api_key, api_base_url, api_model, priority, max_rpm)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (provider_id, key_name, encrypted_key, api_base_url, api_model, priority, max_rpm)
        )
        db.commit()
        row = db.execute("SELECT * FROM api_keys WHERE id=?", (cursor.lastrowid,)).fetchone()
        db.close()
        self._cache_updated_at = 0
        return dict(row)

    def update_key(self, key_id: int, **kwargs) -> Optional[dict]:
        """更新Key"""
        db = get_db()
        row = db.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
        if not row:
            db.close()
            return None

        updates = []
        params = []

        for field in ["key_name", "api_key", "api_base_url", "api_model", "priority", "max_rpm", "provider_id"]:
            if field in kwargs and kwargs[field] is not None:
                updates.append(f"{field}=?")
                params.append(encrypt_key(kwargs[field]) if field == "api_key" else kwargs[field])

        if "is_active" in kwargs:
            updates.append("is_active=?")
            params.append(1 if kwargs["is_active"] else 0)

        if updates:
            params.append(key_id)
            db.execute(f"UPDATE api_keys SET {', '.join(updates)} WHERE id=?", params)
            db.commit()

        row = db.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
        db.close()
        self._cache_updated_at = 0
        return dict(row)

    def delete_key(self, key_id: int) -> bool:
        """删除Key"""
        db = get_db()
        db.execute("DELETE FROM api_keys WHERE id=?", (key_id,))
        db.commit()
        db.close()
        self._cache_updated_at = 0
        return True


# 全局实例
key_manager = APIKeyManager()
