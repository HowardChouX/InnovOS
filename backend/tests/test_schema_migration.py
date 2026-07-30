"""
TDD 测试: api_keys / model_providers 新 schema

覆盖:
1. init_api_keys 新 DDL 包含 AES-GCM 密文列 + 12字节 nonce + 32字节指纹
2. init_api_keys 含租约/统计/cooldown/审计列
3. init_api_keys 含索引 ix_api_keys_selection
4. init_api_keys 显式 DROP 旧 plaintext 列
5. init_model_providers 含 created_by/updated_by 审计列
6. init_model_providers 显式 DROP 旧 api_key_encrypted/current_rpm 等列
7. 启动时 TRUNCATE 两张表
"""

from __future__ import annotations


class _RecordingCursor:
    """Mock cursor that records SQL and supports chain .fetchone() / .fetchall()."""

    def __init__(self) -> None:
        self.recorded_sql: list[str] = []
        self._fetchone_queue: list[object] = []

    def execute(self, sql, params=None):
        self.recorded_sql.append(sql)
        return self

    def fetchone(self):
        if self._fetchone_queue:
            return self._fetchone_queue.pop(0)
        return None

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestApiKeysSchema:
    def _call(self, init_fn) -> _RecordingCursor:
        cur = _RecordingCursor()
        init_fn(cur)
        return cur

    def test_init_api_keys_ddl_contains_encrypted_columns(self):
        from app.tables.pg_schema import init_api_keys

        cur = self._call(init_api_keys)
        all_ddl = "\n".join(cur.recorded_sql)
        assert "key_ciphertext" in all_ddl
        assert "key_nonce" in all_ddl
        assert "key_fingerprint" in all_ddl
        assert "encryption_version" in all_ddl

    def test_init_api_keys_ddl_nonce_is_12_bytes_with_constraint(self):
        from app.tables.pg_schema import init_api_keys

        cur = self._call(init_api_keys)
        all_ddl = "\n".join(cur.recorded_sql)
        assert "BYTEA" in all_ddl
        assert "OCTET_LENGTH" in all_ddl, "缺少 nonce 长度 CHECK 约束"

    def test_init_api_keys_ddl_contains_lease_and_cooldown(self):
        from app.tables.pg_schema import init_api_keys

        cur = self._call(init_api_keys)
        all_ddl = "\n".join(cur.recorded_sql)
        for col in (
            "lease_count",
            "request_count",
            "success_count",
            "failure_count",
            "cooldown_until",
            "last_error_code",
        ):
            assert col in all_ddl, f"缺少列 {col}"

    def test_init_api_keys_ddl_contains_audit_columns(self):
        from app.tables.pg_schema import init_api_keys

        cur = self._call(init_api_keys)
        all_ddl = "\n".join(cur.recorded_sql)
        assert "created_by" in all_ddl
        assert "updated_by" in all_ddl

    def test_init_api_keys_ddl_contains_selection_index(self):
        from app.tables.pg_schema import init_api_keys

        cur = self._call(init_api_keys)
        all_ddl = "\n".join(cur.recorded_sql)
        assert "ix_api_keys_selection" in all_ddl, "缺少选择索引"
        assert "priority" in all_ddl

    def test_init_api_keys_ddl_drops_legacy_columns(self):
        from app.tables.pg_schema import init_api_keys

        cur = self._call(init_api_keys)
        all_ddl = "\n".join(cur.recorded_sql)
        assert "DROP COLUMN IF EXISTS api_key" in all_ddl, "未移除旧明文列 api_key"
        assert "DROP COLUMN IF EXISTS current_rpm" in all_ddl, "未移除 current_rpm"


class TestModelProvidersSchema:
    def _call(self, init_fn) -> _RecordingCursor:
        cur = _RecordingCursor()
        init_fn(cur)
        return cur

    def test_init_model_providers_ddl_contains_audit_columns(self):
        from app.tables.pg_schema import init_model_providers

        cur = self._call(init_model_providers)
        all_ddl = "\n".join(cur.recorded_sql)
        assert "created_by" in all_ddl
        assert "updated_by" in all_ddl

    def test_init_model_providers_ddl_drops_legacy_columns(self):
        from app.tables.pg_schema import init_model_providers

        cur = self._call(init_model_providers)
        all_ddl = "\n".join(cur.recorded_sql)
        for col in (
            "api_key_encrypted",
            "current_rpm",
            "request_count",
            "last_used_at",
            "last_reset_at",
        ):
            assert f"DROP COLUMN IF EXISTS {col}" in all_ddl, f"未移除 model_providers.{col}"

    def test_init_model_providers_ddl_creates_enabled_index(self):
        from app.tables.pg_schema import init_model_providers

        cur = self._call(init_model_providers)
        all_ddl = "\n".join(cur.recorded_sql)
        assert "ix_model_providers_enabled" in all_ddl, "缺少启用状态部分索引"


class TestStartupTruncatesLegacyData:
    def test_init_all_tables_skips_truncate_by_default(self, monkeypatch):
        """默认启动不应 TRUNCATE(防止生产数据被静默擦除)。"""
        from app.tables.pg_schema import init_all_tables

        cur = _RecordingCursor()
        monkeypatch.delenv("INNOVOS_RESET_DATA", raising=False)
        init_all_tables(cur)
        all_sql = "\n".join(cur.recorded_sql)
        assert "TRUNCATE TABLE model_providers" not in all_sql
        assert "TRUNCATE TABLE api_keys" not in all_sql

    def test_init_all_tables_truncates_when_reset_env_set(self, monkeypatch):
        """设置 INNOVOS_RESET_DATA=1 时才 TRUNCATE(用于首次部署)。"""
        from app.tables.pg_schema import init_all_tables

        cur = _RecordingCursor()
        monkeypatch.setenv("INNOVOS_RESET_DATA", "1")
        init_all_tables(cur)
        all_sql = "\n".join(cur.recorded_sql)
        assert "TRUNCATE TABLE model_providers" in all_sql
        assert "TRUNCATE TABLE api_keys" in all_sql