"""注册端点测试。"""
from tests.conftest_auth import *  # noqa: F401, F403


class TestRegister:
    def test_register_success(self, auth_client, auth_session):
        """成功注册返回 201，用户写入 DB。"""
        resp = auth_client.post("/api/auth/register", json={
            "email": "new@example.com",
            "password": "test1234",
            "phone": "13800000000",
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert "id" in data
        assert data["is_active"] is True

    def test_register_duplicate_email(self, auth_client, seed_user):
        """重复邮箱返回 400。"""
        resp = auth_client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "test1234",
        })
        assert resp.status_code == 400

    def test_register_short_password(self, auth_client):
        """密码 < 8 位返回 400。"""
        resp = auth_client.post("/api/auth/register", json={
            "email": "short@example.com",
            "password": "123",
        })
        assert resp.status_code == 400
        data = resp.json()
        # FastAPI Users register router 用 ErrorCode，详情在 reason
        detail = data.get("detail", {})
        if isinstance(detail, dict):
            assert "密码至少 8 位" in detail.get("reason", "")

    def test_register_phone_optional(self, auth_client):
        """phone 可选。"""
        resp = auth_client.post("/api/auth/register", json={
            "email": "nophone@example.com",
            "password": "test1234",
        })
        assert resp.status_code == 201, resp.text

    def test_register_invalid_email(self, auth_client):
        """非法 email 返回 422。"""
        resp = auth_client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "test1234",
        })
        assert resp.status_code == 422