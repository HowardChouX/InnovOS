"""
API Key 加密工具

使用 AES-256 (Fernet) 加密存储 API Key。
密钥从环境变量 INNOVOS_ENCRYPT_KEY 读取，代码中不硬编码。

生成密钥: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
设置环境变量: export INNOVOS_ENCRYPT_KEY=<生成的密钥>
"""

import os
from cryptography.fernet import Fernet, InvalidToken

_encrypt_key = os.getenv("INNOVOS_ENCRYPT_KEY")

if not _encrypt_key:
    raise RuntimeError(
        "未设置 INNOVOS_ENCRYPT_KEY 环境变量\n"
        "请执行: export INNOVOS_ENCRYPT_KEY=$(python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")"
    )

_fernet = Fernet(_encrypt_key.encode() if isinstance(_encrypt_key, str) else _encrypt_key)


def encrypt_key(plain_text: str) -> str:
    """加密 API Key"""
    return _fernet.encrypt(plain_text.encode()).decode()


def decrypt_key(cipher_text: str) -> str:
    """解密 API Key"""
    try:
        return _fernet.decrypt(cipher_text.encode()).decode()
    except InvalidToken:
        # 兼容旧数据（未加密的 Key）
        return cipher_text
