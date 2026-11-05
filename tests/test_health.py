def test_health_contract(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "service": "MarketPilot AI API",
        "version": "1.0.0",
    }


def test_trusted_and_untrusted_cors(client):
    good = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    assert good.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert good.headers["access-control-allow-credentials"] == "true"
    bad = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_disallowed_preflight(client):
    assert (
        client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "TRACE",
            },
        ).status_code
        == 400
    )


def test_missing_route_is_404(client):
    assert client.get("/api/v1/unknown").status_code == 404


def test_openapi_has_all_modules(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path in [
        "/api/v1/auth/register",
        "/api/v1/clients",
        "/api/v1/clients/{client_id}/agents/run",
        "/api/v1/webhooks/leads",
        "/api/v1/automation/actions",
    ]:
        assert path in paths
