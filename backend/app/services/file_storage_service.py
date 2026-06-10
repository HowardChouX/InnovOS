"""
文件存储服务 — MinIO/S3 对象存储

使用 boto3 兼容 S3 API，支持 MinIO 和标准 S3。
配置通过环境变量注入（docker-compose 自动提供）。

用法：
  storage = FileStorageService()
  key = await storage.upload(user_id, "doc.pdf", content_bytes)
  url = await storage.get_download_url(key)
"""
from __future__ import annotations

import io
import os
import uuid
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class FileStorageService:
    """MinIO/S3 文件存储服务。

    配置（环境变量）：
        S3_ENDPOINT    — MinIO/S3 endpoint (e.g. http://minio:9000)
        S3_ACCESS_KEY  — Access key
        S3_SECRET_KEY  — Secret key
        S3_BUCKET      — Bucket name (default: innovos-files)
        S3_REGION      — Region (default: us-east-1)
        PUBLIC_URL     — Public URL prefix for generated URLs
    """

    def __init__(self):
        self._endpoint = os.getenv("S3_ENDPOINT", "")
        self._access_key = os.getenv("S3_ACCESS_KEY", "")
        self._secret_key = os.getenv("S3_SECRET_KEY", "")
        self._bucket = os.getenv("S3_BUCKET", "innovos-files")
        self._region = os.getenv("S3_REGION", "us-east-1")
        self._public_url = os.getenv("PUBLIC_URL", "").rstrip("/")
        self._client = None

    @property
    def enabled(self) -> bool:
        """检查 S3 是否已配置。"""
        return bool(self._endpoint and self._access_key and self._secret_key)

    @property
    def _s3(self):
        """懒加载 boto3 S3 客户端。"""
        if self._client is None:
            if not self.enabled:
                raise RuntimeError(
                    "S3 未配置: 需要设置 S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY"
                )
            import boto3
            from botocore.config import Config

            session = boto3.session.Session(
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
            )
            self._client = session.client(
                service_name="s3",
                endpoint_url=self._endpoint,
                region_name=self._region,
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=5,
                    read_timeout=30,
                    retries={"max_attempts": 3},
                ),
            )
            logger.info(f"S3 客户端已初始化: {self._endpoint} bucket={self._bucket}")
        return self._client

    def _object_key(self, user_id: int, filename: str) -> str:
        """生成 S3 对象键: knowledge/{user_id}/{uuid}_{filename}。"""
        safe_name = filename.replace("/", "_").replace("\\", "_")
        unique_id = uuid.uuid4().hex[:12]
        return f"knowledge/{user_id}/{unique_id}_{safe_name}"

    async def upload(
        self, user_id: int, filename: str, content: bytes
    ) -> Optional[str]:
        """上传文件到 MinIO/S3。

        Args:
            user_id: 用户 ID
            filename: 原始文件名
            content: 文件二进制内容

        Returns:
            S3 对象键 (用于后续下载/删除)，失败返回 None
        """
        if not self.enabled:
            logger.warning("S3 未配置，文件不会被持久化存储")
            return None

        key = self._object_key(user_id, filename)
        try:
            self._s3.upload_fileobj(
                io.BytesIO(content),
                self._bucket,
                key,
                ExtraArgs={"ContentType": self._guess_mime(filename)},
            )
            logger.info(f"文件已上传: {key} ({len(content)} bytes)")
            return key
        except Exception as e:
            logger.exception(f"文件上传失败: {e}")
            return None

    async def download(self, key: str) -> Optional[bytes]:
        """从 S3 下载文件内容。"""
        if not self.enabled:
            return None
        try:
            resp = self._s3.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except Exception as e:
            logger.exception(f"文件下载失败: key={key} {e}")
            return None

    async def delete(self, key: str) -> bool:
        """从 S3 删除文件。"""
        if not self.enabled:
            return False
        try:
            self._s3.delete_object(Bucket=self._bucket, Key=key)
            logger.info(f"文件已删除: {key}")
            return True
        except Exception as e:
            logger.exception(f"文件删除失败: key={key} {e}")
            return False

    async def get_download_url(self, key: str, expires: int = 3600) -> Optional[str]:
        """获取预签名下载 URL（带过期时间）。

        Args:
            key: S3 对象键
            expires: URL 过期时间（秒），默认 1 小时

        Returns:
            可访问的下载 URL，失败返回 None
        """
        if not self.enabled:
            return None
        try:
            url = self._s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires,
            )
            return url
        except Exception as e:
            logger.exception(f"生成下载 URL 失败: key={key} {e}")
            return None

    async def get_public_url(self, key: str) -> Optional[str]:
        """获取公开访问 URL（如果配置了 PUBLIC_URL + 公开 bucket）。

        Args:
            key: S3 对象键

        Returns:
            公开 URL（无过期），None 表示不可用
        """
        if not self._public_url:
            return None
        # 兼容 path-style 和 virtual-hosted-style
        return f"{self._public_url}/api/files/{key}"

    @staticmethod
    def _guess_mime(filename: str) -> str:
        """根据扩展名猜测 MIME 类型。"""
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".csv": "text/csv",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".zip": "application/zip",
        }
        return mime_map.get(ext, "application/octet-stream")


# 单例
file_storage = FileStorageService()
