import hashlib
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings


def _key() -> bytes:
    secret = get_settings().field_encryption_key.get_secret_value().encode()
    return hashlib.sha256(secret).digest()


def encrypt_json(value: dict[str, Any], associated_data: bytes) -> bytes:
    nonce = os.urandom(12)
    plaintext = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return nonce + AESGCM(_key()).encrypt(nonce, plaintext, associated_data)


def decrypt_json(value: bytes, associated_data: bytes) -> dict[str, Any]:
    plaintext = AESGCM(_key()).decrypt(value[:12], value[12:], associated_data)
    result: dict[str, Any] = json.loads(plaintext)
    return result
