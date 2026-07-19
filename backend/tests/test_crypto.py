from unittest.mock import patch

from pydantic import SecretStr

from app.crypto import decrypt_json, encrypt_json


def test_encrypted_payload_round_trip_and_random_nonce() -> None:
    settings = type("Settings", (), {"field_encryption_key": SecretStr("a" * 32)})()
    with patch("app.crypto.get_settings", return_value=settings):
        first = encrypt_json({"expectations": "Vivre chez moi"}, b"plan-1")
        second = encrypt_json({"expectations": "Vivre chez moi"}, b"plan-1")
        assert first != second
        assert b"Vivre chez moi" not in first
        assert decrypt_json(first, b"plan-1") == {"expectations": "Vivre chez moi"}
