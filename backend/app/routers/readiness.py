# ruff: noqa: E501
import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import engine
from app.routers.people import _etag, _parse_if_match, _person_params
from app.security import SecurityContext, get_security_context, require_permission, verify_csrf

router = APIRouter(prefix="/api/v1/pilot-readiness", tags=["pilot readiness"])


class DecisionInput(BaseModel):
    status: Literal["pending", "validated", "blocked"]
    evidence: str = Field(default="", max_length=1000)


@router.get("")
def readiness(context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "pilot.read")
    with engine.connect() as connection:
        decisions = [dict(row) for row in connection.execute(text(
            "SELECT * FROM app.pilot_decision ORDER BY code")).mappings()]
        technical = dict(connection.execute(text("""SELECT
          (SELECT count(*) FROM app.retention_policy WHERE retention_days IS NULL
            OR legal_basis IS NULL) AS retention_missing,
          (SELECT count(*) FROM app.user_account WHERE organization_id=:organization_id
            AND status='active') AS active_accounts,
          (SELECT count(*) FROM app.local_integration WHERE organization_id=:organization_id
            AND status='enabled') AS enabled_integrations,
          (SELECT count(*) FROM audit.event WHERE organization_id=:organization_id) AS audit_events
          ,(SELECT count(*) FROM app.acceptance_scenario WHERE status<>'passed') AS acceptance_remaining
          ,(SELECT count(*) FROM app.pilot_issue WHERE organization_id=:organization_id
            AND severity='critical' AND status IN ('open','in_progress')) AS critical_issues
        """), _person_params(context)).mappings().one())
    checks = [
        {"code": "authorization", "label": "Comptes actifs et habilitations", "passed": technical["active_accounts"] > 0},
        {"code": "audit", "label": "Journal d audit alimente", "passed": technical["audit_events"] > 0},
        {"code": "retention", "label": "Conservation juridiquement renseignee", "passed": technical["retention_missing"] == 0},
        {"code": "integrations", "label": "Flux externes inactifs avant validation", "passed": technical["enabled_integrations"] == 0},
        {"code": "acceptance", "label": "Recette metier entierement validee", "passed": technical["acceptance_remaining"] == 0},
        {"code": "issues", "label": "Aucune anomalie critique ouverte", "passed": technical["critical_issues"] == 0},
    ]
    validated = sum(item["status"] == "validated" for item in decisions)
    return {"decisions": decisions, "technical_checks": checks,
            "summary": {"validated": validated, "total": len(decisions),
                        "technical_passed": sum(item["passed"] for item in checks),
                        "technical_total": len(checks),
                        "ready": validated == len(decisions) and all(item["passed"] for item in checks)}}


@router.put("/{code}")
def update_decision(code: str, payload: DecisionInput, request: Request, response: Response,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> dict[str, Any]:
    require_permission(context, "pilot.manage")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    expected = _parse_if_match(if_match)
    with engine.begin() as connection:
        updated = connection.execute(text("""UPDATE app.pilot_decision SET status=:status,
          evidence=:evidence,updated_by=:user_id,updated_at=now(),row_version=row_version+1
          WHERE code=:code AND row_version=:version RETURNING *"""),
          {"status": payload.status, "evidence": payload.evidence.strip(),
           "user_id": context.user_id, "code": code, "version": expected}).mappings().first()
        if not updated:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, "version_conflict")
        connection.execute(text("""INSERT INTO audit.event
          (organization_id,actor_user_id,event_type,target_type,metadata) VALUES
          (:organization_id,:user_id,'pilot.decision_updated','pilot_decision',CAST(:metadata AS jsonb))"""),
          {**_person_params(context), "metadata": json.dumps({"code": code,
            "status": payload.status})})
    response.headers["ETag"] = _etag(updated["row_version"])
    return dict(updated)
