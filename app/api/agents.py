from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.agents.marketing import run_agent
from app.api.auth import throttle
from app.core.database import get_db
from app.core.security import current_user
from app.models import Report, User
from app.schemas.entities import AgentRequest, ReportOut
from app.services.records import client_context

router = APIRouter(tags=["AI agents"])


@router.post(
    "/clients/{client_id}/agents/run", response_model=ReportOut, status_code=201
)
def agent_run(
    client_id: int,
    data: AgentRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    context = client_context(db, user.id, client_id)
    throttle(db, "ai:" + str(user.id), maximum=20, minutes=60)
    result = run_agent(request.app.state.settings, context, data.agent, data.question)
    report = Report(
        client_id=client_id,
        report_name=f"{data.agent.title()} agent insights",
        report_type=data.agent,
        report_data=result,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
