from types import SimpleNamespace
from pydantic import SecretStr
from app.agents.marketing import run_agent
from app.schemas.entities import AgentResult


def test_tool_calling_and_structured_output(monkeypatch, signed_in, owned, application):
    import json
    from app.services.records import client_context

    with application.state.session_factory() as db:
        context = client_context(db, 1, owned)
    captured = {}

    class Responses:
        def create(self, **kwargs):
            captured["tools"] = kwargs["tools"]
            return SimpleNamespace(
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="get_client_context",
                        arguments="{}",
                        call_id="call-1",
                    )
                ]
            )

        def parse(self, **kwargs):
            tool_result = kwargs["input"][-1]
            captured["context"] = json.loads(tool_result["output"])
            return SimpleNamespace(
                id="test-provider-response",
                output_parsed=AgentResult(
                    summary="No campaign data yet",
                    insights=["No performance totals are available"],
                    recommendations=["Enter campaign totals"],
                    evidence=["Saved client context"],
                    limitations=["No live web research"],
                    draft_content=None,
                ),
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = Responses()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("app.agents.marketing.OpenAI", FakeOpenAI)
    settings = application.state.settings
    settings.ai_enabled = True
    settings.openai_api_key = SecretStr("test-only-not-a-real-api-key")
    result = run_agent(settings, context, "research", "What should we do next?")
    assert captured["context"]["client"]["id"] == owned
    assert "email" not in json.dumps(captured["context"]).lower()
    assert captured["tools"][0]["parameters"]["additionalProperties"] is False
    assert (
        result["result"]["summary"] == "No campaign data yet"
        and result["human_review_required"]
    )
    response = signed_in.post(
        f"/api/v1/clients/{owned}/agents/run", json={"agent": "content"}
    )
    assert response.status_code == 201 and response.json()["report_type"] == "content"
    assert response.json()["report_data"]["source_context"]["client"]["id"] == owned
