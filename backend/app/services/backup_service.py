"""
自动数据库快照备份服务 — 每日定时执行 pg_dump。

集成在主程序中，启动时注册定时任务：
- 默认每日 03:00 执行数据库快照
- 保留最近 30 天的备份，自动清理过期

快照文件存储结构：
  BACKUP_DIR/
    innovos_20260623_030001.sql.gz   — 数据库快照
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ── 默认配置（可通过环境变量覆盖） ──────────────────────────
DEFAULT_BACKUP_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "backups")
)
DEFAULT_BACKUP_TIME = "03:00"  # 24h 格式 HH:MM
DEFAULT_RETENTION_DAYS = 30

class BackupService:
    """每日定时快照备份服务。"""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._enabled = True
        self._backup_dir = os.getenv("BACKUP_DIR", DEFAULT_BACKUP_DIR)
        self._backup_time = os.getenv("BACKUP_TIME", DEFAULT_BACKUP_TIME)
        self._retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS)))

        # 从环境变量取 DATABASE_URL
        self._database_url = os.getenv("DATABASE_URL", "")

        # 只对 development 环境启动时立即打一次快照
        self._env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development"))

    # ── 公开接口 ──────────────────────────────────────────

    async def start(self) -> None:
        """在后台启动定时备份循环。"""
        if not self._enabled:
            logger.info("备份服务已禁用 (BACKUP_ENABLED=false)")
            return

        # 确保备份目录存在
        os.makedirs(self._backup_dir, exist_ok=True)
        logger.info("备份目录: %s", self._backup_dir)

        # 开发环境：启动时立即打一次快照
        if self._env == "development":
            logger.info("开发环境：启动时立即执行快照备份...")
            await self._run_backup()

        # 注册每日定时任务
        self._task = asyncio.create_task(self._backup_loop())
        logger.info(
            "定时备份已注册，每日 %s 执行，保留 %d 天",
            self._backup_time,
            self._retention_days,
        )

    async def stop(self) -> None:
        """停止定时备份循环。"""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("定时备份已停止")

    async def run_now(self) -> str | None:
        """立即执行一次快照备份（手动触发）。返回快照路径。"""
        return await self._run_backup()

    # ── 内部实现 ──────────────────────────────────────────

    async def _backup_loop(self) -> None:
        """定时循环：计算到下次备份时间的秒数 → sleep → 执行 → 继续。"""
        while True:
            now = datetime.now(timezone.utc)
            next_run = self._next_run_time(now)

            sleep_seconds = (next_run - now).total_seconds()
            logger.debug("下次备份时间: %s (%.0f 秒后)", next_run, sleep_seconds)

            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                logger.info("备份循环已取消")
                return

            try:
                await self._run_backup()
            except Exception:
                logger.exception("定时备份执行失败")

    def _next_run_time(self, now: datetime) -> datetime:
        """计算下一个备份时间点。"""
        hour, minute = self._backup_time.split(":")
        candidate = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)

        if candidate <= now:
            candidate += timedelta(days=1)

        return candidate

    async def _run_backup(self) -> str | None:
        """执行一次完整快照备份。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_path = os.path.join(self._backup_dir, f"innovos_{timestamp}.sql.gz")

        logger.info("开始快照备份: innovos_%s", timestamp)

        # 1. 数据库快照
        db_url = self._database_url
        if not db_url:
            # 尝试从 settings 获取
            try:
                from app.core.config import settings

                db_url = settings.DATABASE_URL or ""
            except Exception:
                pass

        if not db_url:
            logger.warning("DATABASE_URL 未配置，跳过数据库备份")
        else:
            try:
                await asyncio.to_thread(self._pg_dump, db_url, db_path)
                size = self._human_size(os.path.getsize(db_path)) if os.path.exists(db_path) else "0B"
                logger.info("数据库快照完成: %s (%s)", db_path, size)
            except Exception:
                logger.exception("数据库快照失败")

        # 2. 清理过期备份
        await asyncio.to_thread(self._cleanup_old_backups)

        return db_path if os.path.exists(db_path) else None

    @staticmethod
    def _pg_dump(db_url: str, output_path: str) -> None:
        """执行 pg_dump 并压缩。"""
        # SQLAlchemy URL ('postgresql+psycopg2://...?host=/tmp') 转 libpq DSN，
        # 否则 pg_dump 不认 '+psycopg2' 前缀和 query-string 字段。
        from app.database import _build_pg_dsn

        dsn = _build_pg_dsn(db_url)
        result = subprocess.run(
            ["pg_dump", dsn],
            capture_output=True,
            timeout=300,  # 5 分钟超时
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"pg_dump 失败 (exit={result.returncode}): {stderr}")

        # gzip 压缩
        import gzip

        with gzip.open(output_path, "wb") as f:
            f.write(result.stdout)

    def _cleanup_old_backups(self) -> None:
        """删除超过保留天数的旧备份文件。"""
        if not os.path.isdir(self._backup_dir):
            return

        now = datetime.now()
        cutoff = now - timedelta(days=self._retention_days)

        removed = 0
        for fname in os.listdir(self._backup_dir):
            # 匹配 innovos_YYYYMMDD_*.sql.gz
            if not fname.startswith("innovos_"):
                continue

            fpath = os.path.join(self._backup_dir, fname)
            if not os.path.isfile(fpath):
                continue

            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime < cutoff:
                os.remove(fpath)
                removed += 1

        if removed:
            logger.info("清理过期备份: %d 个文件", removed)

    @staticmethod
    def _human_size(bytes_: int) -> str:
        """友好显示文件大小。"""
        size = float(bytes_)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


# ── 全局单例 ──────────────────────────────────────────────
backup_service = BackupService()
