import json
import tomllib
from pathlib import Path

from app.config import oidc_issuer_for_public_url

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_oidc_issuer_uses_configured_public_url() -> None:
    assert (
        oidc_issuer_for_public_url("https://transmissions.example.test:8443/")
        == "https://transmissions.example.test:8443/oidc/realms/transmissions"
    )


def test_keycloak_realm_uses_compose_environment() -> None:
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


def test_httpx_is_an_application_dependency() -> None:
    with (REPOSITORY_ROOT / "backend/pyproject.toml").open("rb") as project_file:
        project = tomllib.load(project_file)

    assert any(item.startswith("httpx") for item in project["project"]["dependencies"])
