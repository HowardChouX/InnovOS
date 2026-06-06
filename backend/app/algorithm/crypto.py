"""
API Key 加密工具

使用 AES-256 (Fernet) 加密存储 API Key。
密钥从环境变量 INNOVOS_ENCRYPT_KEY 读取，代码中不硬编码。
"""

import os
from cryptography.fernet import Fernet

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    key = os.getenv("INNOVOS_ENCRYPT_KEY")
    if not key:
        raise RuntimeError(
            "未设置 INNOVOS_ENCRYPT_KEY 环境变量\n"
            "请执行: export INNOVOS_ENCRYPT_KEY=$(python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")"
        )
    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_key(plain_text: str) -> str:
    """加密 API Key"""
    return _get_fernet().encrypt(plain_text.encode()).decode()


def decrypt_key(cipher_text: str) -> str:
    """解密 API Key"""
    return _get_fernet().decrypt(cipher_text.encode()).decode()
