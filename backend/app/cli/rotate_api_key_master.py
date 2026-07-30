"""
主密钥离线轮换 CLI。

用途:将数据库 api_keys 表中所有用旧主密钥加密的 Key,重加密为新主密钥。
- 不修改应用配置
- 不影响运行时(运行时不感知)
- 通过 PostgreSQL advisory lock 防并发
- 支持 --dry-run 预演

用法:
    # 1. dry-run 预演
    python -m app.cli.rotate_api_key_master --dry-run

    # 2. 正式轮换
    INNOVOS_OLD_ENCRYPT_KEY=old-base64-32b \\
    INNOVOS_ENCRYPT_KEY=new-base64-32b \\
    python -m app.cli.rotate_api_key_master --apply --batch-size 100

    # 3. 切换应用实例(env → 移除 OLD,只保留 NEW),重启后端
"""

from __future__ import annotations

import argparse
import base64
import logging
import os
import sys
from dataclasses import dataclass

from app.core.key_crypto import ApiKeyCipher, ApiKeyCryptoError

logger = logging.getLogger(__name__)


# PostgreSQL advisory lock key(任意唯一 64-bit 整数)
# 在同一 DB 上只能有一个轮换任务运行
ROTATE_LOCK_KEY = 8101141317


@dataclass
class RotationReport:
    scanned_count: int = 0
    rotated_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    dry_run: bool = False
    duration_seconds: float = 0.0


def _decode_master_key(env_var: str) -> bytes:
    """从环境变量读取 base64url 编码的 32-byte 主密钥,缺失或错误时抛错。"""
    raw = os.environ.get(env_var)
    if not raw:
        raise RuntimeError(
            f"{env_var} is required. "
            "Generate with: python -c \"import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\""
        )
    pad = "=" * (-len(raw) % 4)
    try:
        return base64.urlsafe_b64decode(raw + pad)
    except Exception as exc:
        raise RuntimeError(
            f"{env_var} is not valid base64url: {type(exc).__name__}"
        ) from exc


def _build_cipher(env_var: str) -> ApiKeyCipher:
    return ApiKeyCipher(master_key=_decode_master_key(env_var))


def rotate(
    *,
    old_key_env: str,
    new_key_env: str,
    batch_size: int = 100,
    dry_run: bool,
    db: object,
) -> RotationReport:
    """主密钥轮换入口。可被 Python 代码调用(测试用),也可被 CLI 调用。

    行为:
    1. 校验两个主密钥都存在且合法
    2. SELECT id, key_ciphertext, key_nonce, encryption_version, provider_id
       逐批分页,直到本批返回行数 < batch_size 为止
    3. 逐行用旧 cipher 解密 → 新 cipher 重加密 → UPDATE api_keys SET ...
    4. 整个过程包裹在 pg_advisory_lock / pg_advisory_unlock 之间
    """
    import time

    report = RotationReport(dry_run=dry_run)
    start = time.time()

    # 校验主密钥
    old_cipher = _build_cipher(old_key_env)
    new_cipher = _build_cipher(new_key_env)

    # 获取 advisory lock
    db.execute("SELECT pg_advisory_lock(?)", (ROTATE_LOCK_KEY,))
    logger.info("Acquired PostgreSQL advisory lock (key=%s)", ROTATE_LOCK_KEY)
    try:
        # 用 cursor 跟踪,确保每次 fetchall 返回新批
        cursor = db.execute(
            "SELECT id, key_ciphertext, key_nonce, encryption_version, provider_id "
            "FROM api_keys ORDER BY id LIMIT ?",
            (batch_size,),
        )
        while True:
            rows = cursor.fetchall()
            if not rows:
                break
            for row in rows:
                report.scanned_count += 1
                key_id, old_ct, old_nonce, old_version, provider_id = (
                    row[0], row[1], row[2], row[3], row[4]
                )
                try:
                    plaintext = old_cipher.decrypt(
                        ciphertext=old_ct,
                        nonce=old_nonce,
                        encryption_version=old_version,
                        provider_id=provider_id,
                        key_id=key_id,
                    )
                except ApiKeyCryptoError as exc:
                    logger.warning(
                        "Failed to decrypt key id=%s provider=%s: %s",
                        key_id, provider_id, exc,
                    )
                    report.failed_count += 1
                    continue

                if dry_run:
                    report.skipped_count += 1
                    continue

                encrypted = new_cipher.encrypt(
                    plaintext=plaintext,
                    provider_id=provider_id,
                    key_id=key_id,
                )
                db.execute(
                    "UPDATE api_keys SET key_ciphertext=?, key_nonce=?, "
                    "encryption_version=?, key_fingerprint=?, key_prefix=?, key_suffix=?, "
                    "updated_at=NOW() WHERE id=?",
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
                report.rotated_count += 1
            db.commit()
            # 本批不足 batch_size → 已读完,终止
            if len(rows) < batch_size:
                break
            # 否则 fetch 下一批
            cursor = db.execute(
                "SELECT id, key_ciphertext, key_nonce, encryption_version, provider_id "
                "FROM api_keys ORDER BY id LIMIT ?",
                (batch_size,),
            )
    finally:
        db.execute("SELECT pg_advisory_unlock(?)", (ROTATE_LOCK_KEY,))
        logger.info("Released PostgreSQL advisory lock")
        db.commit()

    report.duration_seconds = time.time() - start
    return report


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rotate master encryption key for all API keys in the database. "
            "WARNING: Requires advisory lock and rewrites all key_ciphertext rows."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rewrite rows. Default is dry-run (no changes).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="(default) Report scanned/failed counts but do NOT modify DB.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Rows per batch (default 100).",
    )
    parser.add_argument(
        "--old-key-env",
        default="INNOVOS_OLD_ENCRYPT_KEY",
        help="Env var name holding OLD master key (base64url 32 bytes).",
    )
    parser.add_argument(
        "--new-key-env",
        default="INNOVOS_ENCRYPT_KEY",
        help="Env var name holding NEW master key (base64url 32 bytes).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_argparser().parse_args(argv)

    if args.apply and args.dry_run:
        print("ERROR: --apply and --dry-run are mutually exclusive", file=sys.stderr)
        return 2

    dry_run = not args.apply  # 默认 dry-run

    # 真实环境:从 app.database.get_db() 获取连接
    from app.database import get_db

    db = get_db()
    try:
        report = rotate(
            old_key_env=args.old_key_env,
            new_key_env=args.new_key_env,
            batch_size=args.batch_size,
            dry_run=dry_run,
            db=db,
        )
    finally:
        if hasattr(db, "close"):
            db.close()

    print("--- Rotation report ---")
    print(f"  Mode:              {'DRY-RUN' if report.dry_run else 'APPLIED'}")
    print(f"  Scanned:           {report.scanned_count}")
    print(f"  Rotated:           {report.rotated_count}")
    print(f"  Failed (decrypt): {report.failed_count}")
    print(f"  Skipped (dry-run): {report.skipped_count}")
    print(f"  Duration:          {report.duration_seconds:.2f}s")
    if report.failed_count > 0:
        print(
            f"\nWARNING: {report.failed_count} rows failed to decrypt with OLD key. "
            "These rows may already be encrypted with a different key. "
            "Verify the master key lineage before proceeding."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())