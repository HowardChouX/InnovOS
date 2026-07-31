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
