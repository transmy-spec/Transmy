from unittest.mock import MagicMock, patch

from app.healthcheck import main


def test_healthcheck_accepts_successful_response() -> None:
    connection = MagicMock()
    connection.recv.return_value = b"HTTP/1.1 200 OK\r\n"

    with patch("app.healthcheck.create_connection") as create_connection:
        create_connection.return_value.__enter__.return_value = connection
        result = main()

    assert result == 0
    connection.sendall.assert_called_once()


def test_healthcheck_rejects_unsuccessful_response() -> None:
    connection = MagicMock()
    connection.recv.return_value = b"HTTP/1.1 503 Service Unavailable\r\n"

    with patch("app.healthcheck.create_connection") as create_connection:
        create_connection.return_value.__enter__.return_value = connection
        result = main()

    assert result == 1


def test_healthcheck_handles_connection_failure() -> None:
    with patch("app.healthcheck.create_connection", side_effect=OSError):
        assert main() == 1
