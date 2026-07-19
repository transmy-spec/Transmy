# ruff: noqa: S310
import json
from typing import Annotated, Any, Literal
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.routers.people import _person_params
from app.security import SecurityContext, get_security_context, require_permission, verify_csrf

router = APIRouter(prefix="/api/v1/integrations", tags=["local integrations"])


class IntegrationInput(BaseModel):
    label: str = Field(min_length=2, max_length=100)
    endpoint_url: str = Field(min_length=8, max_length=500)
    status: Literal["disabled", "enabled"] = "disabled"


def _validate_endpoint(value: str) -> str:
    parsed = urlparse(value)
    allowed = {host.strip().lower() for host in get_settings().integration_allowed_hosts.split(",")}
    if parsed.scheme != "http" or not parsed.hostname or parsed.hostname.lower() not in allowed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "endpoint_not_allowed")
    if parsed.username or parsed.password or parsed.fragment:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_endpoint")
    return value


def _audit(connection: Any, context: SecurityContext, event: str, target: UUID) -> None:
    connection.execute(text("""INSERT INTO audit.event
      (organization_id,actor_user_id,event_type,target_type,target_id,metadata)
      VALUES (:organization_id,:user_id,:event,'integration',:target,CAST(:metadata AS jsonb))"""),
      {**_person_params(context), "event": event, "target": target,
       "metadata": json.dumps({})})


@router.get("")
def list_integrations(
    context: Annotated[SecurityContext, Depends(get_security_context)],
) -> dict[str, Any]:
    require_permission(context, "integration.read")
    with engine.connect() as connection:
        rows = connection.execute(text("""SELECT id,label,endpoint_url,status,last_tested_at,
          last_test_status,last_test_message,row_version FROM app.local_integration
          WHERE organization_id=:organization_id ORDER BY label"""),
          _person_params(context)).mappings()
        return {"items": [dict(row) for row in rows],
                "allowed_hosts": get_settings().integration_allowed_hosts.split(",")}


@router.post("", status_code=201)
def create_integration(payload: IntegrationInput, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "integration.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    integration_id = uuid4()
    endpoint = _validate_endpoint(payload.endpoint_url)
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO app.local_integration
          (id,organization_id,label,endpoint_url,status,created_by)
          VALUES (:id,:organization_id,:label,:endpoint,:status,:user_id)"""),
          {**_person_params(context), "id": integration_id, "label": payload.label.strip(),
           "endpoint": endpoint, "status": payload.status})
        _audit(connection, context, "integration.created", integration_id)
    return {"id": integration_id, **payload.model_dump(), "row_version": 1}


@router.post("/{integration_id}/test")
def test_integration(integration_id: UUID, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "integration.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    with engine.begin() as connection:
        row = connection.execute(text("""SELECT endpoint_url FROM app.local_integration
          WHERE id=:id AND organization_id=:organization_id"""),
          {**_person_params(context), "id": integration_id}).mappings().first()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        endpoint = _validate_endpoint(row["endpoint_url"])
        body = json.dumps({"event": "connectivity.test", "source": "transmissions",
                           "schema_version": 1}).encode()
        result, message = "success", "Connexion locale validee"
        try:
            response = urlopen(UrlRequest(endpoint, data=body, headers={
                "Content-Type": "application/json", "User-Agent": "Transmissions/1"
            }, method="POST"), timeout=5)
            if response.status < 200 or response.status >= 300:
                raise URLError(f"HTTP {response.status}")
        except (URLError, TimeoutError, OSError) as error:
            result, message = "failed", str(error)[:200]
        connection.execute(text("""UPDATE app.local_integration SET last_tested_at=now(),
          last_test_status=:result,last_test_message=:message WHERE id=:id"""),
          {"result": result, "message": message, "id": integration_id})
        _audit(connection, context, "integration.tested", integration_id)
    return {"status": result, "message": message, "payload_contains_business_data": False}
