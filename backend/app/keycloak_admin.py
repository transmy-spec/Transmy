from uuid import UUID

import httpx

from app.config import get_settings


class KeycloakProvisioningError(RuntimeError):
    pass


class KeycloakUserConflictError(KeycloakProvisioningError):
    pass


def _access_token() -> str:
    settings = get_settings()
    try:
        token_response = httpx.post(
            settings.oidc_token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.keycloak_provisioning_client_id,
                "client_secret": settings.keycloak_provisioning_client_secret.get_secret_value(),
            },
            timeout=10,
        )
        token_response.raise_for_status()
        return str(token_response.json()["access_token"])
    except (httpx.HTTPError, KeyError) as error:
        raise KeycloakProvisioningError from error


def _users_url(suffix: str = "") -> str:
    return f"http://keycloak:8080/oidc/admin/realms/transmissions/users{suffix}"


def create_user(username: str, email: str, display_name: str) -> UUID:
    names = display_name.strip().split(maxsplit=1)
    payload = {
        "username": username,
        "email": email,
        "firstName": names[0],
        "lastName": names[1] if len(names) == 2 else "",
        "enabled": True,
        "emailVerified": False,
    }
    try:
        response = httpx.post(
            _users_url(),
            headers={"Authorization": f"Bearer {_access_token()}"},
            json=payload,
            timeout=10,
        )
        if response.status_code == 409:
            raise KeycloakUserConflictError
        response.raise_for_status()
        return UUID(response.headers["Location"].rstrip("/").rsplit("/", 1)[-1])
    except KeycloakUserConflictError:
        raise
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise KeycloakProvisioningError from error


def delete_user(user_id: UUID) -> None:
    try:
        response = httpx.delete(
            _users_url(f"/{user_id}"),
            headers={"Authorization": f"Bearer {_access_token()}"},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise KeycloakProvisioningError from error


def reset_user_password(user_id: UUID, password: str) -> None:
    try:
        response = httpx.put(
            _users_url(f"/{user_id}/reset-password"),
            headers={"Authorization": f"Bearer {_access_token()}"},
            json={"type": "password", "value": password, "temporary": False},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise KeycloakProvisioningError from error
