from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.models import Campaign, Content, Lead, Report
from .conftest import CSRF, PASSWORD


def test_cross_user_and_cross_client_isolation(signed_in, owned, application):
    lead = signed_in.post(
        f"/api/v1/clients/{owned}/leads",
        json={"name": "Lead", "email": "lead@example.com"},
    ).json()
    with TestClient(application, headers=CSRF) as other:
        other.post(
            "/api/v1/auth/register",
            json={"name": "Other", "email": "other@example.com", "password": PASSWORD},
        )
        assert other.get("/api/v1/clients").json() == []
        for suffix in ["", "/overview", "/leads", "/campaigns", "/content", "/reports"]:
            assert other.get(f"/api/v1/clients/{owned}{suffix}").status_code == 404
        assert (
            other.put(
                f"/api/v1/clients/{owned}", json={"company_name": "Stolen"}
            ).status_code
            == 404
        )
        assert other.delete(f"/api/v1/clients/{owned}").status_code == 404
        assert (
            other.post(
                f"/api/v1/clients/{owned}/leads",
                json={"name": "Bad", "email": "x@example.com"},
            ).status_code
            == 404
        )
    another = signed_in.post("/api/v1/clients", json={"company_name": "Second"}).json()[
        "id"
    ]
    assert (
        signed_in.get(f"/api/v1/clients/{another}/leads/{lead['id']}").status_code
        == 404
    )


def test_crud_metrics_reports_and_cascade(signed_in, owned, application):
    base = f"/api/v1/clients/{owned}"
    campaign = {
        "campaign_name": "Launch",
        "platform": "Search",
        "budget": "500.00",
        "impressions": 1000,
        "clicks": 100,
        "lead_count": 10,
        "conversions": 5,
        "spend": "200.00",
        "revenue": "1000.00",
    }
    r = signed_in.post(base + "/campaigns", json=campaign)
    assert r.status_code == 201, r.text
    campaign_id = r.json()["id"]
    assert (
        signed_in.put(
            base + f"/campaigns/{campaign_id}", json={**campaign, "status": "active"}
        ).json()["status"]
        == "active"
    )
    assert (
        signed_in.post(
            base + "/leads",
            json={
                "name": "One",
                "email": "one@example.com",
                "status": "qualified",
                "lead_score": 80,
            },
        ).status_code
        == 201
    )
    assert (
        signed_in.post(
            base + "/content",
            json={"title": "Post", "platform": "LinkedIn", "body": "Content to review"},
        ).status_code
        == 201
    )
    context = signed_in.get(base + "/overview").json()
    assert {k: context["metrics"][k] for k in ["ctr", "cpc", "cpm", "cpl", "roas"]} == {
        "ctr": 10.0,
        "cpc": 2.0,
        "cpm": 200.0,
        "cpl": 20.0,
        "roas": 5.0,
    }
    report = signed_in.post(base + "/reports", json={"report_name": "Weekly"})
    assert report.status_code == 201
    assert report.json()["report_data"]["lead_summary"]["qualified"] == 1
    assert signed_in.delete(base).status_code == 204
    with application.state.session_factory() as db:
        for model in [Campaign, Lead, Content, Report]:
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_empty_metrics_and_validation(signed_in, owned):
    base = f"/api/v1/clients/{owned}"
    assert signed_in.get(base + "/overview").json()["metrics"]["roas"] is None
    assert (
        signed_in.post(
            base + "/leads",
            json={"name": "X", "email": "a@example.com", "lead_score": 101},
        ).status_code
        == 422
    )
    assert (
        signed_in.post(
            base + "/campaigns",
            json={"campaign_name": "X", "platform": "Search", "budget": "-1"},
        ).status_code
        == 422
    )
    assert (
        signed_in.post(
            base + "/content",
            json={
                "title": "X",
                "platform": "Social",
                "body": "X",
                "scheduled_at": "2026-11-05T15:00:00",
            },
        ).status_code
        == 422
    )
    assert signed_in.get("/api/v1/clients?limit=1001").status_code == 422
    assert (
        signed_in.post(
            "/api/v1/clients",
            json={"company_name": "X", "website": "javascript:alert(1)"},
        ).status_code
        == 422
    )


def test_ai_unconfigured_and_ownership(signed_in, owned):
    assert (
        signed_in.post(
            f"/api/v1/clients/{owned}/agents/run", json={"agent": "research"}
        ).status_code
        == 503
    )
    assert (
        signed_in.post(
            "/api/v1/clients/99999/agents/run", json={"agent": "research"}
        ).status_code
        == 404
    )
