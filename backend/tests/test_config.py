import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_localhost() -> None:
    with pytest.raises(ValidationError):
        Settings(
            env="production",
            public_url="https://localhost",
            database_password="a" * 40,
        )


def test_production_rejects_short_password() -> None:
    with pytest.raises(ValidationError):
        Settings(
            env="production",
            public_url="https://transmissions.example.test",
            database_password="too-short",
        )
