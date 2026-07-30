"""
TDD 测试套件: ApiKeyCipher (AES-256-GCM)

覆盖:
1. 主密钥格式校验(base64url、长度)
2. AES-GCM 加密 round-trip
3. 每次 nonce 不同
4. AAD 绑定(provider_id / key_id 变化导致解密失败)
5. ciphertext 篡改 → InvalidTag
6. HMAC 指纹稳定(同明文 → 同 fingerprint)
7. 错误信息不泄漏明文/密文/nonce
"""

from __future__ import annotations

import base64
import os

import pytest


# ── Fixture: 生成 32 字节随机主密钥(base64url 编码) ──


@pytest.fixture
def master_key_b64() -> str:
    raw = os.urandom(32)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


@pytest.fixture
def cipher(master_key_b64, monkeypatch):
    monkeypatch.setenv("INNOVOS_ENCRYPT_KEY", master_key_b64)
    from app.core.key_crypto import ApiKeyCipher, load_api_key_cipher

    return load_api_key_cipher()


# ── 主密钥格式校验 ──


class TestMasterKeyValidation:
    def test_missing_master_key_raises(self, monkeypatch):
        """缺失 INNOVOS_ENCRYPT_KEY 必须 fail fast,不允许默认值。"""
        monkeypatch.delenv("INNOVOS_ENCRYPT_KEY", raising=False)
        from app.core.key_crypto import load_api_key_cipher

        with pytest.raises(RuntimeError, match="INNOVOS_ENCRYPT_KEY"):
            load_api_key_cipher()

    def test_wrong_length_master_key_raises(self, monkeypatch):
        """长度不是 32 字节必须失败。"""
        bad = base64.urlsafe_b64encode(os.urandom(16)).decode("ascii").rstrip("=")
        monkeypatch.setenv("INNOVOS_ENCRYPT_KEY", bad)
        from app.core.key_crypto import load_api_key_cipher

        with pytest.raises(RuntimeError, match="32"):
            load_api_key_cipher()

    def test_invalid_base64_raises(self, monkeypatch):
        monkeypatch.setenv("INNOVOS_ENCRYPT_KEY", "not-base64-!!!")
        from app.core.key_crypto import load_api_key_cipher

        with pytest.raises(RuntimeError):
            load_api_key_cipher()


# ── 加密 round-trip ──


class TestEncryptDecryptRoundTrip:
    def test_round_trip_recovers_plaintext(self, cipher):
        plaintext = "sk-test-secret-1234567890"
        encrypted = cipher.encrypt(plaintext=plaintext, provider_id="openai", key_id=1)
        recovered = cipher.decrypt(
            ciphertext=encrypted.ciphertext,
            nonce=encrypted.nonce,
            encryption_version=encrypted.encryption_version,
            provider_id="openai",
            key_id=1,
        )
        assert recovered == plaintext

    def test_encrypt_produces_nonce_12_bytes(self, cipher):
        encrypted = cipher.encrypt(plaintext="any-key", provider_id="p1", key_id=1)
        assert len(encrypted.nonce) == 12

    def test_encrypt_twice_yields_different_nonces_and_ciphertexts(self, cipher):
        """同一明文两次加密,nonce 必须不同 → 密文也不同。"""
        plaintext = "sk-abc"
        e1 = cipher.encrypt(plaintext=plaintext, provider_id="p1", key_id=1)
        e2 = cipher.encrypt(plaintext=plaintext, provider_id="p1", key_id=1)
        assert e1.nonce != e2.nonce
        assert e1.ciphertext != e2.ciphertext
        # 但两次都能解出原值
        assert cipher.decrypt(
            ciphertext=e1.ciphertext, nonce=e1.nonce,
            encryption_version=1, provider_id="p1", key_id=1,
        ) == plaintext
        assert cipher.decrypt(
            ciphertext=e2.ciphertext, nonce=e2.nonce,
            encryption_version=1, provider_id="p1", key_id=1,
        ) == plaintext


# ── AAD 绑定 ──


class TestAADBinding:
    def test_decrypt_with_wrong_provider_id_fails(self, cipher):
        """provider_id 错误 → AAD 不匹配 → 解密失败。"""
        encrypted = cipher.encrypt(plaintext="secret", provider_id="openai", key_id=1)
        with pytest.raises(Exception):
            cipher.decrypt(
                ciphertext=encrypted.ciphertext, nonce=encrypted.nonce,
                encryption_version=1, provider_id="anthropic", key_id=1,
            )

    def test_decrypt_with_wrong_key_id_fails(self, cipher):
        """key_id 错误 → AAD 不匹配 → 解密失败。"""
        encrypted = cipher.encrypt(plaintext="secret", provider_id="p1", key_id=1)
        with pytest.raises(Exception):
            cipher.decrypt(
                ciphertext=encrypted.ciphertext, nonce=encrypted.nonce,
                encryption_version=1, provider_id="p1", key_id=2,
            )

    def test_ciphertext_tamper_fails(self, cipher):
        """密文被改 1 字节 → AES-GCM 认证失败。"""
        encrypted = cipher.encrypt(plaintext="secret", provider_id="p1", key_id=1)
        tampered = bytearray(encrypted.ciphertext)
        tampered[0] ^= 0xFF
        with pytest.raises(Exception):
            cipher.decrypt(
                ciphertext=bytes(tampered), nonce=encrypted.nonce,
                encryption_version=1, provider_id="p1", key_id=1,
            )


# ── HMAC 指纹 ──


class TestFingerprint:
    def test_fingerprint_is_stable_for_same_plaintext(self, cipher):
        """同明文 → 同 fingerprint。"""
        f1 = cipher.fingerprint("sk-stable")
        f2 = cipher.fingerprint("sk-stable")
        assert f1 == f2
        assert len(f1) == 32

    def test_fingerprint_differs_for_different_plaintexts(self, cipher):
        f1 = cipher.fingerprint("sk-aaa")
        f2 = cipher.fingerprint("sk-bbb")
        assert f1 != f2

    def test_fingerprint_does_not_equal_plaintext_hash(self, cipher):
        """指纹应该是 HMAC,不能是裸 SHA256(防止低熵字典攻击)。"""
        f = cipher.fingerprint("sk-test")
        # 不应该是 plaintext 的 sha256,而是 32 字节 HMAC
        import hashlib
        plain_sha = hashlib.sha256(b"sk-test").digest()
        assert f != plain_sha


# ── 错误信息不泄漏 ──


class TestErrorMessagesDoNotLeak:
    def test_decrypt_failure_message_does_not_contain_plaintext(self, cipher):
        plaintext = "super-secret-marker-XYZ-12345"
        encrypted = cipher.encrypt(plaintext=plaintext, provider_id="p1", key_id=1)
        # 篡改密文触发解密失败
        tampered = bytearray(encrypted.ciphertext)
        tampered[5] ^= 0x01
        with pytest.raises(Exception) as exc_info:
            cipher.decrypt(
                ciphertext=bytes(tampered), nonce=encrypted.nonce,
                encryption_version=1, provider_id="p1", key_id=1,
            )
        # 异常信息中不能含明文标记
        assert "super-secret-marker-XYZ-12345" not in str(exc_info.value)
        # 也不能含完整 ciphertext 或 nonce 的 hex/base64 表示
        full_hex = encrypted.ciphertext.hex()
        assert full_hex not in str(exc_info.value)