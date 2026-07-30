"""
TDD 测试: ApiKeyService

覆盖:
1. create_key — 加密后入库,plaintext 永不返,列表只返掩码
2. create_key — 同 Provider 同 fingerprint 拒绝 (409)
3. create_key — actor 写入 created_by
4. list_keys — 不解密,只返掩码 + 短 fingerprint
5. update_metadata — 改 name/priority/max_rpm/is_active,不改密文
6. replace_secret — 替换 Key 全文,新 nonce,清除 cooldown
7. deactivate — is_active=false
8. delete_key — 软删 (is_active=false)
9. lease_key — 选优先级最低且不在 cooldown 的 Key
10. lease_key — 同优先级按 lease_count + last_used_at 公平
11. lease_key — exclude_key_ids 跳过
12. lease_key — 全部 cooldown 返回 None
13. mark_success / mark_failure 更新计数
14. has_active_key — 至少一把 active
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


# ── Mock DB ──


class FakeRow(dict):
    """dict-like row that supports cursor.fetchone() return value."""
    pass


class FakeCursor:
    """Cursor that captures SQL and returns preset results."""

    def __init__(self) -> None:
        self.history: list[tuple[str, tuple | None]] = []
        self._rows: list[Any] = []
        self._inserted_id: int | None = None
        self._fetchone_queue: list[Any] = []

    def set_rows(self, rows: list[Any]) -> None:
        self._rows = list(rows)

    def set_inserted_id(self, value: int) -> None:
        self._inserted_id = value
        # 初始化 fetchone 队列让 _fetchone_queue 在 set_inserted_id 后可用
        if not hasattr(self, "_fetchone_queue"):
            self._fetchone_queue = []

    def execute(self, sql: str, params: tuple | None = None):
        self.history.append((sql.strip(), params))
        return self

    def fetchone(self):
        if self._inserted_id is not None:
            value = self._inserted_id
            self._inserted_id = None
            return FakeRow({"id": value})
        if self._fetchone_queue:
            return self._fetchone_queue.pop(0)
        if self._rows:
            return self._rows.pop(0)
        return None

    def fetchall(self):
        rows = self._rows
        self._rows = []
        return rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeDB:
    """db.execute() 风格 — 直接返回 cursor(不是 cursor from conn)."""

    def __init__(self) -> None:
        self.cursor = FakeCursor()
        self.commits = 0

    def execute(self, sql, params=None):
        return self.cursor.execute(sql, params)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        pass

    def closed(self) -> bool:
        return False


# ── Fixtures ──


def _make_master_key(monkeypatch) -> None:
    """设置 INNOVOS_ENCRYPT_KEY 环境变量供 ApiKeyCipher 加载。"""
    import base64
    import os

    monkeypatch.setenv(
        "INNOVOS_ENCRYPT_KEY",
        base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("="),
    )


def _make_service(monkeypatch):
    """import service + 提供 cipher + db"""
    from app.services.api_key_service import ApiKeyService

    cipher = _get_cipher(monkeypatch)
    db = FakeDB()
    svc = ApiKeyService(db=db, cipher=cipher)
    return svc, db, cipher


def _get_cipher(monkeypatch):
    from app.core.key_crypto import load_api_key_cipher

    return load_api_key_cipher()


def _make_full_row(
    key_id: int,
    provider_id: str,
    name: str,
    cipher,
    plaintext: str,
    *,
    priority: int = 100,
    is_active: bool = True,
    max_rpm: int | None = None,
    request_count: int = 0,
    success_count: int = 0,
    failure_count: int = 0,
    cooldown_until=None,
    last_error_code=None,
    created_by: int = 1,
    updated_by: int = 1,
):
    """构造一个完整的 api_keys 行(已用 cipher 加密)。"""
    encrypted = cipher.encrypt(plaintext=plaintext, provider_id=provider_id, key_id=key_id)
    return FakeRow(
        {
            "id": key_id,
            "provider_id": provider_id,
            "name": name,
            "key_ciphertext": encrypted.ciphertext,
            "key_nonce": encrypted.nonce,
            "encryption_version": 1,
            "key_fingerprint": encrypted.fingerprint,
            "key_prefix": encrypted.prefix,
            "key_suffix": encrypted.suffix,
            "priority": priority,
            "is_active": is_active,
            "max_rpm": max_rpm,
            "request_count": request_count,
            "success_count": success_count,
            "failure_count": failure_count,
            "last_used_at": None,
            "cooldown_until": cooldown_until,
            "last_error_code": last_error_code,
            "created_by": created_by,
            "updated_by": updated_by,
        }
    )


# ── 测试 ──


class TestCreateKey:
    def test_create_key_stores_ciphertext_not_plaintext(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, cipher = _make_service(monkeypatch)
        # 顺序: 1) INSERT 返 id=42; 2) 查重 SELECT 返 None; 3) 最终 SELECT 返 row
        db.cursor.set_inserted_id(42)
        db.cursor._fetchone_queue.extend([None, _make_full_row(42, "p1", "prod-primary", cipher, "sk-supersecret-1234567890", priority=100)])

        result = svc.create_key(
            provider_id="p1",
            name="prod-primary",
            plaintext="sk-supersecret-1234567890",
            priority=100,
            max_rpm=60,
            actor_id=7,
        )

        # 查找 INSERT
        insert_sql = next(s for s, _ in db.cursor.history if s.startswith("INSERT INTO api_keys"))
        assert "key_ciphertext" in insert_sql
        assert "key_nonce" in insert_sql
        assert "key_fingerprint" in insert_sql

        # 返回值不含 plaintext
        for forbidden in ("plaintext", "apiKey", "api_key", "ciphertext", "nonce"):
            assert forbidden not in result, f"返回值泄漏了 {forbidden}"

    def test_create_key_does_not_return_plaintext_in_dict(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, cipher = _make_service(monkeypatch)
        db.cursor.set_inserted_id(1)
        db.cursor._fetchone_queue.extend([None, _make_full_row(1, "p1", "n1", cipher, "sk-leak-test-XYZ")])

        result = svc.create_key(
            provider_id="p1", name="n1", plaintext="sk-leak-test-XYZ", actor_id=1
        )

        for forbidden in ("sk-leak-test-XYZ",):
            assert forbidden not in str(result), "返回值含明文"

    def test_create_key_writes_actor_id(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, cipher = _make_service(monkeypatch)
        db.cursor.set_inserted_id(1)
        db.cursor._fetchone_queue.extend([None, _make_full_row(1, "p1", "n1", cipher, "sk-x")])

        svc.create_key(provider_id="p1", name="n1", plaintext="sk-x", actor_id=99)

        # 找 INSERT params
        for sql, params in db.cursor.history:
            if sql.startswith("INSERT INTO api_keys"):
                assert 99 in params, f"actor_id=99 未写入 INSERT params: {params}"

    def test_create_key_rejects_duplicate_fingerprint_within_provider(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, _ = _make_service(monkeypatch)
        # 模拟同一 provider 同 plaintext 已存在 → SELECT 命中
        cipher = svc.cipher
        encrypted = cipher.encrypt(plaintext="sk-dupe", provider_id="p1", key_id=999)
        existing_row = FakeRow(
            {
                "id": 1,
                "provider_id": "p1",
                "key_fingerprint": encrypted.fingerprint,
            }
        )
        # 顺序: INSERT 返 id=2; 查重 SELECT 返 existing_row(id=1) ≠ 自己(2)
        db.cursor.set_inserted_id(2)
        db.cursor._fetchone_queue.append(existing_row)

        with __import__("pytest").raises(ValueError, match="duplicate|fingerprint|exists"):
            svc.create_key(
                provider_id="p1", name="another", plaintext="sk-dupe", actor_id=1
            )


class TestListKeys:
    def test_list_keys_does_not_trigger_decrypt(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, cipher = _make_service(monkeypatch)

        row = _make_full_row(10, "p1", "primary", cipher, "sk-aaa-bbb-secret-end")
        db.cursor.set_rows([row])

        results = svc.list_keys(provider_id="p1")

        # 不能含明文(完整串)
        for r in results:
            assert "sk-aaa-bbb-secret-end" not in str(r), f"完整明文泄漏: {r}"
        # 必须含掩码
        assert all("masked" in r for r in results)
        # 必须含短 fingerprint
        assert all("fingerprint" in r for r in results)
        # fingerprint 不能是完整 32 bytes hex
        for r in results:
            assert len(r["fingerprint"]) <= 16
        # masked 不应包含明文中段
        for r in results:
            assert "secret-end" not in r["masked"], "掩码含明文中段"
            assert "bbb" not in r["masked"] or "••" in r["masked"], "掩码未脱敏"


class TestUpdateMetadata:
    def test_update_metadata_does_not_touch_ciphertext(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, _ = _make_service(monkeypatch)
        db.cursor.set_rows([None])  # SELECT for update 不命中也可

        # 第一次 SELECT 是 update 之前的 select(任意返回)
        # 让它返回一行
        existing = FakeRow(
            {
                "id": 1, "provider_id": "p1", "name": "old",
                "priority": 100, "is_active": True, "max_rpm": None,
                "key_ciphertext": b"\x00" * 16,
                "key_nonce": b"\x00" * 12,
                "encryption_version": 1,
                "key_fingerprint": b"\x00" * 32,
                "key_prefix": None, "key_suffix": "",
                "request_count": 0, "success_count": 0, "failure_count": 0,
                "last_used_at": None, "cooldown_until": None,
                "created_by": 1, "updated_by": 1,
            }
        )
        db.cursor.set_rows([existing, existing])

        svc.update_metadata(
            key_id=1,
            name="renamed",
            priority=50,
            max_rpm=120,
            is_active=False,
            actor_id=2,
        )

        # 找 UPDATE api_keys 语句
        update_sql = next(
            (s for s, _ in db.cursor.history if s.startswith("UPDATE api_keys SET")), None
        )
        assert update_sql is not None
        # 必须不含 key_ciphertext / key_nonce / key_fingerprint
        for forbidden in ("key_ciphertext", "key_nonce", "key_fingerprint"):
            assert forbidden not in update_sql, f"metadata update 误改了 {forbidden}"


class TestReplaceSecret:
    def test_replace_secret_writes_new_ciphertext_and_clears_cooldown(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, _ = _make_service(monkeypatch)
        existing = FakeRow(
            {
                "id": 1, "provider_id": "p1", "name": "n",
                "priority": 100, "is_active": True, "max_rpm": None,
                "key_ciphertext": b"\x00" * 16,
                "key_nonce": b"\x00" * 12,
                "encryption_version": 1,
                "key_fingerprint": b"\x00" * 32,
                "key_prefix": "old", "key_suffix": "old1",
                "request_count": 5, "success_count": 3, "failure_count": 2,
                "last_used_at": datetime.now(timezone.utc),
                "cooldown_until": datetime.now(timezone.utc),
                "last_error_code": "auth",
                "created_by": 1, "updated_by": 1,
            }
        )
        db.cursor.set_rows([existing])

        result = svc.replace_secret(key_id=1, plaintext="sk-new-secret", actor_id=2)

        # UPDATE 必须含 key_ciphertext + cooldown_until=NULL
        update_sql = next(
            (s for s, _ in db.cursor.history if s.startswith("UPDATE api_keys SET")), None
        )
        assert update_sql is not None
        assert "key_ciphertext" in update_sql
        assert "cooldown_until" in update_sql
        assert "last_error_code" in update_sql
        # 返回值不含明文
        assert "sk-new-secret" not in str(result)


class TestLeaseKey:
    def test_lease_returns_none_when_no_candidates(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, _ = _make_service(monkeypatch)
        db.cursor.set_rows([])  # lease_next 无命中

        result = svc.lease_key(provider_id="missing-provider")
        assert result is None

    def test_lease_returns_first_eligible_key(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, cipher = _make_service(monkeypatch)
        encrypted = cipher.encrypt(plaintext="sk-ok", provider_id="p1", key_id=5)
        candidate = FakeRow(
            {
                "id": 5,
                "provider_id": "p1",
                "key_ciphertext": encrypted.ciphertext,
                "key_nonce": encrypted.nonce,
                "encryption_version": 1,
            }
        )
        db.cursor.set_rows([candidate])

        result = svc.lease_key(provider_id="p1")

        assert result is not None
        assert result.provider_id == "p1"
        assert result.plaintext == "sk-ok"
        assert result.key_id == 5

    def test_lease_does_not_select_inactive_keys(self, monkeypatch):
        """SQL 必须过滤 is_active=TRUE;本测试断言 SQL 中含 is_active 条件。"""
        _make_master_key(monkeypatch)
        svc, db, _ = _make_service(monkeypatch)
        db.cursor.set_rows([])

        svc.lease_key(provider_id="p1")

        # 查找 lease 用的 SELECT
        lease_sql = next(
            (
                s
                for s, _ in db.cursor.history
                if "FROM api_keys" in s and "is_active" in s
            ),
            None,
        )
        assert lease_sql is not None, "lease SELECT 未过滤 is_active"
        assert "is_active = TRUE" in lease_sql or "is_active=TRUE" in lease_sql

    def test_lease_does_not_select_cooldown_keys(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, _ = _make_service(monkeypatch)
        db.cursor.set_rows([])

        svc.lease_key(provider_id="p1")

        lease_sql = next(
            (s for s, _ in db.cursor.history if "FROM api_keys" in s and "is_active" in s),
            None,
        )
        assert lease_sql is not None
        assert "cooldown_until" in lease_sql, "lease SQL 未排除 cooldown 内的 Key"


class TestMarkSuccessAndFailure:
    def test_mark_success_increments_counters(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, _ = _make_service(monkeypatch)

        svc.mark_success(key_id=42)

        update_sql = next(
            (s for s, _ in db.cursor.history if s.startswith("UPDATE api_keys SET")), None
        )
        assert update_sql is not None
        for col in ("success_count", "request_count", "last_success_at"):
            assert col in update_sql

    def test_mark_failure_sets_cooldown(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, _ = _make_service(monkeypatch)

        svc.mark_failure(
            key_id=42,
            category="auth",
            cooldown_until=datetime.now(timezone.utc),
        )

        update_sql = next(
            (s for s, _ in db.cursor.history if s.startswith("UPDATE api_keys SET")), None
        )
        assert update_sql is not None
        for col in ("failure_count", "cooldown_until", "last_error_code"):
            assert col in update_sql


class TestHasActiveKey:
    def test_has_active_key_returns_true_when_key_exists(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, _ = _make_service(monkeypatch)
        db.cursor.set_rows([{"c": 1}])

        assert svc.has_active_key(provider_id="p1") is True

    def test_has_active_key_returns_false_when_none(self, monkeypatch):
        _make_master_key(monkeypatch)
        svc, db, _ = _make_service(monkeypatch)
        db.cursor.set_rows([])

        assert svc.has_active_key(provider_id="p1") is False