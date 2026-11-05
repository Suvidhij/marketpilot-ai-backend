import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app(Settings(_env_file=None, cors_origins=["http://localhost:3000"]))) as client:
        yield client


def test_health_contract(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "MarketPilot AI API", "version": "0.1.0"}


def test_trusted_origin_can_read_health(client):
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_untrusted_origin_gets_no_cors_permission(client):
    response = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_unsupported_method_preflight_is_rejected(client):
    response = client.options("/api/v1/health", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "DELETE"})
    assert response.status_code == 400


def test_missing_route_is_404(client):
    assert client.get("/api/v1/unknown").status_code == 404
