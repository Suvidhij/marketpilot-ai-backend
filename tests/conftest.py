import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.core.database import Base
from app.main import create_app

CSRF = {"X-MarketPilot-CSRF": "1"}
PASSWORD = "test-only-long-passphrase"


@pytest.fixture
def application(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            database_url=f"sqlite:///{tmp_path}/test.db",
            cors_origins=["http://localhost:3000"],
        )
    )
    Base.metadata.create_all(app.state.engine)
    return app


@pytest.fixture
def client(application):
    with TestClient(application, headers=CSRF) as client:
        yield client


@pytest.fixture
def signed_in(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Test Marketer",
            "email": "marketer@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return client


@pytest.fixture
def owned(signed_in):
    response = signed_in.post(
        "/api/v1/clients",
        json={
            "company_name": "Test Client",
            "website": "https://example.com",
            "industry": "Software",
            "description": "A real saved description for testing.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]
