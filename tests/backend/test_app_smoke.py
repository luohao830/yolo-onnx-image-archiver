from backend.api.routes.health import healthz
from backend.main import app


def test_healthz_returns_ok() -> None:
    assert healthz() == {"status": "ok"}


def test_openapi_contains_health_route() -> None:
    schema = app.openapi()
    assert "/api/healthz" in schema["paths"]
    assert "get" in schema["paths"]["/api/healthz"]
