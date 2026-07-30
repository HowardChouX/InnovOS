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


# ── 邮件模板 ─────────────────────────────────────────────────
# 视觉风格参考：AipayOK 风格的灰白卡片 + Logo + 居中胶囊验证码
# 颜色取自 InnovOS 品牌（青→蓝渐变），但保持克制的灰底基调以提升阅读体验。

_BRAND_GRADIENT = "linear-gradient(90deg,#22d3ee 0%,#3b82f6 100%)"  # cyan-400 → blue-500
_CARD_BG = "#f4f5f7"
_CARD_SHADOW = "0 1px 3px rgba(0,0,0,0.04),0 1px 2px rgba(0,0,0,0.06)"


def _wrap_card(inner_html: str) -> str:
    """统一的外层容器 — 居中卡片,圆角,浅灰背景。"""
    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;color:#1f2937;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f4f5f7;padding:40px 16px;">
    <tr><td align="center">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="480" style="max-width:480px;background:#ffffff;border-radius:12px;box-shadow:{_CARD_SHADOW};">
        <tr><td style="padding:40px 36px;">
{inner_html}
        </td></tr>
      </table>
      <p style="margin:24px 0 0;color:#9ca3af;font-size:12px;">© InnovOS · 智融创新操作系统</p>
    </td></tr>
  </table>
