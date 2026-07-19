from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException, UploadFile
from starlette.requests import Request

from app.routers.attachments import (
    _check_type,
    _safe_name,
    _scan,
    delete_attachment,
    download_attachment,
    list_attachments,
    upload_attachment,
)
from app.security import SecurityContext, token_hash

USER = UUID("60000000-0000-4000-8000-000000000002")
ORG = UUID("10000000-0000-4000-8000-000000000001")
TRANSMISSION = UUID("90000000-0000-4000-8000-000000000001")
ATTACHMENT = UUID("d0000000-0000-4000-8000-000000000001")


def context() -> SecurityContext:
    return SecurityContext(USER, ORG, "professionnel", "Camille Martin", None, token_hash("csrf"))


def request() -> Request:
    return Request({"type": "http", "headers": [
        (b"origin", b"https://localhost"), (b"x-csrf-token", b"csrf"),
    ]})


def database(connection: MagicMock, transaction: bool = False) -> MagicMock:
    value = MagicMock()
    manager = value.begin if transaction else value.connect
    manager.return_value.__enter__.return_value = connection
    return value


def result(row: object) -> MagicMock:
    value = MagicMock()
    value.mappings.return_value.first.return_value = row
    return value


def test_attachment_name_type_and_antivirus_fail_closed() -> None:
    assert _safe_name("../preuve.pdf") == "preuve.pdf"
    _check_type(b"%PDF-1.7", "application/pdf")
    with pytest.raises(HTTPException) as invalid:
        _check_type(b"not a pdf", "application/pdf")
    assert invalid.value.status_code == 415
    with patch(
        "app.routers.attachments.socket.create_connection", side_effect=OSError
    ), pytest.raises(HTTPException) as unavailable:
        _scan(b"%PDF-test")
    assert unavailable.value.status_code == 503


def test_antivirus_rejects_malware_and_accepts_clean_file() -> None:
    scanner = MagicMock()
    scanner.__enter__.return_value = scanner
    scanner.recv.return_value = b"stream: Eicar-Signature FOUND\0"
    with patch(
        "app.routers.attachments.socket.create_connection", return_value=scanner
    ), pytest.raises(HTTPException) as infected:
        _scan(b"infected")
    assert infected.value.detail == "malware_detected"
    scanner.recv.return_value = b"stream: OK\0"
    with patch("app.routers.attachments.socket.create_connection", return_value=scanner):
        _scan(b"clean")


@pytest.mark.anyio
async def test_upload_and_list_clean_attachment() -> None:
    connection = MagicMock()
    transmission = {"id": TRANSMISSION, "status": "draft", "author_id": USER}
    connection.execute.side_effect = [result(transmission), MagicMock(), MagicMock()]
    upload = UploadFile(filename="preuve.pdf", file=BytesIO(b"%PDF-1.7 test"),
                        headers={"content-type": "application/pdf"})
    with patch("app.routers.attachments.engine", database(connection, True)), patch(
        "app.routers.attachments.require_permission"
    ), patch("app.routers.attachments._scan"):
        response = await upload_attachment(TRANSMISSION, request(), context(), upload)
    assert response["scan_status"] == "clean"
    assert response["byte_size"] == 13

    connection = MagicMock()
    rows = MagicMock()
    rows.mappings.return_value.__iter__.return_value = iter([{"id": ATTACHMENT}])
    connection.execute.side_effect = [result(transmission), rows]
    with patch("app.routers.attachments.engine", database(connection)), patch(
        "app.routers.attachments.require_permission"
    ):
        listed = list_attachments(TRANSMISSION, context())
    assert listed["items"][0]["id"] == ATTACHMENT


def test_download_and_delete_attachment_are_scoped_and_audited() -> None:
    transmission = {"id": TRANSMISSION, "status": "draft", "author_id": USER}
    connection = MagicMock()
    connection.execute.side_effect = [
        result(transmission),
        result({"original_name": "preuve.pdf", "media_type": "application/pdf",
                "content": b"%PDF-test"}),
        MagicMock(),
    ]
    with patch("app.routers.attachments.engine", database(connection, True)), patch(
        "app.routers.attachments.require_permission"
    ):
        response = download_attachment(TRANSMISSION, ATTACHMENT, context())
    assert response.body == b"%PDF-test"
    assert response.headers["x-content-type-options"] == "nosniff"

    connection = MagicMock()
    connection.execute.side_effect = [result(transmission), MagicMock(first=lambda: (ATTACHMENT,)),
                                      MagicMock()]
    with patch("app.routers.attachments.engine", database(connection, True)), patch(
        "app.routers.attachments.require_permission"
    ):
        delete_attachment(TRANSMISSION, ATTACHMENT, request(), context())
    assert connection.execute.call_count == 3
