"""邮件发送服务 - SMTP。

开发环境用 Mailpit（localhost:1025），生产环境用配置的 SMTP。
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.exceptions.email_verification import EmailUnavailable

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.use_tls = settings.SMTP_TLS
        self.use_ssl = settings.SMTP_SSL

    def _send(self, to_email: str, subject: str, body: str) -> None:
        """发送邮件（同步）。"""
        if not self.host:
            logger.warning("SMTP_HOST 未配置，跳过邮件发送 to=%s", to_email)
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html", "utf-8"))

        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port)
            else:
                server = smtplib.SMTP(self.host, self.port)
            try:
                if self.use_tls:
                    server.starttls()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.sendmail(self.from_email, [to_email], msg.as_string())
            finally:
                server.quit()
        except Exception as e:
            logger.error("邮件发送失败 to=%s: %s", to_email, e)

    def send_verification_email_sync(self, user, token: str, request=None) -> None:
        """发送邮箱验证邮件。"""
        verify_url = f"{settings.PUBLIC_URL}/verify?token={token}"
        body = f"""
        <h2>验证您的邮箱</h2>
        <p>请点击下方链接验证您的邮箱地址：</p>
        <p><a href="{verify_url}">{verify_url}</a></p>
        """
        self._send(user.email, "InnovOS 邮箱验证", body)

    def send_reset_password_email_sync(self, user, token: str, request=None) -> None:
        """发送密码重置邮件。"""
        reset_url = f"{settings.PUBLIC_URL}/reset-password?token={token}"
        body = f"""
        <h2>重置您的密码</h2>
        <p>请点击下方链接重置密码：</p>
        <p><a href="{reset_url}">{reset_url}</a></p>
        """
        self._send(user.email, "InnovOS 密码重置", body)

    def send_verification_otp_sync(self, user, code: str, request=None) -> None:
        """发送 6 位邮件 OTP。仅 dev 在未配 SMTP 时记录明文日志。"""
        body = (
            f"<h2>您的 InnovOS 邮箱验证码</h2>"
            f"<p>验证码：<b>{code}</b></p>"
            f"<p>10 分钟内有效，请勿泄露给他人。</p>"
        )
        if not self.host:
            if settings.ENVIRONMENT == "production" and not settings.EMAIL_OTP_SOFT_FAIL:
                raise EmailUnavailable()
            if settings.ENVIRONMENT == "development":
                logger.info(
                    "[DEV OTP] email=%s code=%s ttl=%ss",
                    user.email, code, settings.OTP_TTL_SECONDS,
                )
                return
            logger.warning("SMTP_HOST 未配置，跳过邮件发送 to=%s", user.email)
            return
        self._send(user.email, "InnovOS 邮箱验证码", body)


email_service = EmailService()