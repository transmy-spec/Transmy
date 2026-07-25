from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        case_sensitive=False,
        extra="ignore",
    )

    env: Literal["development", "test", "production"] = "development"
    public_url: AnyHttpUrl = AnyHttpUrl("https://localhost")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "transmissions"
    database_user: str = "transmissions_app"
    database_password: SecretStr

    oidc_issuer: str = "https://localhost/oidc/realms/transmissions"
    oidc_authorization_url: str = (
        "https://localhost/oidc/realms/transmissions/protocol/openid-connect/auth"
    )
    oidc_token_url: str = (
        "http://keycloak:8080/oidc/realms/transmissions/protocol/openid-connect/token"  # noqa: S105
    )
    oidc_jwks_url: str = (
        "http://keycloak:8080/oidc/realms/transmissions/protocol/openid-connect/certs"
    )
    oidc_end_session_url: str = (
        "https://localhost/oidc/realms/transmissions/protocol/openid-connect/logout"
    )
    oidc_client_id: str = "transmissions-web"
    oidc_client_secret: SecretStr = SecretStr("development-client-secret")
    keycloak_provisioning_client_id: str = "transmissions-provisioning"
    keycloak_provisioning_client_secret: SecretStr = SecretStr(
        "local-provisioning-client-secret-2026"
    )
    session_secret: SecretStr = SecretStr("development-session-secret")
    field_encryption_key: SecretStr = SecretStr("development-field-encryption-key")
    clamav_host: str = "clamav"
    clamav_port: int = Field(default=3310, ge=1, le=65535)
    integration_allowed_hosts: str = "host.docker.internal"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=self.database_password.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        ).render_as_string(hide_password=False)

    @model_validator(mode="after")
    def reject_development_defaults_in_production(self) -> "Settings":
        if self.env == "production":
            if self.public_url.host == "localhost":
                raise ValueError("APP_PUBLIC_URL cannot use localhost in production")
            if len(self.database_password.get_secret_value()) < 32:
                raise ValueError("APP_DATABASE_PASSWORD must have at least 32 characters")
            if len(self.session_secret.get_secret_value()) < 32:
                raise ValueError("APP_SESSION_SECRET must have at least 32 characters")
            if len(self.field_encryption_key.get_secret_value()) < 32:
                raise ValueError("APP_FIELD_ENCRYPTION_KEY must have at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
