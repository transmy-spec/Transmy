from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.database import engine
from app.keycloak_admin import KeycloakProvisioningError, reset_user_password
from app.security import token_hash

router = APIRouter(prefix="/api/v1/account-activation", tags=["account activation"])
TICKET_QUERY = text(
    """
    SELECT a.id,a.user_id,a.purpose,a.expires_at,u.username,u.display_name,u.subject
    FROM auth_session.account_activation a
    JOIN app.user_account u ON u.id=a.user_id
    WHERE a.token_hash=:token_hash AND a.expires_at>now()
      AND a.consumed_at IS NULL AND a.revoked_at IS NULL
    """
)
LOCKED_TICKET_QUERY = text(
    """
    SELECT a.id,a.user_id,a.purpose,a.expires_at,u.username,u.display_name,u.subject
    FROM auth_session.account_activation a
    JOIN app.user_account u ON u.id=a.user_id
    WHERE a.token_hash=:token_hash AND a.expires_at>now()
      AND a.consumed_at IS NULL AND a.revoked_at IS NULL
    FOR UPDATE
    """
)


class ActivationTokenInput(BaseModel):
    token: SecretStr


class CompleteActivationInput(ActivationTokenInput):
    password: SecretStr = Field(min_length=12, max_length=128)


class ActivationDetails(BaseModel):
    username: str
    display_name: str
    purpose: Literal["admin_bootstrap", "admin_reset", "user_invitation"]
    expires_at: str


def _ticket(connection: Connection, token: str, *, lock: bool = False) -> Any:
    return connection.execute(
        LOCKED_TICKET_QUERY if lock else TICKET_QUERY,
        {"token_hash": token_hash(token)},
    ).mappings().first()


@router.post("/inspect")
def inspect_activation(payload: ActivationTokenInput) -> ActivationDetails:
    with engine.connect() as connection:
        ticket = _ticket(connection, payload.token.get_secret_value())
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "activation_invalid_or_expired")
    return ActivationDetails(
        username=ticket["username"],
        display_name=ticket["display_name"],
        purpose=ticket["purpose"],
        expires_at=ticket["expires_at"].isoformat(),
    )


@router.post("/complete", status_code=status.HTTP_204_NO_CONTENT)
def complete_activation(payload: CompleteActivationInput) -> None:
    with engine.begin() as connection:
        ticket = _ticket(connection, payload.token.get_secret_value(), lock=True)
        if not ticket:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "activation_invalid_or_expired")
        try:
            reset_user_password(UUID(ticket["subject"]), payload.password.get_secret_value())
        except KeycloakProvisioningError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "identity_provider_unavailable"
            ) from error
        connection.execute(
            text(
                """
                UPDATE auth_session.account_activation SET consumed_at=now() WHERE id=:id;
                UPDATE app.user_account SET status='active',
                  authorization_version=authorization_version+1 WHERE id=:user_id;
                DELETE FROM auth_session.web_session WHERE user_id=:user_id;
                INSERT INTO audit.event
                  (organization_id,actor_user_id,event_type,target_type,target_id,metadata)
                SELECT organization_id,id,'account.activation_completed','user',id,
                  jsonb_build_object('purpose',:purpose)
                FROM app.user_account WHERE id=:user_id;
                """
            ),
            {"id": ticket["id"], "user_id": ticket["user_id"], "purpose": ticket["purpose"]},
        )
