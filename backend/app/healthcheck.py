import sys
from socket import create_connection


def main() -> int:
    try:
        with create_connection(("127.0.0.1", 8000), timeout=2) as connection:
            connection.sendall(
                b"GET /api/v1/health/live HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
            )
            response = connection.recv(64)
            return 0 if response.startswith(b"HTTP/1.1 200") else 1
    except OSError:
        return 1


if __name__ == "__main__":
    sys.exit(main())
