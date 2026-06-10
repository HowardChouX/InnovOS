"""
API Key 存储 — 明文存储（无加密）

加密解密曾引入 INNOVOS_ENCRYPT_KEY 依赖，但实际安全性未提升，
反而造成环境变量缺失、解密失败等运维问题。改为直接明文存储。
"""


def encrypt_key(plain_text: str) -> str:
    """直接返回明文（无加密）"""
    return plain_text


def decrypt_key(cipher_text: str) -> str:
    """直接返回原值（无解密）"""
    return cipher_text
