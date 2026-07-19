import hashlib
import json
import socket
import struct
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.routers.people import _person_params
from app.security import SecurityContext, get_security_context, require_permission, verify_csrf

router = APIRouter(prefix="/api/v1/transmissions", tags=["attachments"])
MAX_SIZE = 5 * 1024 * 1024
SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


def _safe_name(value: str | None) -> str:
    name = Path(value or "fichier").name.strip().replace("\x00", "")
    return name[:180] or "fichier"


def _check_type(content: bytes, media_type: str) -> None:
    if media_type not in SIGNATURES or not content.startswith(SIGNATURES[media_type]):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_file_type")


def _scan(content: bytes) -> None:
    settings = get_settings()
    try:
        with socket.create_connection(
            (settings.clamav_host, settings.clamav_port), timeout=10
        ) as scanner:
            scanner.sendall(b"zINSTREAM\0")
            for offset in range(0, len(content), 65536):
                chunk = content[offset : offset + 65536]
                scanner.sendall(struct.pack("!I", len(chunk)) + chunk)
            scanner.sendall(struct.pack("!I", 0))
            result = scanner.recv(4096).decode(errors="replace")
    except OSError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "antivirus_unavailable") from error
    if "FOUND" in result:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "malware_detected")
    if "OK" not in result:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "antivirus_scan_failed")


def _transmission(connection: Any, context: SecurityContext, transmission_id: UUID) -> Any:
    return connection.execute(text("""SELECT t.id,t.status,t.author_id FROM app.transmission t
      WHERE t.id=:id AND t.organization_id=:organization_id
      AND EXISTS (SELECT 1 FROM app.membership m WHERE m.user_id=:user_id
        AND m.unit_id=t.unit_id AND m.starts_at<=now()
        AND (m.ends_at IS NULL OR m.ends_at>now()))"""),
      {**_person_params(context), "id": transmission_id}).mappings().first()


def _audit(connection: Any, context: SecurityContext, event: str, target: UUID) -> None:
    connection.execute(text("""INSERT INTO audit.event
      (organization_id,actor_user_id,event_type,target_type,target_id,metadata)
      VALUES (:organization_id,:user_id,:event,'attachment',:target,CAST(:metadata AS jsonb))"""),
      {**_person_params(context), "event": event, "target": target,
       "metadata": json.dumps({})})


@router.get("/{transmission_id}/attachments")
def list_attachments(transmission_id: UUID,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> dict[str, Any]:
    require_permission(context, "attachment.read")
    with engine.connect() as connection:
        transmission = _transmission(connection, context, transmission_id)
        if not transmission:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        rows = connection.execute(text("""SELECT id,original_name,media_type,byte_size,
          sha256,scan_status,created_at,uploaded_by FROM app.transmission_attachment
          WHERE transmission_id=:id ORDER BY created_at"""), {"id": transmission_id}).mappings()
        return {"items": [dict(row) for row in rows]}


@router.post("/{transmission_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_attachment(transmission_id: UUID, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)],
    file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    require_permission(context, "attachment.create")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    content = await file.read(MAX_SIZE + 1)
    if not content or len(content) > MAX_SIZE:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large")
    media_type = file.content_type or ""
    _check_type(content, media_type)
    _scan(content)
    attachment_id = uuid4()
    name = _safe_name(file.filename)
    digest = hashlib.sha256(content).hexdigest()
    with engine.begin() as connection:
        transmission = _transmission(connection, context, transmission_id)
        if not transmission or transmission["status"] != "draft" \
                or transmission["author_id"] != context.user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        connection.execute(text("""INSERT INTO app.transmission_attachment
          (id,organization_id,transmission_id,uploaded_by,original_name,media_type,
           byte_size,sha256,scan_status,content)
          VALUES (:id,:organization_id,:transmission_id,:user_id,:name,:media_type,
                  :size,:sha256,'clean',:content)"""),
          {**_person_params(context), "id": attachment_id, "transmission_id": transmission_id,
           "name": name, "media_type": media_type, "size": len(content),
           "sha256": digest, "content": content})
        _audit(connection, context, "attachment.uploaded", attachment_id)
    return {"id": attachment_id, "original_name": name, "media_type": media_type,
            "byte_size": len(content), "sha256": digest, "scan_status": "clean"}


@router.get("/{transmission_id}/attachments/{attachment_id}/content")
def download_attachment(transmission_id: UUID, attachment_id: UUID,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> Response:
    require_permission(context, "attachment.read")
    with engine.begin() as connection:
        if not _transmission(connection, context, transmission_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        row = connection.execute(text("""SELECT original_name,media_type,content FROM
          app.transmission_attachment WHERE id=:attachment_id AND transmission_id=:transmission_id
          AND scan_status='clean'"""), {"attachment_id": attachment_id,
          "transmission_id": transmission_id}).mappings().first()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        _audit(connection, context, "attachment.downloaded", attachment_id)
    name = row["original_name"].replace('"', "")
    return Response(content=bytes(row["content"]), media_type=row["media_type"], headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "X-Content-Type-Options": "nosniff",
    })


@router.delete("/{transmission_id}/attachments/{attachment_id}", status_code=204)
def delete_attachment(transmission_id: UUID, attachment_id: UUID, request: Request,
    context: Annotated[SecurityContext, Depends(get_security_context)]) -> None:
    require_permission(context, "attachment.delete_draft")
    verify_csrf(request, context, request.headers.get("X-CSRF-Token"))
    with engine.begin() as connection:
        transmission = _transmission(connection, context, transmission_id)
        if not transmission or transmission["status"] != "draft" \
                or transmission["author_id"] != context.user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        deleted = connection.execute(text("""DELETE FROM app.transmission_attachment
          WHERE id=:attachment_id AND transmission_id=:transmission_id RETURNING id"""),
          {"attachment_id": attachment_id, "transmission_id": transmission_id}).first()
        if not deleted:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        _audit(connection, context, "attachment.deleted", attachment_id)
