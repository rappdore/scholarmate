"""
Tests for main.py app hygiene (bug B-13).

- The catch-all exception handler must return a generic body to clients
  (details only in server logs).
- CORS must allow only the explicit localhost origins (plus "null" for the
  packaged Electron app) and must not echo arbitrary origins.
"""

import json

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

import main


def make_request(path: str = "/boom") -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_exception_handler_returns_generic_body():
    async def call_next(request):
        raise RuntimeError("secret internal details: db password hunter2")

    response = await main.log_requests(make_request(), call_next)

    assert response.status_code == 500
    body = json.loads(response.body)
    assert body == {"detail": "Internal server error"}
    assert b"hunter2" not in response.body
    assert b"secret" not in response.body


class TestCORSConfiguration:
    @pytest.fixture
    def client(self):
        return TestClient(main.app)

    def test_preflight_allows_vite_dev_server_origin(self, client):
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:5173"
        )

    def test_preflight_allows_null_origin_for_electron(self, client):
        response = client.options(
            "/health",
            headers={
                "Origin": "null",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "null"

    def test_preflight_rejects_unknown_origin(self, client):
        response = client.options(
            "/health",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in response.headers

    def test_no_wildcard_with_credentials(self, client):
        response = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert response.headers.get("access-control-allow-origin") != "*"
        # Credentials must not be allowed (nothing in the app sends them).
        assert "access-control-allow-credentials" not in response.headers
