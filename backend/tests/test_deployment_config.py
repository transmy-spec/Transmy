import json
import tomllib
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = import_module(
    "migrations.versions.20260801_0021_configure_seeded_oidc_issuer"
)


def test_seeded_account_migration_uses_configured_oidc_issuer() -> None:
    settings = SimpleNamespace(oidc_issuer="https://identity.example.test/realms/custom")
    with patch.object(MIGRATION, "get_settings", return_value=settings):
        assert MIGRATION._configured_issuer() == settings.oidc_issuer


def test_seeded_account_migration_downgrade_preserves_working_issuer() -> None:
    with patch.object(MIGRATION.op, "get_bind") as get_bind:
        MIGRATION.downgrade()
    get_bind.assert_not_called()


def test_keycloak_realm_uses_deployment_environment() -> None:
    realm = json.loads(
        (REPOSITORY_ROOT / "infrastructure/keycloak/transmissions-realm.json").read_text()
    )
    client = next(item for item in realm["clients"] if item["clientId"] == "transmissions-web")

    assert client["secret"] == "${OIDC_CLIENT_SECRET}"
    assert client["redirectUris"] == ["${APP_PUBLIC_URL}/auth/callback"]
    assert client["webOrigins"] == ["${APP_PUBLIC_URL}"]
    assert client["attributes"]["post.logout.redirect.uris"] == "${APP_PUBLIC_URL}/*"

    compose = (REPOSITORY_ROOT / "compose.yaml").read_text()
    keycloak_environment = compose.split("  keycloak:\n", 1)[1].split(
        "  postgres-keycloak:\n", 1
    )[0]
    assert "APP_PUBLIC_URL: ${APP_PUBLIC_URL:-https://localhost}" in keycloak_environment
    assert "OIDC_CLIENT_SECRET: ${OIDC_CLIENT_SECRET:?" in keycloak_environment
    assert "APP_PUBLIC_URL must not have a trailing slash" in keycloak_environment

    migrate_environment = compose.split("  migrate:\n", 1)[1].split(
        "  postgres-app:\n", 1
    )[0]
    assert (
        "APP_OIDC_ISSUER: ${APP_PUBLIC_URL:-https://localhost}/oidc/realms/transmissions"
        in migrate_environment
    )


def test_httpx_is_an_application_dependency() -> None:
    with (REPOSITORY_ROOT / "backend/pyproject.toml").open("rb") as project_file:
        project = tomllib.load(project_file)

    assert any(item.startswith("httpx") for item in project["project"]["dependencies"])
