import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.security import random_token, token_hash

ADMIN_SUBJECT = "11111111-1111-4111-8111-111111111111"


def issue(purpose: str) -> str:
    if purpose not in {"admin_bootstrap", "admin_reset"}:
        raise ValueError("invalid activation purpose")
    token = random_token(48)
    expires_at = datetime.now(UTC) + timedelta(hours=2)
    with engine.begin() as connection:
        admin = connection.execute(
            text(
                "SELECT id,organization_id FROM app.user_account "
                "WHERE subject=:subject AND username='admin'"
            ),
            {"subject": ADMIN_SUBJECT},
        ).mappings().one()
        connection.execute(
            text(
                """
                UPDATE auth_session.account_activation SET revoked_at=now()
                WHERE user_id=:user_id AND consumed_at IS NULL AND revoked_at IS NULL;
                DELETE FROM auth_session.web_session WHERE user_id=:user_id;
                UPDATE app.user_account SET status='invited',
                  authorization_version=authorization_version+1 WHERE id=:user_id;
                INSERT INTO auth_session.account_activation
                  (id,user_id,token_hash,purpose,expires_at)
                VALUES (:id,:user_id,:token_hash,:purpose,:expires_at);
                INSERT INTO audit.event
                  (organization_id,actor_user_id,event_type,target_type,target_id,metadata)
                VALUES (:organization_id,:user_id,'account.activation_issued','user',:user_id,
                  jsonb_build_object('purpose',:purpose,'expires_at',:expires_at));
                """
            ),
            {
                "id": uuid4(),
                "user_id": admin["id"],
                "organization_id": admin["organization_id"],
                "token_hash": token_hash(token),
                "purpose": purpose,
                "expires_at": expires_at,
            },
        )
    return f"{str(get_settings().public_url).rstrip('/')}/#activation={token}"


if __name__ == "__main__":
    print(issue(sys.argv[1] if len(sys.argv) == 2 else "admin_reset"))