</body>
</html>
"""


def _brand_logo() -> str:
    """顶部品牌名 — 大字、渐变填充。"""
    return f'''\
      <div style="font-size:28px;font-weight:700;line-height:1;margin:0 0 24px;
                  background:{_BRAND_GRADIENT};-webkit-background-clip:text;
                  background-clip:text;color:transparent;-webkit-text-fill-color:transparent;
                  letter-spacing:-0.5px;">
        InnovOS
      </div>
'''


def _code_pill(code: str) -> str:
    """居中胶囊状验证码 — 等宽风格、字间距大。"""
    return f'''\
      <div style="margin:32px 0;padding:24px 16px;background:{_CARD_BG};border-radius:12px;
                  text-align:center;">
        <div style="font-family:'SF Mono','Menlo','Consolas','Courier New',monospace;
                    font-size:36px;font-weight:600;letter-spacing:8px;color:#111827;
                    line-height:1.2;">
          {code}
        </div>
      </div>
'''


def _footer_note(ttl_minutes: int = 10) -> str:
    """底部辅助 + 免责文字。"""
    return f'''\
      <p style="margin:0 0 8px;color:#6b7280;font-size:13px;line-height:1.6;">
        验证码 {ttl_minutes} 分钟内有效。请勿将验证码转发给任何人。
      </p>
      <p style="margin:0;color:#9ca3af;font-size:12px;line-height:1.6;">
        如果不是您本人操作，请忽略这封邮件。
      </p>
'''


def _action_button(label: str, url: str) -> str:
    """CTA 按钮 — 居中、渐变背景、白色文字。"""
    return f'''\
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:24px 0 8px;">
        <tr><td align="center">
          <a href="{url}" style="display:inline-block;padding:12px 32px;
                                   background:{_BRAND_GRADIENT};color:#ffffff;
                                   text-decoration:none;font-size:15px;font-weight:600;
                                   border-radius:8px;">
            {label}
          </a>
        </td></tr>
      </table>
'''


# ── 邮件服务类 ───────────────────────────────────────────────
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
        """发送邮箱验证邮件。

        链接走前端路由 /verify-email(而非 fastapi-users 默认的 /verify)。
        dev 模式 SMTP 未配置时,把 verify URL 打到日志(便于本地端到端调试)。
        """
        verify_url = f"{settings.PUBLIC_URL}/verify-email?token={token}"
        inner = (
            _brand_logo()
            + '<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#111827;">验证您的邮箱</h1>\n'
            + '<p style="margin:0 0 24px;color:#4b5563;font-size:14px;line-height:1.6;">'
              '请点击下方按钮完成邮箱验证,按钮 1 小时内有效。</p>\n'
            + _action_button("验证邮箱", verify_url)
            + f'<p style="margin:16px 0 0;color:#9ca3af;font-size:12px;line-height:1.6;'
              f'word-break:break-all;">如按钮无效,请复制链接:<br>{verify_url}</p>\n'
        )
        body = _wrap_card(inner)
        if not self.host:
            if settings.ENVIRONMENT == "development":
                logger.info(
                    "[DEV VERIFY] email=%s url=%s",
                    user.email, verify_url,
                )
                return
            logger.warning("SMTP_HOST 未配置，跳过邮箱验证邮件发送 to=%s", user.email)
            return
        self._send(user.email, "InnovOS 邮箱验证", body)

    def send_reset_password_email_sync(self, user, token: str, request=None) -> None:
        """发送密码重置邮件。

        链接走前端路由 /reset-password(已注册在 routes/index.tsx)。
        dev 模式 SMTP 未配置时,把 reset URL 打到日志(便于本地端到端调试)。
        """
        reset_url = f"{settings.PUBLIC_URL}/reset-password?token={token}"
        inner = (
            _brand_logo()
            + '<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#111827;">重置您的密码</h1>\n'
            + '<p style="margin:0 0 24px;color:#4b5563;font-size:14px;line-height:1.6;">'
              '您正在申请重置 InnovOS 账号密码。点击下方按钮设置新密码,链接 1 小时内有效。</p>\n'
            + _action_button("重置密码", reset_url)
            + f'<p style="margin:16px 0 0;color:#9ca3af;font-size:12px;line-height:1.6;'
              f'word-break:break-all;">如按钮无效,请复制链接:<br>{reset_url}</p>\n'
        )
        body = _wrap_card(inner)
        if not self.host:
            if settings.ENVIRONMENT == "development":
                logger.info(
                    "[DEV RESET] email=%s url=%s",
                    user.email, reset_url,
                )
                return
            logger.warning("SMTP_HOST 未配置，跳过密码重置邮件发送 to=%s", user.email)
            return
        self._send(user.email, "InnovOS 密码重置", body)

    def send_verification_otp_sync(self, user, code: str, request=None) -> None:
        """发送 6 位邮件 OTP。仅 dev 在未配 SMTP 时记录明文日志。"""
        ttl_min = settings.OTP_TTL_SECONDS // 60
        inner = (
            _brand_logo()
            + '<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#111827;">注册验证</h1>\n'
            + '<p style="margin:0 0 8px;color:#4b5563;font-size:14px;line-height:1.6;">'
              '您正在进行注册验证,请使用以下验证码完成操作。</p>\n'
            + _code_pill(code)
            + _footer_note(ttl_min)
        )
        body = _wrap_card(inner)
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

    def send_password_reset_otp_sync(self, user, code: str, request=None) -> None:
        """发送密码重置邮件 — 仅含 6 位验证码,无 URL。
        dev 模式 SMTP 未配置时,把验证码明文写日志。
        """
        ttl_min = settings.OTP_TTL_SECONDS // 60
        inner = (
            _brand_logo()
            + '<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#111827;">密码重置</h1>\n'
            + '<p style="margin:0 0 8px;color:#4b5563;font-size:14px;line-height:1.6;">'
              '您正在申请重置 InnovOS 账号密码,请使用以下验证码完成操作。</p>\n'
            + _code_pill(code)
            + _footer_note(ttl_min)
        )
        body = _wrap_card(inner)
        if not self.host:
            if settings.ENVIRONMENT == "production" and not settings.EMAIL_OTP_SOFT_FAIL:
                raise EmailUnavailable()
            if settings.ENVIRONMENT == "development":
                logger.info(
                    "[DEV RESET OTP] email=%s code=%s ttl=%ss",
                    user.email, code, settings.OTP_TTL_SECONDS,
                )
                return
            logger.warning("SMTP_HOST 未配置,跳过密码重置邮件发送 to=%s", user.email)
            return
        self._send(user.email, "InnovOS 密码重置验证码", body)


email_service = EmailService()