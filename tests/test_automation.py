from fastapi.testclient import TestClient
from .conftest import CSRF, PASSWORD


def key(client):
    r = client.post("/api/v1/automation/token")
    assert r.status_code == 201
    return {"X-Workflow-Key": r.json()["token"]}


def test_authenticated_idempotent_webhooks(signed_in, owned):
    headers = key(signed_in)
    payload = {
        "event_id": "lead-event-1",
        "client_id": owned,
        "name": "Lead",
        "email": "lead@example.com",
        "source": "referral",
    }
    assert signed_in.post("/api/v1/webhooks/leads", json=payload).status_code == 401
    first = signed_in.post(
        "/api/v1/webhooks/leads", json=payload, headers=headers
    ).json()
    second = signed_in.post(
        "/api/v1/webhooks/leads", json=payload, headers=headers
    ).json()
    assert first["lead_id"] == second["lead_id"] and second["duplicate"]
    assert first["lead_score"] == 70
    assert (
        signed_in.post(
            "/api/v1/webhooks/leads",
            json={**payload, "name": "Different"},
            headers=headers,
        ).status_code
        == 409
    )
    assert len(signed_in.get(f"/api/v1/clients/{owned}/leads").json()) == 1
    report = {"event_id": "weekly-1", "client_id": owned}
    assert (
        signed_in.post(
            "/api/v1/webhooks/reports", json=report, headers=headers
        ).status_code
        == 200
    )
    assert signed_in.post(
        "/api/v1/webhooks/reports", json=report, headers=headers
    ).json()["duplicate"]
    assert len(signed_in.get("/api/v1/automation/events").json()) == 2


def test_rotating_and_revoking_workflow_key(signed_in, owned):
    old = key(signed_in)
    new = key(signed_in)
    assert signed_in.get("/api/v1/webhooks/actions", headers=old).status_code == 401
    assert signed_in.get("/api/v1/webhooks/actions", headers=new).status_code == 200
    assert signed_in.delete("/api/v1/automation/token").status_code == 204
    assert signed_in.get("/api/v1/webhooks/actions", headers=new).status_code == 401


def test_approval_required_and_immutable_handoff(signed_in, owned):
    headers = key(signed_in)
    content = signed_in.post(
        f"/api/v1/clients/{owned}/content",
        json={"title": "Draft", "platform": "Social", "body": "Review this"},
    ).json()
    action = signed_in.post(
        "/api/v1/automation/actions",
        json={
            "client_id": owned,
            "resource_id": content["id"],
            "action": "publish_content",
        },
    ).json()
    aid = action["id"]
    assert action["status"] == "pending_approval"
    assert signed_in.get("/api/v1/webhooks/actions", headers=headers).json() == []
    assert (
        signed_in.post(
            f"/api/v1/webhooks/actions/{aid}/claim", headers=headers
        ).status_code
        == 409
    )
    assert (
        signed_in.post(
            f"/api/v1/automation/actions/{aid}/decision", json={"decision": "approve"}
        ).json()["status"]
        == "approved"
    )
    claim = signed_in.post(
        f"/api/v1/webhooks/actions/{aid}/claim", headers=headers
    ).json()
    assert claim["idempotency_key"] == f"marketpilot-action-{aid}"
    assert (
        signed_in.post(f"/api/v1/webhooks/actions/{aid}/claim", headers=headers).json()
        == claim
    )
    assert (
        signed_in.put(
            f"/api/v1/clients/{owned}/content/{content['id']}",
            json={"title": "Edited", "platform": "Social", "body": "Changed"},
        ).status_code
        == 409
    )
    assert signed_in.delete(f"/api/v1/clients/{owned}").status_code == 409
    assert (
        signed_in.post(
            f"/api/v1/automation/actions/{aid}/decision", json={"decision": "reject"}
        ).status_code
        == 409
    )
    completion = {"external_reference": "external-publish-receipt-123"}
    assert (
        signed_in.post(
            f"/api/v1/webhooks/actions/{aid}/complete", json=completion, headers=headers
        ).json()["status"]
        == "completed"
    )
    assert (
        signed_in.post(
            f"/api/v1/webhooks/actions/{aid}/complete", json=completion, headers=headers
        ).status_code
        == 200
    )
    assert (
        signed_in.post(
            f"/api/v1/webhooks/actions/{aid}/complete",
            json={"external_reference": "other"},
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        signed_in.get(f"/api/v1/clients/{owned}/content/{content['id']}").json()[
            "status"
        ]
        == "published"
    )


def test_edit_invalidates_approval(signed_in, owned):
    content = signed_in.post(
        f"/api/v1/clients/{owned}/content",
        json={"title": "Draft", "platform": "Social", "body": "Review"},
    ).json()
    action = signed_in.post(
        "/api/v1/automation/actions",
        json={
            "client_id": owned,
            "resource_id": content["id"],
            "action": "publish_content",
        },
    ).json()
    signed_in.post(
        f"/api/v1/automation/actions/{action['id']}/decision",
        json={"decision": "approve"},
    )
    assert (
        signed_in.put(
            f"/api/v1/clients/{owned}/content/{content['id']}",
            json={"title": "New", "platform": "Social", "body": "New"},
        ).json()["status"]
        == "draft"
    )
    assert (
        signed_in.get("/api/v1/automation/actions").json()[0]["status"] == "cancelled"
    )


def test_workflow_ownership(signed_in, owned, application):
    with TestClient(application, headers=CSRF) as other:
        other.post(
            "/api/v1/auth/register",
            json={"name": "Other", "email": "other@example.com", "password": PASSWORD},
        )
        headers = key(other)
        r = other.post(
            "/api/v1/webhooks/leads",
            json={
                "event_id": "bad",
                "client_id": owned,
                "name": "X",
                "email": "x@example.com",
            },
            headers=headers,
        )
        assert r.status_code == 404
