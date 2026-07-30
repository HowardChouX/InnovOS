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


def test_dev_otp_logged_when_smtp_unset(monkeypatch, caplog):
    """dev 模式 + SMTP_HOST 留空时,OTP 明码写入 backend 日志。
    注:EmailService 在 __init__ 缓存了 settings.SMTP_HOST 到 self.host,
    需同时清空实例属性。
    """
    from app.services import email_service as es

    class _User:
        email = "a@b.com"

    monkeypatch.setattr(es.settings, "SMTP_HOST", "")
    monkeypatch.setattr(es.settings, "ENVIRONMENT", "development")
    es.email_service.host = ""  # 覆盖 __init__ 缓存值
    with caplog.at_level("INFO", logger=es.logger.name):
        es.email_service.send_verification_otp_sync(_User(), "123456")
    assert any("[DEV OTP]" in rec.message and "code=123456" in rec.message for rec in caplog.records)


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


def test_password_reset_otp_email_includes_code(configured_service):
    """重置密码邮件只发 6 位验证码,不含 URL。"""
    import base64
    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        mock_smtp.return_value = server
        user = MagicMock()
        user.email = "test@example.com"
        configured_service.send_password_reset_otp_sync(user, "199622")
        raw = server.sendmail.call_args[0][2]
        # MIME multipart/alternative: 提取 base64 段后断言
        html = _extract_html_body(raw)
        assert "199622" in html, "邮件必须包含 6 位验证码"
        assert "http://" not in html and "https://" not in html, \
            "重置邮件不应包含任何 URL"


def test_email_templates_use_brand_card_layout(configured_service):
    """所有邮件模板走统一卡片样式(_wrap_card 输出的 <!DOCTYPE html> 结构)。"""
    import base64
    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        mock_smtp.return_value = server
        user = MagicMock()
        user.email = "test@example.com"
        configured_service.send_password_reset_otp_sync(user, "199622")
        raw = server.sendmail.call_args[0][2]
        html = _extract_html_body(raw)
        # 卡片样式特征:DOCTYPE + 渐变背景 + 居中胶囊验证码
        assert "<!DOCTYPE html>" in html
        assert "linear-gradient" in html
        assert "InnovOS" in html
        assert "monospace" in html  # 验证码等宽字体


def _extract_html_body(mime_raw: str) -> str:
    """从 multipart/alternative 邮件中提取 base64 解码后的 HTML 段。"""
    import base64
    import re
    # 找到 text/html 段后的 base64 内容
    m = re.search(
        r'Content-Type: text/html.*?\n\n([A-Za-z0-9+/=\s]+)--',
        mime_raw,
        re.DOTALL,
    )
    if not m:
        return mime_raw  # fallback: 未匹配则返回原文本
    return base64.b64decode(m.group(1)).decode("utf-8", "ignore")