"""邮件服务测试 - mock SMTP。"""
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_service import EmailService


@pytest.fixture
def configured_service():
    """返回 SMTP_HOST 已配置的 EmailService。"""
    svc = EmailService()
    svc.host = "smtp.test.local"
    svc.port = 25
    svc.user = ""
    svc.password = ""
    svc.from_email = "noreply@test.local"
    svc.use_tls = False
    svc.use_ssl = False
    return svc


def test_send_verification_email_calls_smtp(configured_service):
    """send_verification_email_sync 应调用 SMTP。"""
    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        server.__enter__ = MagicMock(return_value=server)
        server.__exit__ = MagicMock(return_value=False)
        mock_smtp.return_value = server
        user = MagicMock()
        user.email = "test@example.com"
        configured_service.send_verification_email_sync(user, "token123")
        assert server.sendmail.called


def test_send_reset_password_email_calls_smtp(configured_service):
    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        server.__enter__ = MagicMock(return_value=server)
        server.__exit__ = MagicMock(return_value=False)
        mock_smtp.return_value = server
        user = MagicMock()
        user.email = "test@example.com"
        configured_service.send_reset_password_email_sync(user, "token123")
        assert server.sendmail.called


def test_send_skipped_when_smtp_not_configured():
    """SMTP_HOST 未配置时跳过发送。"""
    svc = EmailService()
    svc.host = ""
    user = MagicMock()
    user.email = "test@example.com"
    # 不抛异常即通过
    svc.send_verification_email_sync(user, "token123")
    svc.send_reset_password_email_sync(user, "token123")



def test_dev_reset_url_logged_when_smtp_unset(monkeypatch, caplog):
    """dev 模式 + SMTP_HOST 留空时,reset URL 明码写入 backend 日志。"""
    from app.services import email_service as es

    class _User:
        email = "a@b.com"

    monkeypatch.setattr(es.settings, "SMTP_HOST", "")
    monkeypatch.setattr(es.settings, "ENVIRONMENT", "development")
    es.email_service.host = ""
    with caplog.at_level("INFO", logger=es.logger.name):
        es.email_service.send_reset_password_email_sync(_User(), "tok-xyz")
    assert any(
        "[DEV RESET]" in rec.message
        and "url=" in rec.message
        and "/reset-password?token=tok-xyz" in rec.message
        for rec in caplog.records
    )


def test_dev_verify_url_logged_when_smtp_unset(monkeypatch, caplog):
    """dev 模式 + SMTP_HOST 留空时,verify URL 明码写入 backend 日志。"""
    from app.services import email_service as es

    class _User:
        email = "a@b.com"

    monkeypatch.setattr(es.settings, "SMTP_HOST", "")
    monkeypatch.setattr(es.settings, "ENVIRONMENT", "development")
    es.email_service.host = ""
    with caplog.at_level("INFO", logger=es.logger.name):
        es.email_service.send_verification_email_sync(_User(), "tok-abc")
    assert any(
        "[DEV VERIFY]" in rec.message
        and "/verify-email?token=tok-abc" in rec.message
        for rec in caplog.records
    )


