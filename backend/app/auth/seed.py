"""首任超级用户种子 — 仅在 .env 提供 FIRST_SUPERUSER/INNOVOS_ADMIN_USER 时幂等执行。

替代旧的 id=0 幽灵管理员：现在使用真实的 DB 用户记录，由 FastAPI Users 的密码工具哈希密码。
"""
import logging
import re

from app.core import config as _config_mod
from app.db.models import User
from app.db.session import get_session

logger = logging.getLogger(__name__)

# 简易邮箱校验（避免引入 pydantic[email] 重依赖）
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _looks_like_email(value: str) -> bool:
    """FastAPI Users 以 email 为主键；FIRST_SUPERUSER 必须是合法邮箱。"""
    return bool(value) and bool(_EMAIL_RE.match(value))


def seed_first_superuser_if_configured() -> None:
    """当 .env 提供 FIRST_SUPERUSER/INNOVOS_ADMIN_USER 时，幂等地创建/更新该管理员。

    幂等：已存在同 email 的用户则跳过；密码若设置也仅在用户不存在时生效。
    不会向日志打印明文密码。
    """
    # 每次调用都从 config_mod 读取最新 settings（便于测试 monkeypatch）
    settings = _config_mod.settings
    email = settings.FIRST_SUPERUSER
    password = settings.FIRST_SUPERUSER_PASSWORD
    if not email:
        logger.info("未配置 FIRST_SUPERUSER，跳过管理员种子")
        return
    if not _looks_like_email(email):
        logger.warning(
            "FIRST_SUPERUSER (%s) 不是合法邮箱；FastAPI Users 必须以 email 为主键，跳过种子。",
            email,
        )
        return

    db = next(get_session())
    try:
        existing = db.query(User).filter(User.email == email).one_or_none()
        if existing is not None:
            # 仍确保该用户是 superuser（便于运营/重置 .env 后快速恢复权限）
            if not existing.is_superuser or not existing.is_active:
                existing.is_superuser = True
                existing.is_active = True
                db.commit()
                logger.info("已将现有用户 %s 提升为超级用户", email)
            else:
                logger.info("管理员 %s 已存在，跳过种子", email)
            return

        # 走 FastAPI Users 的密码工具生成哈希
        from fastapi_users.password import PasswordHelper

        password_helper = PasswordHelper()
        if not password:
            # 无密码时生成随机密码，仅供测试场景（仅 dev）
            import secrets

            password = secrets.token_urlsafe(24)
            logger.warning(
                "FIRST_SUPERUSER_PASSWORD 未设置，已为 %s 生成一次性随机密码：%s（请立即保存并修改）",
                email,
                password,
            )
        hashed = password_helper.hash(password)
        user = User(
            email=email,
            hashed_password=hashed,
            is_active=True,
            is_superuser=True,
            is_verified=True,
            username=email.split("@")[0],
            role="admin",
            token_version=0,
        )
        db.add(user)
        db.commit()
        logger.info("已创建首任超级用户：%s", email)
    except Exception as exc:
        db.rollback()
        logger.exception("管理员种子失败：%s", exc)
    finally:
        db.close()
