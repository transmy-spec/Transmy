from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi import Response
from pydantic import SecretStr
from starlette.requests import Request

from app.routers.personalized_plans import PlanContent, PlanInput, create_plan
from app.security import SecurityContext, token_hash


def context() -> SecurityContext:
    return SecurityContext(UUID("60000000-0000-4000-8000-000000000003"),
      UUID("10000000-0000-4000-8000-000000000001"), "chef", "Sophie", None,
      token_hash("csrf"))


def request() -> Request:
    return Request({"type": "http", "headers": [(b"origin", b"https://localhost"),
      (b"x-csrf-token", b"csrf")]})


def test_create_plan_encrypts_content_and_audits() -> None:
    connection = MagicMock()
    connection.execute.return_value.first.return_value = (1,)
    database = MagicMock()
    database.begin.return_value.__enter__.return_value = connection
    settings = type("Settings", (), {"field_encryption_key": SecretStr("a" * 32)})()
    payload = PlanInput(content=PlanContent(person_expectations="Choisir mon logement",
      goals=["Gagner en autonomie"], participation_method="Entretien avec la personne",
      consent_status="obtained"), publish=True)
    with patch("app.routers.personalized_plans.engine", database), patch(
      "app.routers.personalized_plans.require_permission"), patch(
      "app.crypto.get_settings", return_value=settings):
        result = create_plan(UUID("90000000-0000-4000-8000-000000000001"), payload,
          request(), Response(), context())
    assert result["status"] == "active"
    assert connection.execute.call_count == 4
