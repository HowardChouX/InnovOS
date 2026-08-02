"""
应用配置 — Pydantic Settings，从环境变量读取。
替代散落在各模块的 os.getenv() 调用。
"""

from __future__ import annotations

import secrets
import warnings
from typing import Annotated, Any, Literal

from pydantic import (
    AliasChoices,
    AnyUrl,
    BeforeValidator,
    Field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
        populate_by_name=True,
    )

    # ── 应用基础 ──
    PROJECT_NAME: str = "InnovOS"
    API_V1_STR: str = "/api"
    ENVIRONMENT: Literal["development", "production"] = Field(
        default="development", validation_alias=AliasChoices("ENVIRONMENT", "ENV")
    )
    BACKEND_CORS_ORIGINS: Annotated[list[AnyUrl] | str, BeforeValidator(parse_cors)] = []

    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS]

    # ── 认证 ──
    SECRET_KEY: str = Field(
        default=secrets.token_urlsafe(32), validation_alias=AliasChoices("INNOVOS_JWT_SECRET", "SECRET_KEY")
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ── 数据库 ──
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "innovos"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "innovos"
    DATABASE_URL: str | None = None

    # ── 管理员 ──
    # 超级用户由开发者手动在数据库中设置（UPDATE users SET is_superuser=true ...），
    # 不再通过环境变量种子化。

    # ── S3 / MinIO ──
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "innovos-files"
    S3_REGION: str = "us-east-1"
    PUBLIC_URL: str = "http://localhost"

    # ── CNIPR 专利API（备用）──
    CNIPR_CLIENT_ID: str = ""
    CNIPR_CLIENT_SECRET: str = ""
    CNIPR_USERNAME: str = ""
    CNIPR_PASSWORD: str = ""

    # ── PatentHub 专利API（主数据源）──
    PATENT_HUB_TOKEN: str = ""

    # ── 邮件（SMTP）──
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@innovos.local"
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False

    # ── Email OTP 验证 ──
    OTP_TTL_SECONDS: int = 600
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN: int = 60
    OTP_PEPPER: str = Field(default="", validation_alias=AliasChoices("INNOVOS_OTP_PEPPER", "OTP_PEPPER"))
    EMAIL_OTP_SOFT_FAIL: bool = False

    # ── 阿里云号码认证服务（参数与官方 SDK 示例一致）──
    SMS_SCHEME_NAME: str = "一竖光年"
    SMS_SIGN_NAME: str = "速通互联验证码"
    SMS_REGISTER_TEMPLATE_CODE: str = "100001"
    SMS_RESET_PASSWORD_TEMPLATE_CODE: str = "100003"
    SMS_COUNTRY_CODE: str = "86"
    SMS_CODE_LENGTH: int = 6
    SMS_CODE_VALID_TIME: int = 300        # 秒
    SMS_CODE_VALID_MIN: int = 5           # 分钟（模板 ${min} 变量）
    SMS_RESEND_INTERVAL: int = 60         # 秒
    SMS_CODE_TYPE: int = 1                # 1=纯数字
    SMS_DUPLICATE_POLICY: int = 1         # 1=覆盖旧验证码
    SMS_AUTO_RETRY: int = 1               # 1=开启自动重试
    SMS_CASE_AUTH_POLICY: int = 1         # 1=不区分大小写
    SMS_ENDPOINT: str = "dypnsapi.aliyuncs.com"
    ALIBABA_CLOUD_ACCESS_KEY_ID: str = ""
    ALIBABA_CLOUD_ACCESS_KEY_SECRET: str = ""

    # ── Password reset session token ──
    # 独立 secret,避免和业务 JWT 共用导致 reset_token 泄露时影响会话安全。
    # 不配则回退到 SECRET_KEY。
    RESET_SESSION_JWT_SECRET: str = ""
    RESET_SESSION_JWT_AUDIENCE: str = "password-reset:consume"
    RESET_SESSION_TOKEN_TTL_SECONDS: int = 600

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value and value == "changethis":
            msg = f'The value of {var_name} is "changethis", for security, please change it.'
            if self.ENVIRONMENT == "development":
                warnings.warn(msg, stacklevel=1)
            else:
                raise ValueError(msg)

    @model_validator(mode="after")
    def _build_database_url(self) -> Settings:
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Settings:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        return self

    @model_validator(mode="after")
    def _enforce_production_settings(self) -> Settings:
        if self.ENVIRONMENT == "production":
            if not self.POSTGRES_PASSWORD:
                raise ValueError("POSTGRES_PASSWORD must be set in production")
            if not self.BACKEND_CORS_ORIGINS:
                raise ValueError(
                    "BACKEND_CORS_ORIGINS must be configured in production. "
                    "Set to ['https://yourdomain.com'] or configure nginx to handle CORS."
                )
            if not self.OTP_PEPPER:
                raise ValueError("OTP_PEPPER must be set in production")
        return self


settings = Settings()
