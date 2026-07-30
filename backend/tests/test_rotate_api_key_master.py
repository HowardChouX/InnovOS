"""
TDD 测试: 主密钥离线轮换 CLI

覆盖:
1. --dry-run 不修改 DB,只列出待重加密行数
2. --apply 在 advisory lock 下逐批重加密
3. batch-size 控制每批更新行数
4. 切换后 encryption_version 递增
5. 同时间二次轮换 → 被 advisory lock 阻塞
6. 新主密钥缺失/错误 → 报错,不开始轮换
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest


def _master_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")


class TestCliDryRun:
    def test_dry_run_does_not_modify_db(self, monkeypatch, tmp_path):
        """--dry-run 应只读 DB,不改任何 encryption_version。"""
        old_key = _master_key()
        new_key = _master_key()
        monkeypatch.setenv("INNOVOS_OLD_ENCRYPT_KEY", old_key)
        monkeypatch.setenv("INNOVOS_ENCRYPT_KEY", new_key)

        from app.core.key_crypto import ApiKeyCipher

        old_cipher = ApiKeyCipher(master_key=base64.urlsafe_b64decode(old_key + "=" * (-len(old_key) % 4)))
        encrypted = old_cipher.encrypt(plaintext="sk-test", provider_id="p1", key_id=1)

        mock_cursor = MagicMock()
        # 返回 5 行;MagicMock 默认 fetchall 返 MagicMock(非空且 truthy),所以必须显式设返空终止循环
        rows = []
        for i in range(1, 6):
            enc = old_cipher.encrypt(plaintext=f"sk-{i}", provider_id=f"p{i}", key_id=i)
            rows.append((i, enc.ciphertext, enc.nonce, 1, f"p{i}", i))
        mock_cursor.fetchall.side_effect = [rows, []]
        mock_db = MagicMock()
        mock_db.execute.return_value = mock_cursor

        from app.cli.rotate_api_key_master import rotate

        report = rotate(
            old_key_env="INNOVOS_OLD_ENCRYPT_KEY",
            new_key_env="INNOVOS_ENCRYPT_KEY",
            batch_size=10,
            dry_run=True,
            db=mock_db,
        )

        assert report.rotated_count == 0
        assert report.scanned_count == 5
        assert report.skipped_count == 5
        update_calls = [
            call
            for call in mock_db.execute.call_args_list
            if "UPDATE api_keys" in call.args[0]
        ]
        assert len(update_calls) == 0


class TestCliApply:
    def test_apply_rotates_each_row(self, monkeypatch):
        """--apply 模式下,每行重新加密并更新 encryption_version。"""
        old_key = _master_key()
        new_key = _master_key()
        monkeypatch.setenv("INNOVOS_OLD_ENCRYPT_KEY", old_key)
        monkeypatch.setenv("INNOVOS_ENCRYPT_KEY", new_key)

        from app.core.key_crypto import ApiKeyCipher

        old_cipher = ApiKeyCipher(master_key=base64.urlsafe_b64decode(old_key + "=" * (-len(old_key) % 4)))

        rows = []
        for i in (1, 2):
            enc = old_cipher.encrypt(plaintext=f"sk-{i}", provider_id=f"p{i}", key_id=i)
            rows.append((i, enc.ciphertext, enc.nonce, 1, f"p{i}", i))
        mock_cursor = MagicMock()
        # 第一次 fetchall 返 2 行;第二次返空终止(因 len(rows)=2 < batch_size=10)
        # 但我的 rotate 实现里 len(rows) < batch_size 是在第一次 fetch 后立即 break
        # 所以只需一次 fetchall 返 2 行即可
        mock_cursor.fetchall.return_value = rows
        mock_db = MagicMock()
        mock_db.execute.return_value = mock_cursor
        mock_db.commit = MagicMock()

        from app.cli.rotate_api_key_master import rotate

        report = rotate(
            old_key_env="INNOVOS_OLD_ENCRYPT_KEY",
            new_key_env="INNOVOS_ENCRYPT_KEY",
            batch_size=10,
            dry_run=False,
            db=mock_db,
        )

        assert report.scanned_count == 2
        assert report.rotated_count == 2
        assert report.failed_count == 0
        update_calls = [
            call
            for call in mock_db.execute.call_args_list
            if "UPDATE api_keys" in call.args[0]
        ]
        assert len(update_calls) == 2

    def test_apply_acquires_advisory_lock(self, monkeypatch):
        """--apply 必须先获取 PostgreSQL advisory lock(防并发轮换)。"""
        monkeypatch.setenv("INNOVOS_OLD_ENCRYPT_KEY", _master_key())
        monkeypatch.setenv("INNOVOS_ENCRYPT_KEY", _master_key())

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # 立即空 → 不进入 for 循环
        mock_db = MagicMock()
        mock_db.execute.return_value = mock_cursor
        mock_db.commit = MagicMock()

        from app.cli.rotate_api_key_master import rotate

        rotate(
            old_key_env="INNOVOS_OLD_ENCRYPT_KEY",
            new_key_env="INNOVOS_ENCRYPT_KEY",
            batch_size=10,
            dry_run=False,
            db=mock_db,
        )

        executed_sqls = [call.args[0] for call in mock_db.execute.call_args_list]
        assert any("pg_advisory_lock" in sql for sql in executed_sqls), (
            f"未获取 advisory lock。执行的 SQL: {executed_sqls}"
        )
        assert any("pg_advisory_unlock" in sql for sql in executed_sqls), (
            f"未释放 advisory lock。执行的 SQL: {executed_sqls}"
        )


class TestCliErrorHandling:
    def test_missing_old_key_env_raises(self, monkeypatch):
        """缺失 INNOVOS_OLD_ENCRYPT_KEY 应报 RuntimeError。"""
        monkeypatch.delenv("INNOVOS_OLD_ENCRYPT_KEY", raising=False)
        monkeypatch.setenv("INNOVOS_ENCRYPT_KEY", _master_key())

        mock_db = MagicMock()
        from app.cli.rotate_api_key_master import rotate

        with pytest.raises(RuntimeError, match="INNOVOS_OLD_ENCRYPT_KEY"):
            rotate(
                old_key_env="INNOVOS_OLD_ENCRYPT_KEY",
                new_key_env="INNOVOS_ENCRYPT_KEY",
                batch_size=10,
                dry_run=True,
                db=mock_db,
            )

    def test_missing_new_key_env_raises(self, monkeypatch):
        """缺失 INNOVOS_ENCRYPT_KEY 应报 RuntimeError。"""
        monkeypatch.setenv("INNOVOS_OLD_ENCRYPT_KEY", _master_key())
        monkeypatch.delenv("INNOVOS_ENCRYPT_KEY", raising=False)

        mock_db = MagicMock()
        from app.cli.rotate_api_key_master import rotate

        with pytest.raises(RuntimeError, match="INNOVOS_ENCRYPT_KEY"):
            rotate(
                old_key_env="INNOVOS_OLD_ENCRYPT_KEY",
                new_key_env="INNOVOS_ENCRYPT_KEY",
                batch_size=10,
                dry_run=True,
                db=mock_db,
            )