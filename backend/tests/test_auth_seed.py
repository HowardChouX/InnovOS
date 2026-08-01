"""首任超级用户种子测试。"""
import os
import tempfile
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.seed import seed_first_superuser_if_configured
from app.db.base import Base
from app.db.models import User


@pytest.fixture
def isolated_db(monkeypatch):
    """独立 SQLite 文件 + 隔离 settings。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    url = f"sqlite:///{tmp.name}"

    # 替换 settings
    from app.core import config as config_mod
    from app.core.config import Settings

    test_settings = Settings(
        FIRST_SUPERUSER="seed-admin@example.com",
        FIRST_SUPERUSER_PASSWORD="StrongPass123",
        DATABASE_URL=url,
    )
    monkeypatch.setattr(config_mod, "settings", test_settings)

    # 替换 ORM engine + factory
    from app.db import session as session_mod

    test_engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(session_mod, "_engine", test_engine)
    monkeypatch.setattr(session_mod, "_SessionLocal", TestSession)

    yield test_engine, TestSession, test_settings

    os.unlink(tmp.name)


class TestSeed:
    def test_creates_superuser(self, isolated_db):
        _, Session, _ = isolated_db
        seed_first_superuser_if_configured()
        with Session() as s:
            u = s.query(User).filter(User.email == "seed-admin@example.com").one()
            assert u.is_superuser is True
            assert u.is_active is True
            assert u.role == "admin"
            assert u.hashed_password != "StrongPass123"  # 已哈希
            assert u.hashed_password.startswith(("$argon2", "$2", "!"))  # pwdlib/argon2/bcrypt 之一

    def test_idempotent(self, isolated_db):
        _, Session, _ = isolated_db
        seed_first_superuser_if_configured()
        seed_first_superuser_if_configured()
        with Session() as s:
            n = s.query(User).filter(User.email == "seed-admin@example.com").count()
            assert n == 1, "重复调用应保持单条"

    def test_promotes_existing_user(self, isolated_db):
        """已存在的同 email 用户若不是 superuser，应被提升。"""
        _, Session, _ = isolated_db
        with Session() as s:
            existing = User(
                email="seed-admin@example.com",
                phone="13800000004",
                hashed_password="$argon2id$dummy",
                is_active=True,
                is_superuser=False,
                is_verified=True,
            )
            s.add(existing)
            s.commit()

        seed_first_superuser_if_configured()
        with Session() as s:
            u = s.query(User).filter(User.email == "seed-admin@example.com").one()
            assert u.is_superuser is True

    def test_no_config_skips(self, isolated_db, monkeypatch):
        """未配置 FIRST_SUPERUSER 时跳过。"""
        from app.core import config as config_mod
        from app.core.config import Settings

        _, Session, _ = isolated_db
        monkeypatch.setattr(
            config_mod, "settings",
            Settings(FIRST_SUPERUSER="", FIRST_SUPERUSER_PASSWORD="", DATABASE_URL="sqlite:///:memory:"),
        )
        seed_first_superuser_if_configured()
        with Session() as s:
            assert s.query(User).count() == 0

    def test_invalid_email_skips(self, isolated_db, monkeypatch):
        """非邮箱格式时跳过并打 warning。"""
        from app.core import config as config_mod
        from app.core.config import Settings

        _, Session, _ = isolated_db
        monkeypatch.setattr(
            config_mod, "settings",
            Settings(FIRST_SUPERUSER="not-an-email", FIRST_SUPERUSER_PASSWORD="x", DATABASE_URL="sqlite:///:memory:"),
        )
        seed_first_superuser_if_configured()
        with Session() as s:
            assert s.query(User).count() == 0
