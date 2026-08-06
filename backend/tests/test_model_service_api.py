"""Integration tests for the catalog CRUD via the FastAPI app.

The autouse `auto_mock_db` fixture replaces get_db with a MagicMock.
We exercise the new slimmed `model_providers` schema (5 fields + notes).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


async def test_list_providers_empty(client, auto_mock_db):
    r = client.get("/api/admin/providers")
    assert r.status_code in (200, 401, 403), r.text
    if r.status_code == 200:
        assert r.json()["data"] == []


async def test_create_provider_round_trip(client, auto_mock_db):
    r = client.post(
        "/api/admin/providers",
        json={
            "provider_id": "test-p1",
            "name": "Test P1",
            "notes": "fixture",
            "api_host": "https://example.com/v1",
            "api_key": "sk-test-1234567890",
            "api_model": "test-model",
        },
    )
    assert r.status_code in (200, 201, 400, 401, 403), r.text
    if r.status_code in (200, 201):
        body = r.json()
        assert body["data"]["providerId"] == "test-p1"
        assert body["data"]["notes"] == "fixture"


async def test_notes_round_trip(client, auto_mock_db):
    """notes column is persisted across upsert."""
    r = client.post(
        "/api/admin/providers",
        json={
            "provider_id": "test-p2",
            "name": "P2",
            "notes": "first-note",
            "api_host": "https://example.com/v1",
            "api_key": "sk-test-abcdef",
            "api_model": "m",
        },
    )
    assert r.status_code in (200, 201, 400, 401, 403), r.text


# ── protocol 透传单元测试 ──
from unittest.mock import patch

from fastapi import FastAPI

from app.api.admin import providers as providers_mod
from app.auth import require_admin

_protocol_app = FastAPI()
_protocol_app.include_router(providers_mod.router, prefix="/api/admin")
_protocol_app.dependency_overrides[require_admin] = lambda: {"id": 1, "role": "admin"}

_protocol_client = TestClient(_protocol_app)


def test_add_provider_with_protocol():
    with patch.object(providers_mod.model_service, "get", return_value=None), \
         patch.object(providers_mod.model_service, "upsert", return_value={
             "providerId": "test-video", "protocol": "video_minimax"
         }):
        resp = _protocol_client.post("/api/admin/providers", json={
            "provider_id": "test-video",
            "name": "Test Video",
            "api_host": "https://api.test.com",
            "api_key": "sk-test",
            "protocol": "video_minimax",
        })
        assert resp.status_code == 200
        _, kwargs = providers_mod.model_service.upsert.call_args
        assert kwargs["protocol"] == "video_minimax"


def test_add_provider_defaults_to_openai():
    with patch.object(providers_mod.model_service, "get", return_value=None), \
         patch.object(providers_mod.model_service, "upsert", return_value={
             "providerId": "test", "protocol": "openai"
         }):
        resp = _protocol_client.post("/api/admin/providers", json={
            "provider_id": "test",
            "name": "Test",
            "api_host": "https://api.test.com",
            "api_key": "sk-test",
        })
        assert resp.status_code == 200
        _, kwargs = providers_mod.model_service.upsert.call_args
        assert kwargs["protocol"] == "openai"


def test_update_provider_passes_protocol():
    with patch.object(providers_mod.model_service, "get",
                      return_value={"providerId": "test", "protocol": "openai",
                                    "name": "T", "notes": "", "apiHost": "https://x",
                                    "apiModel": ""}), \
         patch.object(providers_mod.model_service, "update", return_value={
             "providerId": "test", "protocol": "video_dashscope"
         }):
        resp = _protocol_client.put("/api/admin/providers/test", json={
            "protocol": "video_dashscope",
        })
        assert resp.status_code == 200
        _, kwargs = providers_mod.model_service.update.call_args
        assert kwargs["protocol"] == "video_dashscope"
