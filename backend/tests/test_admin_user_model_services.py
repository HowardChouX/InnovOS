"""Tests for admin user_model_services API endpoints — capability parameter.

Tests that the `capability` query/body parameter is correctly passed through
to SQL queries and that different capabilities return different data.

Covers:
1. GET /api/admin/users/{user_id}/model-services — list enabled services
2. GET /api/admin/users/{user_id}/model-services/available — list available
3. POST /api/admin/users/{user_id}/model-services — add provider
4. DELETE /api/admin/users/{user_id}/model-services/{provider_id} — remove
5. POST /api/admin/users/{user_id}/model-services/{provider_id}/toggle — toggle
6. PUT /api/admin/users/{user_id}/model-services/order — reorder
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


# ── Mock Data ──

SERVICES_CHAT = [
    {
        "provider_id": "openai",
        "capability": "chat",
        "failover_order": 1,
        "is_enabled": True,
        "name": "OpenAI",
        "api_host": "https://api.openai.com",
        "api_model": "gpt-4",
        "is_healthy": True,
        "consecutive_failures": 0,
        "cooldown_until": None,
    },
    {
        "provider_id": "anthropic",
        "capability": "chat",
        "failover_order": 2,
        "is_enabled": True,
        "name": "Anthropic",
        "api_host": "https://api.anthropic.com",
        "api_model": "claude-3-opus",
        "is_healthy": True,
        "consecutive_failures": 0,
        "cooldown_until": None,
    },
]

SERVICES_EMBEDDING = [
    {
        "provider_id": "openai",
        "capability": "embedding",
        "failover_order": 1,
        "is_enabled": True,
        "name": "OpenAI",
        "api_host": "https://api.openai.com",
        "api_model": "text-embedding-3-large",
        "is_healthy": True,
        "consecutive_failures": 0,
        "cooldown_until": None,
    },
]

AVAILABLE_CHAT = [
    {
        "provider_id": "anthropic",
        "name": "Anthropic",
        "api_host": "https://api.anthropic.com",
        "api_model": "claude-3-opus",
        "is_healthy": True,
        "already_enabled": False,
    },
    {
        "provider_id": "google",
        "name": "Google",
        "api_host": "https://api.google.com",
        "api_model": "gemini-pro",
        "is_healthy": True,
        "already_enabled": False,
    },
    {
        "provider_id": "openai",
        "name": "OpenAI",
        "api_host": "https://api.openai.com",
        "api_model": "gpt-4",
        "is_healthy": True,
        "already_enabled": False,
    },
]

AVAILABLE_EMBEDDING = [
    {
        "provider_id": "cohere",
        "name": "Cohere",
        "api_host": "https://api.cohere.com",
        "api_model": "embed-english-v3",
        "is_healthy": True,
        "already_enabled": False,
    },
    {
        "provider_id": "openai",
        "name": "OpenAI",
        "api_host": "https://api.openai.com",
        "api_model": "text-embedding-3-large",
        "is_healthy": True,
        "already_enabled": False,
    },
]


# ── Fake Cursor ──


class _FakeCursor:
    """Mock DB cursor that returns data based on SQL keywords.

    Matches the specific SQL patterns emitted by user_model_services.py
    and returns appropriate mock data for each pattern.
    """

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self._services = {
            "chat": list(SERVICES_CHAT),
            "embedding": list(SERVICES_EMBEDDING),
            "rerank": [],
        }
        self._available = {
            "chat": list(AVAILABLE_CHAT),
            "embedding": list(AVAILABLE_EMBEDDING),
            "rerank": [],
        }
        # Controls for add_service and toggle tests
        self._existing_check: dict | None = None
        self._next_order_val: int = 1
        self._update_rowcount: int = 1

    # ── configuration helpers for tests ──

    def set_existing(self, row: dict | None) -> None:
        """Set the return value for the 'check if service exists' query."""
        self._existing_check = row

    def set_next_order(self, val: int) -> None:
        """Set the next failover_order value."""
        self._next_order_val = val

    def set_update_rowcount(self, val: int) -> None:
        """Set the rowcount for UPDATE queries (default 1)."""
        self._update_rowcount = val

    def set_services(self, capability: str, data: list) -> None:
        """Override the services data for a given capability."""
        self._services[capability] = data

    # ── helpers ──

    @staticmethod
    def _extract_capability(params) -> str:
        if params and isinstance(params, tuple):
            for p in params:
                if p in ("chat", "embedding", "rerank"):
                    return str(p)
        return "chat"

    # ── mock DB API ──

    def execute(self, sql: str, params=None):
        self.calls.append((sql, params or ()))
        cur = MagicMock()
        sql_l = sql.strip().lower()
        cap = self._extract_capability(params)

        # _load_available() — has "already_enabled" alias (unique to this query)
        if "already_enabled" in sql_l:
            cur.fetchall.return_value = self._available.get(cap, [])
            return cur

        # _load() — SELECT from user_model_services with JOIN
        if "join model_providers" in sql_l:
            cur.fetchall.return_value = self._services.get(cap, [])
            return cur

        # _next_order() — SELECT COALESCE(MAX(failover_order), ...)
        if "max(failover_order)" in sql_l:
            cur.fetchone.return_value = {"next": self._next_order_val}
            return cur

        # add_user_service() existing check — SELECT failover_order, is_enabled
        if sql_l.startswith("select") and "failover_order, is_enabled" in sql_l:
            cur.fetchone.return_value = self._existing_check
            return cur

        # UPDATE
        if sql_l.startswith("update"):
            cur.rowcount = self._update_rowcount
            return cur

        # DELETE
        if sql_l.startswith("delete"):
            cur.rowcount = 1
            return cur

        # INSERT
        if sql_l.startswith("insert"):
            cur.rowcount = 1
            return cur

        # Fallback
        cur.fetchone.return_value = None
        cur.fetchall.return_value = []
        cur.rowcount = 0
        return cur

    def commit(self):
        pass

    def close(self):
        pass


# ── Fixtures ──


@pytest.fixture
def fake_cursor():
    return _FakeCursor()


@pytest.fixture
def app_with_mock_db(monkeypatch, fake_cursor):
    """Build a minimal FastAPI app with the user_model_services router.

    Patches the module-level get_db reference directly so monkeypatch
    takes effect even if the module was already imported elsewhere.
    """
    from app.api.admin import user_model_services as ums_router
    from app.auth import require_admin

    # Patch the module-level get_db reference directly
    monkeypatch.setattr("app.api.admin.user_model_services.get_db", lambda: fake_cursor)

    app = FastAPI()
    from fastapi import APIRouter

    admin_router = APIRouter(prefix="/api/admin")
    admin_router.include_router(ums_router.router)
    app.include_router(admin_router)

    app.dependency_overrides[require_admin] = lambda: {
        "user_id": 1,
        "username": "admin",
        "role": "admin",
    }

    return app, fake_cursor


@pytest.fixture
def client(app_with_mock_db):
    app, _ = app_with_mock_db
    return TestClient(app)


# ====================================================================
# GET /api/admin/users/{user_id}/model-services  —  list enabled services
# ====================================================================


class TestListServices:
    """GET /api/admin/users/{user_id}/model-services"""

    def test_default_capability_is_chat(self, client):
        """When no capability param is given, defaults to 'chat'."""
        response = client.get("/api/admin/users/1/model-services")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "success"
        for item in data["data"]:
            assert item["capability"] == "chat"

    def test_chat_returns_two_services(self, client):
        """Explicit 'chat' capability returns two services."""
        response = client.get(
            "/api/admin/users/1/model-services", params={"capability": "chat"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["data"][0]["provider_id"] == "openai"
        assert data["data"][1]["provider_id"] == "anthropic"

    def test_embedding_returns_one_service(self, client):
        """'embedding' capability returns a different set of services."""
        response = client.get(
            "/api/admin/users/1/model-services", params={"capability": "embedding"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["provider_id"] == "openai"
        assert data["data"][0]["capability"] == "embedding"

    def test_rerank_returns_empty(self, client):
        """'rerank' capability returns an empty list when no services configured."""
        response = client.get(
            "/api/admin/users/1/model-services", params={"capability": "rerank"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 0

    def test_passes_capability_to_sql(self, client, fake_cursor):
        """The capability value is forwarded to the SQL query as a parameter."""
        client.get(
            "/api/admin/users/1/model-services", params={"capability": "embedding"}
        )
        load_calls = [
            c
            for c in fake_cursor.calls
            if "from user_model_services" in c[0].lower()
            and "join model_providers" in c[0].lower()
        ]
        assert len(load_calls) >= 1
        _, params = load_calls[0]
        assert "embedding" in params


# ====================================================================
# GET /api/admin/users/{user_id}/model-services/available  —  list available
# ====================================================================


class TestListAvailableServices:
    """GET /api/admin/users/{user_id}/model-services/available"""

    def test_default_capability_is_chat(self, client):
        """When no capability param is given, defaults to 'chat'."""
        response = client.get("/api/admin/users/1/model-services/available")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "success"
        # All available providers for chat
        assert len(data["data"]) == 3

    def test_embedding_returns_different_providers(self, client):
        """'embedding' capability returns a different set of available providers."""
        response = client.get(
            "/api/admin/users/1/model-services/available",
            params={"capability": "embedding"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        provider_ids = {p["provider_id"] for p in data["data"]}
        assert "cohere" in provider_ids

    def test_rerank_returns_empty(self, client):
        """'rerank' capability returns an empty list when no providers available."""
        response = client.get(
            "/api/admin/users/1/model-services/available",
            params={"capability": "rerank"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 0

    def test_passes_capability_to_sql(self, client, fake_cursor):
        """The capability value is forwarded to the available SQL query."""
        client.get(
            "/api/admin/users/1/model-services/available",
            params={"capability": "embedding"},
        )
        avail_calls = [
            c for c in fake_cursor.calls if "already_enabled" in c[0].lower()
        ]
        assert len(avail_calls) >= 1
        _, params = avail_calls[0]
        assert "embedding" in params


# ====================================================================
# POST /api/admin/users/{user_id}/model-services  —  add provider
# ====================================================================


class TestAddService:
    """POST /api/admin/users/{user_id}/model-services"""

    def test_add_new_service(self, client, fake_cursor):
        """Adding a new service returns 'added'."""
        fake_cursor.set_existing(None)
        fake_cursor.set_next_order(3)
        response = client.post(
            "/api/admin/users/1/model-services",
            json={"provider_id": "google", "capability": "chat"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "added"

    def test_add_existing_service_returns_already_enabled(self, client, fake_cursor):
        """Adding a service that already exists returns 'already enabled'."""
        fake_cursor.set_existing({"failover_order": 1, "is_enabled": True})
        response = client.post(
            "/api/admin/users/1/model-services",
            json={"provider_id": "openai", "capability": "chat"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "already enabled"

    def test_default_capability_in_body(self, client, fake_cursor):
        """When no capability in body, defaults to 'chat'."""
        fake_cursor.set_existing(None)
        fake_cursor.set_next_order(1)
        response = client.post(
            "/api/admin/users/1/model-services",
            json={"provider_id": "openai"},
        )
        assert response.status_code == 200
        # Verify the INSERT used 'chat' as the capability
        insert_calls = [
            c for c in fake_cursor.calls if c[0].strip().lower().startswith("insert")
        ]
        assert len(insert_calls) >= 1
        _, params = insert_calls[0]
        assert "chat" in params

    def test_add_with_embedding_capability(self, client, fake_cursor):
        """Adding a service with 'embedding' capability."""
        fake_cursor.set_existing(None)
        fake_cursor.set_next_order(1)
        response = client.post(
            "/api/admin/users/1/model-services",
            json={"provider_id": "cohere", "capability": "embedding"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "added"
        # Verify the capability was used in the existing-service check
        select_calls = [
            c
            for c in fake_cursor.calls
            if c[0].strip().lower().startswith("select")
            and "failover_order, is_enabled" in c[0].lower()
        ]
        assert len(select_calls) >= 1
        _, params = select_calls[0]
        assert "embedding" in params


# ====================================================================
# DELETE /api/admin/users/{user_id}/model-services/{provider_id}  —  remove
# ====================================================================


class TestRemoveService:
    """DELETE /api/admin/users/{user_id}/model-services/{provider_id}"""

    def test_remove_with_default_capability(self, client, fake_cursor):
        """When no capability param, defaults to 'chat'."""
        response = client.delete("/api/admin/users/1/model-services/openai")
        assert response.status_code == 204

    def test_remove_with_chat_capability(self, client, fake_cursor):
        """Explicit 'chat' capability removes the service."""
        response = client.delete(
            "/api/admin/users/1/model-services/openai",
            params={"capability": "chat"},
        )
        assert response.status_code == 204

    def test_remove_passes_capability_to_sql(self, client, fake_cursor):
        """The capability value is forwarded to the DELETE SQL."""
        client.delete(
            "/api/admin/users/1/model-services/openai",
            params={"capability": "embedding"},
        )
        delete_calls = [
            c for c in fake_cursor.calls if c[0].strip().lower().startswith("delete")
        ]
        assert len(delete_calls) >= 1
        _, params = delete_calls[0]
        assert "embedding" in params


# ====================================================================
# POST /api/admin/users/{user_id}/model-services/{provider_id}/toggle  —  toggle
# ====================================================================


class TestToggleService:
    """POST /api/admin/users/{user_id}/model-services/{provider_id}/toggle"""

    def test_toggle_enable(self, client, fake_cursor):
        """Toggling a service enabled returns is_enabled=True."""
        fake_cursor.set_update_rowcount(1)
        response = client.post(
            "/api/admin/users/1/model-services/openai/toggle",
            json={"is_enabled": True, "capability": "chat"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["is_enabled"] is True

    def test_toggle_disable(self, client, fake_cursor):
        """Toggling a service disabled returns is_enabled=False."""
        fake_cursor.set_update_rowcount(1)
        response = client.post(
            "/api/admin/users/1/model-services/openai/toggle",
            json={"is_enabled": False, "capability": "chat"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["is_enabled"] is False

    def test_toggle_with_default_capability(self, client, fake_cursor):
        """When no capability in body, defaults to 'chat' in SQL."""
        fake_cursor.set_update_rowcount(1)
        response = client.post(
            "/api/admin/users/1/model-services/openai/toggle",
            json={"is_enabled": True},
        )
        assert response.status_code == 200
        # Verify the UPDATE used 'chat' as the capability
        update_calls = [
            c for c in fake_cursor.calls if c[0].strip().lower().startswith("update")
        ]
        assert len(update_calls) >= 1
        _, params = update_calls[0]
        assert "chat" in params

    def test_toggle_passes_capability_to_sql(self, client, fake_cursor):
        """The capability is forwarded to the UPDATE SQL."""
        fake_cursor.set_update_rowcount(1)
        client.post(
            "/api/admin/users/1/model-services/openai/toggle",
            json={"is_enabled": True, "capability": "embedding"},
        )
        update_calls = [
            c for c in fake_cursor.calls if c[0].strip().lower().startswith("update")
        ]
        assert len(update_calls) >= 1
        _, params = update_calls[0]
        assert "embedding" in params

    def test_toggle_nonexistent_service_returns_404(self, client, fake_cursor):
        """Toggling a service that is not enabled returns 404."""
        fake_cursor.set_update_rowcount(0)
        response = client.post(
            "/api/admin/users/1/model-services/nonexistent/toggle",
            json={"is_enabled": True, "capability": "chat"},
        )
        assert response.status_code == 404
        assert "not enabled" in response.json()["detail"]


# ====================================================================
# PUT /api/admin/users/{user_id}/model-services/order  —  reorder
# ====================================================================


class TestReorderServices:
    """PUT /api/admin/users/{user_id}/model-services/order"""

    def test_reorder_with_capability(self, client, fake_cursor):
        """Reordering with explicit capability returns 'reordered'."""
        response = client.put(
            "/api/admin/users/1/model-services/order",
            json={"provider_ids": ["anthropic", "openai"], "capability": "chat"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "reordered"

    def test_reorder_with_default_capability(self, client, fake_cursor):
        """When no capability in body, defaults to 'chat' in SQL."""
        response = client.put(
            "/api/admin/users/1/model-services/order",
            json={"provider_ids": ["openai"]},
        )
        assert response.status_code == 200
        # Verify the DELETE used 'chat' as the capability
        delete_calls = [
            c for c in fake_cursor.calls if c[0].strip().lower().startswith("delete")
        ]
        assert len(delete_calls) >= 1
        _, params = delete_calls[0]
        assert "chat" in params

    def test_reorder_passes_capability_to_sql(self, client, fake_cursor):
        """The capability is forwarded to the DELETE/INSERT/UPDATE SQL."""
        client.put(
            "/api/admin/users/1/model-services/order",
            json={"provider_ids": ["anthropic"], "capability": "embedding"},
        )
        delete_calls = [
            c for c in fake_cursor.calls if c[0].strip().lower().startswith("delete")
        ]
        assert len(delete_calls) >= 1
        _, params = delete_calls[0]
        assert "embedding" in params

    def test_reorder_duplicate_provider_returns_409(self, client):
        """Duplicate provider_ids in the order list returns 409."""
        response = client.put(
            "/api/admin/users/1/model-services/order",
            json={"provider_ids": ["openai", "openai"], "capability": "chat"},
        )
        assert response.status_code == 409
        assert "duplicate provider_id" in response.json()["detail"]

    def test_reorder_empty_list(self, client, fake_cursor):
        """Empty provider_ids list clears all services for the capability."""
        response = client.put(
            "/api/admin/users/1/model-services/order",
            json={"provider_ids": [], "capability": "chat"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "reordered"


# ====================================================================
# Authentication — non-admin users are rejected
# ====================================================================


class TestAuth:
    """Verify that non-admin users are rejected for all endpoints."""

    @pytest.fixture
    def user_client(self, app_with_mock_db):
        app, _ = app_with_mock_db
        from app.auth import require_admin

        def deny():
            raise HTTPException(status_code=403, detail="Forbidden")

        app.dependency_overrides[require_admin] = deny
        return TestClient(app)

    def test_list_requires_admin(self, user_client):
        response = user_client.get("/api/admin/users/1/model-services")
        assert response.status_code == 403

    def test_list_available_requires_admin(self, user_client):
        response = user_client.get("/api/admin/users/1/model-services/available")
        assert response.status_code == 403

    def test_add_requires_admin(self, user_client):
        response = user_client.post(
            "/api/admin/users/1/model-services",
            json={"provider_id": "openai"},
        )
        assert response.status_code == 403

    def test_remove_requires_admin(self, user_client):
        response = user_client.delete("/api/admin/users/1/model-services/openai")
        assert response.status_code == 403

    def test_toggle_requires_admin(self, user_client):
        response = user_client.post(
            "/api/admin/users/1/model-services/openai/toggle",
            json={"is_enabled": True},
        )
        assert response.status_code == 403

    def test_reorder_requires_admin(self, user_client):
        response = user_client.put(
            "/api/admin/users/1/model-services/order",
            json={"provider_ids": ["openai"]},
        )
        assert response.status_code == 403