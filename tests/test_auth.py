from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.security import COOKIE, passwords
from app.models import User, UserSession
from .conftest import CSRF, PASSWORD


def test_password_hash_and_cookie(signed_in, application):
    with application.state.session_factory() as db:
        user = db.scalar(select(User))
        assert user.hashed_password != PASSWORD and passwords.verify(
            PASSWORD, user.hashed_password
        )
    r = signed_in.post(
        "/api/v1/auth/login",
        json={"email": "MARKETER@example.com", "password": PASSWORD},
    )
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert (
        "httponly" in cookie and "samesite=lax" in cookie and "max-age=86400" in cookie
    )
    assert "hashed_password" not in r.text


def test_duplicate_email_and_invalid_inputs(signed_in):
    assert (
        signed_in.post(
            "/api/v1/auth/register",
            json={
                "name": "Another",
                "email": "MARKETER@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 409
    )
    bad = signed_in.post(
        "/api/v1/auth/register",
        json={"name": "A", "email": "invalid", "password": "private-short"},
    )
    assert (
        bad.status_code == 422
        and "private-short" not in bad.text
        and '"input"' not in bad.text
    )


def test_login_errors_and_rate_limit(client):
    for _ in range(8):
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": PASSWORD},
        )
        assert (
            r.status_code == 401
            and r.json()["detail"] == "Email or password is incorrect"
        )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": PASSWORD},
        ).status_code
        == 429
    )


def test_logout_revokes_replayed_cookie(signed_in, application):
    token = signed_in.cookies.get(COOKIE)
    assert signed_in.post("/api/v1/auth/logout").status_code == 204
    with TestClient(application) as attacker:
        assert (
            attacker.get(
                "/api/v1/auth/me", headers={"Cookie": f"{COOKIE}={token}"}
            ).status_code
            == 401
        )


def test_expiry(signed_in, application):
    with application.state.session_factory() as db:
        row = db.scalar(select(UserSession))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert signed_in.get("/api/v1/auth/me").status_code == 401


def test_password_change_revokes_other_sessions(signed_in, application):
    with TestClient(application, headers=CSRF) as other:
        assert (
            other.post(
                "/api/v1/auth/login",
                json={"email": "marketer@example.com", "password": PASSWORD},
            ).status_code
            == 200
        )
        assert (
            signed_in.post(
                "/api/v1/auth/password",
                json={
                    "current_password": PASSWORD,
                    "new_password": "different-test-passphrase",
                },
            ).status_code
            == 204
        )
        assert other.get("/api/v1/auth/me").status_code == 401
        assert signed_in.get("/api/v1/auth/me").status_code == 200
        assert (
            other.post(
                "/api/v1/auth/login",
                json={"email": "marketer@example.com", "password": PASSWORD},
            ).status_code
            == 401
        )
        assert (
            other.post(
                "/api/v1/auth/login",
                json={
                    "email": "marketer@example.com",
                    "password": "different-test-passphrase",
                },
            ).status_code
            == 200
        )


def test_csrf_origin_and_anonymous_protection(client, application):
    assert client.get("/api/v1/clients").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "a@example.com", "password": PASSWORD},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    with TestClient(application) as browser:
        assert (
            browser.post(
                "/api/v1/auth/register",
                json={"name": "A", "email": "a@example.com", "password": PASSWORD},
            ).status_code
            == 403
        )


def test_profile_update(signed_in):
    assert (
        signed_in.patch("/api/v1/auth/me", json={"name": "Updated Name"}).json()["name"]
        == "Updated Name"
    )
    assert signed_in.patch("/api/v1/auth/me", json={"name": " "}).status_code == 422


def test_body_size_limit(client):
    assert (
        client.post("/api/v1/auth/login", content=b"x" * 1_048_577).status_code == 413
    )


def test_production_security_settings():
    import pytest
    from app.core.config import Settings

    with pytest.raises(ValueError):
        Settings(_env_file=None, environment="production")
    settings = Settings(
        _env_file=None,
        environment="production",
        cookie_secure=True,
        cors_origins=["https://app.example.com"],
        allowed_hosts=["api.example.com"],
    )
    assert settings.cookie_secure
