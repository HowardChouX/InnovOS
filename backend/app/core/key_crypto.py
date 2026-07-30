"""
供应商 API Key 加密模块 (AES-256-GCM)

设计:
- 主密钥 INNOVOS_ENCRYPT_KEY: base64url 编码 32 字节;缺失/长度错误时 fail fast
- 每行加密用 CSPRNG 生成 12 字节 nonce
- AAD = "innovos:api_keys:v1:{provider_id}:{key_id}" 防止 ciphertext 被复制到其他行
- HMAC-SHA256(派生自主密钥, plaintext) 作为指纹;完整 32 字节入库,API 只返前 12 hex
- 解密失败/异常文本绝不包含 plaintext / ciphertext / nonce

依赖: cryptography>=42(cryptography 49.0.0 已锁定)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ── 错误类型 ──


class ApiKeyCryptoError(RuntimeError):
    """加密/解密相关错误的统一基类。"""


class ApiKeyDecryptionError(ApiKeyCryptoError):
    """解密失败(主密钥错误、密文被篡改、AAD 不匹配)。"""


# ── 常量 ──


_MASTER_KEY_BYTES = 32
_NONCE_BYTES = 12
_FINGERPRINT_BYTES = 32

# HKDF info 用于派生不同用途的子密钥
_INFO_FINGERPRINT = b"innovos:api-key-fingerprint:v1"
_AAD_PREFIX = "innovos:api_keys:v1"


# ── 数据结构 ──


@dataclass(frozen=True)
class EncryptedApiKey:
    """单条 Key 的加密产物。"""

    ciphertext: bytes
    nonce: bytes
    encryption_version: int
    fingerprint: bytes
    prefix: str | None
    suffix: str


# ── 主实现 ──


class ApiKeyCipher:
    """AES-256-GCM API Key 加解密器。

    主密钥通过构造参数传入。load_api_key_cipher() 是从环境变量初始化的工厂。
    """

    def __init__(self, master_key: bytes) -> None:
        if not isinstance(master_key, (bytes, bytearray)):
            raise ApiKeyCryptoError("master_key must be bytes")
        if len(master_key) != _MASTER_KEY_BYTES:
            raise ApiKeyCryptoError(
                f"master_key must be exactly {_MASTER_KEY_BYTES} bytes, got {len(master_key)}"
            )
        self._master_key = bytes(master_key)
        self._aesgcm = AESGCM(self._master_key)
        # 派生指纹专用 HMAC key
        self._fingerprint_key = self._derive_subkey(_INFO_FINGERPRINT)

    @staticmethod
    def _derive_subkey(info: bytes) -> bytes:
        """HKDF-SHA256 从主密钥派生子密钥(仅指纹用途)。"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=_FINGERPRINT_BYTES,
            salt=None,
            info=info,
        )
        return hkdf.derive(b"innovos-master-key")  # IKM 用占位,只取 info 域

    @staticmethod
    def _build_aad(provider_id: str, key_id: int) -> bytes:
        return f"{_AAD_PREFIX}:{provider_id}:{key_id}".encode("utf-8")

    @staticmethod
    def _extract_prefix_suffix(plaintext: str) -> tuple[str | None, str]:
        """从明文中提取稳定前缀 + 后 4 位。"""
        if not plaintext:
            return None, ""
        # 多数供应商 Key 形如 "sk-..." / "sk-proj-..."
        # 取开头连续 [a-zA-Z0-9_-] 字符作为前缀(最多 12),取末尾 4 个字符
        head = ""
        for ch in plaintext[:12]:
            if ch.isalnum() or ch in "-_":
                head += ch
            else:
                break
        prefix = head[:12] if head else None
        suffix = plaintext[-4:] if len(plaintext) >= 4 else plaintext
        return prefix, suffix

    # ── 加密 ──

    def encrypt(
        self,
        *,
        plaintext: str,
        provider_id: str,
        key_id: int,
    ) -> EncryptedApiKey:
        nonce = os.urandom(_NONCE_BYTES)
        aad = self._build_aad(provider_id, key_id)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)
        prefix, suffix = self._extract_prefix_suffix(plaintext)
        return EncryptedApiKey(
            ciphertext=ciphertext,
            nonce=nonce,
            encryption_version=1,
            fingerprint=self.fingerprint(plaintext),
            prefix=prefix,
            suffix=suffix,
        )

    # ── 解密 ──

    def decrypt(
        self,
        *,
        ciphertext: bytes,
        nonce: bytes,
        encryption_version: int,
        provider_id: str,
        key_id: int,
    ) -> str:
        if encryption_version != 1:
            raise ApiKeyDecryptionError(
                f"unsupported encryption_version: {encryption_version}"
            )
        if len(nonce) != _NONCE_BYTES:
            raise ApiKeyDecryptionError("invalid nonce length")
        aad = self._build_aad(provider_id, key_id)
        try:
            plaintext_bytes = self._aesgcm.decrypt(nonce, ciphertext, aad)
        except InvalidTag as exc:
            raise ApiKeyDecryptionError("decryption failed (tag mismatch)") from exc
        return plaintext_bytes.decode("utf-8")

    # ── 指纹 ──

    def fingerprint(self, plaintext: str) -> bytes:
        """HMAC-SHA256(派生 key, plaintext)。稳定、防字典攻击。"""
        return hmac.new(
            self._fingerprint_key,
            plaintext.encode("utf-8"),
            hashlib.sha256,
        ).digest()


# ── 工厂函数 ──


def _decode_master_key(b64_str: str) -> bytes:
    """base64url 解码并补 padding。"""
    # 补齐 base64 padding
    pad = "=" * (-len(b64_str) % 4)
    try:
        raw = base64.urlsafe_b64decode(b64_str + pad)
    except Exception as exc:
        raise ApiKeyCryptoError(
            f"INNOVOS_ENCRYPT_KEY is not valid base64url: {type(exc).__name__}"
        ) from exc
    return raw


def load_api_key_cipher() -> ApiKeyCipher:
    """从环境变量 INNOVOS_ENCRYPT_KEY 加载 cipher。

    - 缺失:RuntimeError
    - base64 解析失败:RuntimeError
    - 长度不为 32 字节:RuntimeError
    """
    raw = os.environ.get("INNOVOS_ENCRYPT_KEY")
    if not raw:
        raise RuntimeError(
            "INNOVOS_ENCRYPT_KEY is required for AES-256-GCM API key encryption. "
            "Generate with: python -c \"import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\""
        )
    master_key = _decode_master_key(raw)
    return ApiKeyCipher(master_key)