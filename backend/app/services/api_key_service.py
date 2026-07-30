"""
供应商 API Key 服务 — 加密 CRUD + 公平租用 + failover 状态管理。

所有读写都走数据库(api_keys 表),不再读环境变量。plaintext 仅在
lease_key 返回的 ApiKeyLease 中,供运行时调用;其他所有方法永不返回 plaintext。

事务:
- create_key:SELECT 查重 → INSERT 加密产物 → 返回掩码
- replace_secret:SELECT FOR UPDATE → UPDATE 密文 + 清 cooldown
- lease_key:原子租用(lease_count++, last_used_at=NOW())返回明文 lease
- mark_success / mark_failure:更新统计 + cooldown
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


# ── 数据结构 ──


@dataclass(frozen=True)
class ApiKeyLease:
    """运行时租用,含明文。仅供服务端运行时调用,绝不入日志。"""

    key_id: int
    provider_id: str
    plaintext: str


# ── Service ──


class ApiKeyService:
    """api_keys 表的 CRUD + 租用门面。"""

    def __init__(self, db: Any, cipher: Any) -> None:
        self._db = db
        self._cipher = cipher

    # 公开 cipher 给测试与 runtime 使用(runtime 可能在外部需要直接加密场景)
    @property
    def cipher(self):
        return self._cipher

    # ── 辅助 ──

    def _execute(self, sql: str, params: tuple | None = None):
        return self._db.execute(sql, params)

    def _commit(self) -> None:
        if hasattr(self._db, "commit"):
            self._db.commit()

    def _row_to_masked(self, row: dict[str, Any]) -> dict[str, Any]:
        """把数据库行转成不泄漏 plaintext/ciphertext/nonce 的视图。

        掩码规则:
        - 用 prefix 长度 + 8 个 • + suffix 4 位
        - 单独返回 prefix 字符串供前端 UI 展示"识别标签",但绝不暴露完整明文
        """
        fingerprint_hex = row["key_fingerprint"].hex()
        short_fp = fingerprint_hex[:12]
        prefix = row.get("key_prefix") or ""
        suffix = row.get("key_suffix") or ""
        if prefix and suffix:
            masked = f"{prefix}{'•' * 8}{suffix}"
        elif suffix:
            masked = f"••••••••{suffix}"
        else:
            masked = "••••••••••••"
        return {
            "id": row["id"],
            "provider_id": row["provider_id"],
            "name": row["name"],
            "masked": masked,
            "prefix": prefix,  # 仅供 UI 标签,如 "sk-";不含明文
            "fingerprint": short_fp,
            "priority": row["priority"],
            "is_active": bool(row["is_active"]),
            "max_rpm": row.get("max_rpm"),
            "request_count": row["request_count"],
            "success_count": row["success_count"],
            "failure_count": row["failure_count"],
            "last_used_at": row.get("last_used_at"),
            "cooldown_until": row.get("cooldown_until"),
            "last_error_code": row.get("last_error_code"),
            "created_by": row.get("created_by"),
            "updated_by": row.get("updated_by"),
        }

    # ── CREATE ──

    def create_key(
        self,
        *,
        provider_id: str,
        name: str,
        plaintext: str,
        priority: int = 100,
        max_rpm: int | None = None,
        actor_id: int,
    ) -> dict[str, Any]:
        # 先 reserve id(让 AAD 包含 key_id)
        row = self._execute(
            "INSERT INTO api_keys (provider_id, name, key_ciphertext, key_nonce, "
            "encryption_version, key_fingerprint, key_prefix, key_suffix, "
            "priority, max_rpm, created_by, updated_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                provider_id,
                name,
                b"\x00" * 16,  # placeholder; updated below
                b"\x00" * 12,
                1,
                b"\x00" * 32,
                "",
                "",
                priority,
                max_rpm,
                actor_id,
                actor_id,
            ),
        ).fetchone()
        if not row:
            raise RuntimeError("INSERT api_keys failed: no id returned")
        key_id = row["id"]

        # 真加密
        encrypted = self._cipher.encrypt(
            plaintext=plaintext, provider_id=provider_id, key_id=key_id
        )

        # 查重:fingerprint 唯一约束由 DB 兜底,但应用层先 SELECT
        existing = self._execute(
            "SELECT id FROM api_keys WHERE provider_id=? AND key_fingerprint=?",
            (provider_id, encrypted.fingerprint),
        ).fetchone()
        if existing and existing["id"] != key_id:
            # 回滚自己插入的占位
            self._execute("DELETE FROM api_keys WHERE id=?", (key_id,))
            raise ValueError(
                f"duplicate API key fingerprint for provider '{provider_id}'"
            )

        # 写回真密文
        self._execute(
            "UPDATE api_keys SET key_ciphertext=?, key_nonce=?, encryption_version=?, "
            "key_fingerprint=?, key_prefix=?, key_suffix=? WHERE id=?",
            (
                encrypted.ciphertext,
                encrypted.nonce,
                encrypted.encryption_version,
                encrypted.fingerprint,
                encrypted.prefix,
                encrypted.suffix,
                key_id,
            ),
        )
        self._commit()

        # 重新读返掩码
        final_row = self._execute(
            "SELECT * FROM api_keys WHERE id=?", (key_id,)
        ).fetchone()
        return self._row_to_masked(final_row)

    # ── LIST ──

    def list_keys(
        self,
        *,
        provider_id: str,
        include_inactive: bool = True,
    ) -> list[dict[str, Any]]:
        if include_inactive:
            rows = self._execute(
                "SELECT * FROM api_keys WHERE provider_id=? ORDER BY priority ASC, id ASC",
                (provider_id,),
            ).fetchall()
        else:
            rows = self._execute(
                "SELECT * FROM api_keys WHERE provider_id=? AND is_active=TRUE "
                "ORDER BY priority ASC, id ASC",
                (provider_id,),
            ).fetchall()
        return [self._row_to_masked(r) for r in (rows or [])]

    # ── UPDATE METADATA ──

    def update_metadata(
        self,
        *,
        key_id: int,
        name: str | None = None,
        priority: int | None = None,
        max_rpm: int | None = None,
        is_active: bool | None = None,
        actor_id: int,
    ) -> dict[str, Any] | None:
        updates, params = [], []
        if name is not None:
            updates.append("name=?")
            params.append(name)
        if priority is not None:
            updates.append("priority=?")
            params.append(priority)
        if max_rpm is not None:
            updates.append("max_rpm=?")
            params.append(max_rpm)
        if is_active is not None:
            updates.append("is_active=?")
            params.append(is_active)
        updates.append("updated_by=?")
        params.append(actor_id)
        updates.append("updated_at=NOW()")
        params.append(key_id)

        self._execute(
            f"UPDATE api_keys SET {', '.join(updates)} WHERE id=?",
            tuple(params),
        )
        self._commit()
        row = self._execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
        return self._row_to_masked(row) if row else None

    # ── REPLACE SECRET ──

    def replace_secret(
        self,
        *,
        key_id: int,
        plaintext: str,
        actor_id: int,
    ) -> dict[str, Any] | None:
        row = self._execute(
            "SELECT provider_id FROM api_keys WHERE id=?", (key_id,)
        ).fetchone()
        if not row:
            return None
        provider_id = row["provider_id"]

        encrypted = self._cipher.encrypt(
            plaintext=plaintext, provider_id=provider_id, key_id=key_id
        )
        # 替换密文 + 清 cooldown + 清错误码 + 更新 actor
        self._execute(
            "UPDATE api_keys SET key_ciphertext=?, key_nonce=?, encryption_version=?, "
            "key_fingerprint=?, key_prefix=?, key_suffix=?, "
            "cooldown_until=NULL, last_error_code=NULL, "
            "updated_by=?, updated_at=NOW() WHERE id=?",
            (
                encrypted.ciphertext,
                encrypted.nonce,
                encrypted.encryption_version,
                encrypted.fingerprint,
                encrypted.prefix,
                encrypted.suffix,
                actor_id,
                key_id,
            ),
        )
        self._commit()
        row = self._execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
        return self._row_to_masked(row) if row else None

    # ── ACTIVATE / DEACTIVATE / DELETE ──

    def deactivate(self, *, key_id: int, actor_id: int) -> dict[str, Any] | None:
        return self.update_metadata(key_id=key_id, is_active=False, actor_id=actor_id)

    def activate(self, *, key_id: int, actor_id: int) -> dict[str, Any] | None:
        return self.update_metadata(key_id=key_id, is_active=True, actor_id=actor_id)

    def delete_key(self, *, key_id: int, actor_id: int) -> bool:
        """软删(is_active=false),保留审计;如需硬删,运营需走 DB 直接操作。"""
        result = self.deactivate(key_id=key_id, actor_id=actor_id)
        return result is not None

    # ── LEASE (运行时唯一入口返回 plaintext) ──

    def lease_key(
        self,
        *,
        provider_id: str,
        exclude_key_ids: set[int] | None = None,
    ) -> ApiKeyLease | None:
        """公平租用一把可用的 Key,并发安全。

        选择规则:
        1. is_active=TRUE
        2. cooldown_until 为 NULL 或 <= NOW()
        3. 在最高可用 priority 层中选(数字越小越优先)
        4. 同 priority 按 lease_count ASC, last_used_at ASC NULLS FIRST, id ASC
        5. 排除 exclude_key_ids(同请求已尝试过)
        """
        exclude_clause = ""
        params: list[Any] = [provider_id]
        if exclude_key_ids:
            placeholders = ",".join("?" for _ in exclude_key_ids)
            exclude_clause = f" AND id NOT IN ({placeholders})"
            params.extend(exclude_key_ids)

        # SQL:选最高可用 priority 层的候选,然后按 lease_count 公平
        sql = (
            "SELECT * FROM api_keys "
            "WHERE provider_id=? AND is_active=TRUE "
            "  AND (cooldown_until IS NULL OR cooldown_until <= NOW()) "
            f"  AND priority = ("
            "    SELECT MIN(priority) FROM api_keys "
            "    WHERE provider_id=? AND is_active=TRUE "
            "      AND (cooldown_until IS NULL OR cooldown_until <= NOW())"
            "  )"
            f"{exclude_clause} "
            "ORDER BY lease_count ASC, last_used_at ASC NULLS FIRST, id ASC "
            "LIMIT 1"
        )
        params.insert(1, provider_id)  # for inner SELECT
        row = self._execute(sql, tuple(params)).fetchone()
        if not row:
            return None

        # 原子租用 — UPDATE 返回后我们拿回 row
        key_id = row["id"]
        self._execute(
            "UPDATE api_keys SET lease_count = lease_count + 1, "
            "last_used_at = NOW(), updated_at = NOW() WHERE id=?",
            (key_id,),
        )
        self._commit()

        # 解密
        try:
            plaintext = self._cipher.decrypt(
                ciphertext=row["key_ciphertext"],
                nonce=row["key_nonce"],
                encryption_version=row["encryption_version"],
                provider_id=row["provider_id"],
                key_id=key_id,
            )
        except Exception:
            # 解密失败:禁用该 Key,不让业务继续尝试
            self._execute(
                "UPDATE api_keys SET is_active=FALSE, "
                "last_error_code='decryption_failed', updated_at=NOW() WHERE id=?",
                (key_id,),
            )
            self._commit()
            return None

        return ApiKeyLease(
            key_id=key_id,
            provider_id=row["provider_id"],
            plaintext=plaintext,
        )

    # ── 状态更新 ──

    def mark_success(self, *, key_id: int) -> None:
        self._execute(
            "UPDATE api_keys SET success_count = success_count + 1, "
            "request_count = request_count + 1, "
            "last_success_at = NOW(), updated_at = NOW() WHERE id=?",
            (key_id,),
        )
        self._commit()

    def mark_failure(
        self,
        *,
        key_id: int,
        category: Literal[
            "auth", "rate_limit", "timeout", "network", "provider", "unknown"
        ],
        cooldown_until: datetime | None = None,
    ) -> None:
        params: list[Any] = [category]
        cooldown_sql = ""
        if cooldown_until is not None:
            cooldown_sql = ", cooldown_until=?"
            params.append(cooldown_until)
        params.append(key_id)
        self._execute(
            f"UPDATE api_keys SET failure_count = failure_count + 1, "
            f"request_count = request_count + 1, "
            f"last_failure_at = NOW(), last_error_code=?{cooldown_sql}, "
            f"updated_at = NOW() WHERE id=?",
            tuple(params),
        )
        self._commit()

    def has_active_key(self, *, provider_id: str) -> bool:
        row = self._execute(
            "SELECT COUNT(*) AS c FROM api_keys WHERE provider_id=? AND is_active=TRUE",
            (provider_id,),
        ).fetchone()
        return bool(row and row.get("c", 0))


# ── 工厂 helper ──


def get_api_key_service(db: object | None = None) -> ApiKeyService:
    """构造 ApiKeyService 实例,统一 cipher + db 加载路径。

    使用方:model_service._get_provider_api_key / _has_provider_api_key,
    admin/providers._get_api_key_service, ai_client.ProviderKeyPool,
    api/analysis._create_ai_base 等。
    """
    from app.core.key_crypto import load_api_key_cipher
    from app.database import get_db

    return ApiKeyService(
        db=db if db is not None else get_db(),
        cipher=load_api_key_cipher(),
    )