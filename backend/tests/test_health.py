import os
from unittest.mock import patch

os.environ.setdefault("APP_DATABASE_PASSWORD", "synthetic-test-password")

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app


def test_liveness_does_not_expose_details() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_interactive_documentation_is_not_public() -> None:
    with TestClient(app) as client:
        response = client.get("/docs")

    assert response.status_code == 404


def test_readiness_reports_healthy_database() -> None:
    with patch("app.routers.health.engine.connect") as connect, TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    connect.return_value.__enter__.return_value.execute.assert_called_once()


def test_readiness_reports_database_failure() -> None:
    with (
        patch("app.routers.health.engine.connect", side_effect=SQLAlchemyError),
        TestClient(app) as client,
    ):
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "error"}
