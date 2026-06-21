"""
API Key 存储 — AES-256 加密（Fernet）
"""
import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


def _get_cipher() -> Fernet:
    """获取或创建加密器，从 INNOVOS_ENCRYPT_KEY 派生密钥"""
    raw_key = os.getenv("INNOVOS_ENCRYPT_KEY", "")
    if not raw_key:
        logger.warning("INNOVOS_ENCRYPT_KEY 未设置，使用开发默认密钥")
        raw_key = "dev-default-key-change-in-production!"
    # 使用 PBKDF2 派生 32 字节密钥
    salt = b"innovos-fixed-salt"
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    key = base64.urlsafe_b64encode(kdf.derive(raw_key.encode()))
    return Fernet(key)


def encrypt_key(plain_text: str) -> str:
    """加密 API Key"""
    if not plain_text:
        return ""
    cipher = _get_cipher()
    return cipher.encrypt(plain_text.encode()).decode()


def decrypt_key(cipher_text: str) -> str:
    """解密 API Key — 兼容旧明文数据"""
    if not cipher_text:
        return ""
    try:
        cipher = _get_cipher()
        return cipher.decrypt(cipher_text.encode()).decode()
    except Exception:
        # 兼容旧数据：如果是未加密的明文则直接返回
        # （e.g. 数据库迁移前存储的明文 API keys）
        if cipher_text and not cipher_text.startswith("gAAAAA"):  # Fernet token 前缀
            logger.debug("解密失败，按明文兼容模式返回")
            return cipher_text
        logger.error("解密失败且非明文格式")
        return ""
