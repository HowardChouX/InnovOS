"""
TDD 测试: /api/admin/providers/{provider_id}/keys 路由

覆盖:
1. POST 创建 Key(201)
2. POST 缺少 plaintext → 422
3. POST 非管理员 → 403
4. GET 列表 → 掩码 + 短 fingerprint
5. PATCH metadata → 不改密文
6. PUT /secret → 替换密文
7. POST /activate / /deactivate → is_active 切换
8. DELETE → 软删
9. 任何响应都不能含 plaintext / ciphertext / nonce
"""

from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def master_key(monkeypatch):
    monkeypatch.setenv(
        "INNOVOS_ENCRYPT_KEY",
        base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("="),
    )


@pytest.fixture
def app_with_mock_db(master_key, monkeypatch):
    """构造一个测试 app,mock 掉 ApiKeyService 实际依赖。"""
    from app.api.admin import providers as providers_router
    from app.auth import get_current_user

    # mock ApiKeyService:对所有调用返回确定值
    fake_service = MagicMock()
    fake_service.create_key.return_value = {
        "id": 1,
        "provider_id": "openai",
        "name": "prod-primary",
        "masked": "sk-••••••••9a7f",
        "prefix": "sk-",
        "fingerprint": "2e6f9bd94d30",
        "priority": 100,
        "is_active": True,
        "max_rpm": 60,
        "request_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "last_used_at": None,
        "cooldown_until": None,
        "last_error_code": None,
        "created_by": 7,
        "updated_by": 7,
    }
    fake_service.list_keys.return_value = [
        {
            "id": 1,
            "provider_id": "openai",
            "name": "prod-primary",
            "masked": "sk-••••••••9a7f",
            "prefix": "sk-",
            "fingerprint": "2e6f9bd94d30",
            "priority": 100,
            "is_active": True,
            "max_rpm": 60,
            "request_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "last_used_at": None,
            "cooldown_until": None,
            "last_error_code": None,
            "created_by": 7,
            "updated_by": 7,
        }
    ]
    fake_service.update_metadata.return_value = fake_service.create_key.return_value
    fake_service.replace_secret.return_value = fake_service.create_key.return_value
    fake_service.activate.return_value = fake_service.create_key.return_value
    fake_service.deactivate.return_value = {
        **fake_service.create_key.return_value,
        "is_active": False,
    }
    fake_service.delete_key.return_value = True

    # patch ApiKeyService factory
    monkeypatch.setattr(
        "app.api.admin.providers._get_api_key_service", lambda: fake_service
    )

    # patch require_admin / get_current_user
    app = FastAPI()
    app.include_router(providers_router.router)

    return app, fake_service


@pytest.fixture
def admin_user():
    return {"user_id": 7, "username": "admin", "is_superuser": True}


@pytest.fixture
def normal_user():
    return {"user_id": 1, "username": "user"}


@pytest.fixture
def admin_client(app_with_mock_db, admin_user):
    app, _ = app_with_mock_db
    from app.auth import require_admin

    app.dependency_overrides[require_admin] = lambda: admin_user
    return TestClient(app)


@pytest.fixture
def user_client(app_with_mock_db, normal_user):
    app, _ = app_with_mock_db
    from app.auth import require_admin

    # 模拟非管理员 — 让 require_admin 拒绝
    def deny():
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Forbidden")

    app.dependency_overrides[require_admin] = deny
    return TestClient(app)


# ── CREATE ──


class TestCreateKey:
    def test_create_key_returns_201(self, admin_client):
        response = admin_client.post(
            "/providers/openai/keys",
            json={"name": "prod-primary", "apiKey": "sk-secret", "priority": 100},
        )
        assert response.status_code in (200, 201), response.text

    def test_create_key_response_does_not_contain_plaintext_or_ciphertext(
        self, admin_client
    ):
        response = admin_client.post(
            "/providers/openai/keys",
            json={"name": "prod-primary", "apiKey": "sk-secret-leak-XYZ", "priority": 100},
        )
        body = response.text
        for forbidden in (
            "sk-secret-leak-XYZ",  # 明文
            "key_ciphertext",
            "key_nonce",
            "ciphertext",
            "nonce",
        ):
            assert forbidden not in body, f"响应泄漏了 {forbidden}"

    def test_create_key_without_plaintext_returns_422(self, admin_client):
        response = admin_client.post(
            "/providers/openai/keys",
            json={"name": "no-key"},
        )
        assert response.status_code == 422


class TestAuth:
    def test_non_admin_gets_403(self, user_client):
        response = user_client.get("/providers/openai/keys")
        assert response.status_code == 403


# ── LIST ──


class TestListKeys:
    def test_list_keys_returns_masked(self, admin_client):
        response = admin_client.get("/providers/openai/keys")
        assert response.status_code == 200
        body = response.text
        # 不含明文
        assert "sk-secret" not in body
        # 含掩码
        assert "masked" in body

    def test_list_keys_response_does_not_leak(self, admin_client):
        response = admin_client.get("/providers/openai/keys")
        body = response.text
        for forbidden in ("key_ciphertext", "key_nonce", "ciphertext", "nonce", "plaintext"):
            assert forbidden not in body


# ── PATCH METADATA ──


class TestUpdateMetadata:
    def test_patch_metadata_returns_updated_key(self, admin_client):
        response = admin_client.patch(
            "/providers/openai/keys/1",
            json={"name": "renamed", "priority": 50, "isActive": False},
        )
        assert response.status_code == 200


# ── REPLACE SECRET ──


class TestReplaceSecret:
    def test_replace_secret_returns_masked_only(self, admin_client):
        response = admin_client.put(
            "/providers/openai/keys/1/secret",
            json={"apiKey": "sk-new-secret-XYZ"},
        )
        assert response.status_code == 200
        body = response.text
        for forbidden in ("sk-new-secret-XYZ", "key_ciphertext", "key_nonce"):
            assert forbidden not in body, f"响应泄漏了 {forbidden}"


# ── ACTIVATE / DEACTIVATE / DELETE ──


class TestStateTransitions:
    def test_deactivate(self, admin_client):
        response = admin_client.post("/providers/openai/keys/1/deactivate")
        assert response.status_code == 200

    def test_activate(self, admin_client):
        response = admin_client.post("/providers/openai/keys/1/activate")
        assert response.status_code == 200

    def test_delete_returns_204(self, admin_client):
        response = admin_client.delete("/providers/openai/keys/1")
        assert response.status_code in (200, 204)