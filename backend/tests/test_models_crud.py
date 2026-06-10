"""测试 models 独立表 CRUD（使用 SQLite 内存数据库）"""
import sqlite3
import pytest


class FakeDB:
    """模拟 app.database.Database — 封装 SQLite 连接。"""
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        import re
        sql_clean = re.sub(r'\s+RETURNING\s+\S+', '', sql, flags=re.IGNORECASE)
        try:
            cur = self._conn.execute(sql_clean, params or ())
        except sqlite3.OperationalError as e:
            if "RETURNING" in str(e).upper():
                sql_clean = re.sub(r'\s+RETURNING\s+\S+', '', sql, flags=re.IGNORECASE)
                cur = self._conn.execute(sql_clean, params or ())
            else:
                raise
        return cur

    def close(self):
        pass


@pytest.fixture(autouse=True)
def real_db(monkeypatch):
    """替换全局 get_db 为 SQLite 内存数据库。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # 直接创建 models 表（SQLite 兼容语法）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS models (
            provider_id     TEXT NOT NULL,
            model_id        TEXT NOT NULL,
            name            TEXT DEFAULT '',
            capabilities    TEXT DEFAULT '[]',
            endpoint_types  TEXT DEFAULT '[]',
            context_window  INTEGER DEFAULT 0,
            max_output_tokens INTEGER DEFAULT 0,
            max_input_tokens  INTEGER DEFAULT 0,
            model_group     TEXT DEFAULT '',
            is_enabled      INTEGER DEFAULT 1,
            metadata        TEXT DEFAULT '{}',
            PRIMARY KEY (provider_id, model_id)
        )
    """)
    conn.commit()

    fake_db = FakeDB(conn)

    # patch 所有引用 get_db 的模块
    targets = [
        "app.database.get_db",
        "app.database.init_db",
        "app.api.models.get_db",
        "app.algorithm.model_service.get_db",
        "app.algorithm.models_crud.get_db",
    ]
    for t in targets:
        try:
            monkeypatch.setattr(t, lambda: fake_db)
        except AttributeError:
            pass
    monkeypatch.setattr("app.database.Database", lambda: fake_db)

    yield fake_db, conn
    conn.close()


class TestModelsTableSchema:
    def test_table_name_is_models(self):
        from app.tables.models import MODELS_TABLE
        assert MODELS_TABLE == "models"

    def test_create_ddl_includes_required_columns(self):
        from app.tables.models import MODELS_DDL
        assert "provider_id" in MODELS_DDL
        assert "model_id" in MODELS_DDL
        assert "name" in MODELS_DDL
        assert "capabilities" in MODELS_DDL
        assert "is_enabled" in MODELS_DDL

    def test_ddl_mentions_foreign_key(self):
        from app.tables.models import MODELS_DDL
        assert "FOREIGN KEY" in MODELS_DDL or "REFERENCES" in MODELS_DDL


class TestModelsCrudService:
    def test_create_model(self, real_db):
        from app.algorithm.models_crud import ModelsCrudService
        svc = ModelsCrudService()
        model = svc.create(
            provider_id="silicon",
            model_id="test-model",
            name="Test Model",
            capabilities=["chat"],
        )
        assert model["provider_id"] == "silicon"
        assert model["model_id"] == "test-model"
        assert model["is_enabled"] == 1
        assert model["capabilities"] == ["chat"]

    def test_get_by_provider_and_model(self, real_db):
        from app.algorithm.models_crud import ModelsCrudService
        svc = ModelsCrudService()
        svc.create(provider_id="silicon", model_id="test-model", name="Test")
        model = svc.get("silicon", "test-model")
        assert model is not None
        assert model["model_id"] == "test-model"

    def test_get_not_found(self, real_db):
        from app.algorithm.models_crud import ModelsCrudService
        svc = ModelsCrudService()
        assert svc.get("silicon", "nonexistent") is None

    def test_list_by_provider(self, real_db):
        from app.algorithm.models_crud import ModelsCrudService
        svc = ModelsCrudService()
        svc.create(provider_id="silicon", model_id="m1", name="M1")
        svc.create(provider_id="silicon", model_id="m2", name="M2")
        svc.create(provider_id="openai", model_id="o1", name="O1")
        models = svc.list_by_provider("silicon")
        assert len(models) == 2
        assert {m["model_id"] for m in models} == {"m1", "m2"}

    def test_update(self, real_db):
        from app.algorithm.models_crud import ModelsCrudService
        svc = ModelsCrudService()
        svc.create(provider_id="silicon", model_id="m1", name="M1", is_enabled=True)
        svc.update("silicon", "m1", {"name": "Updated", "is_enabled": 0})
        model = svc.get("silicon", "m1")
        assert model["name"] == "Updated"
        assert model["is_enabled"] == 0

    def test_delete(self, real_db):
        from app.algorithm.models_crud import ModelsCrudService
        svc = ModelsCrudService()
        svc.create(provider_id="silicon", model_id="m1", name="M1")
        assert svc.delete("silicon", "m1") is True
        assert svc.get("silicon", "m1") is None

    def test_delete_nonexistent(self, real_db):
        from app.algorithm.models_crud import ModelsCrudService
        svc = ModelsCrudService()
        assert svc.delete("silicon", "no-such-model") is False

    def test_batch_upsert(self, real_db):
        from app.algorithm.models_crud import ModelsCrudService
        svc = ModelsCrudService()
        models = [
            {"provider_id": "silicon", "model_id": "m1", "name": "M1"},
            {"provider_id": "silicon", "model_id": "m2", "name": "M2"},
        ]
        svc.batch_upsert("silicon", models)
        all_m = svc.list_by_provider("silicon")
        assert len(all_m) == 2

    def test_batch_upsert_updates_existing(self, real_db):
        from app.algorithm.models_crud import ModelsCrudService
        svc = ModelsCrudService()
        svc.create(provider_id="silicon", model_id="m1", name="Original")
        svc.batch_upsert("silicon", [
            {"provider_id": "silicon", "model_id": "m1", "name": "Updated"}
        ])
        model = svc.get("silicon", "m1")
        assert model["name"] == "Updated"

    def test_list_enabled(self, real_db):
        from app.algorithm.models_crud import ModelsCrudService
        svc = ModelsCrudService()
        svc.create(provider_id="silicon", model_id="m1", name="M1", is_enabled=True)
        svc.create(provider_id="silicon", model_id="m2", name="M2", is_enabled=False)
        enabled = svc.list_by_provider("silicon", only_enabled=True)
        assert len(enabled) == 1
        assert enabled[0]["model_id"] == "m1"
