import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user, digest, workflow_user
from app.models import ApprovalAction, Content, User, WorkflowEvent, WorkflowToken
from app.schemas.entities import (
    ActionComplete,
    ActionDecision,
    ActionIn,
    ActionOut,
    LeadWebhook,
    ReportWebhook,
)
from app.services.automation import apply_completion, create_action, process_event
from app.services.records import owned_client, owned_record

router = APIRouter(tags=["Automation"])


@router.get("/automation/status")
def status(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return {
        "workflow_token_configured": db.get(WorkflowToken, user.id) is not None,
        "external_executor": "Configure n8n and an external publishing/advertising integration. No external service is connected by this endpoint.",
    }


@router.post("/automation/token", status_code=201)
def rotate_token(db: Session = Depends(get_db), user: User = Depends(current_user)):
    token = secrets.token_urlsafe(48)
    existing = db.get(WorkflowToken, user.id)
    if existing:
        existing.token_hash = digest(token)
        existing.created_at = datetime.now(timezone.utc)
    else:
        db.add(WorkflowToken(user_id=user.id, token_hash=digest(token)))
    db.commit()
    return {
        "token": token,
        "message": "Copy this key now. Only its hash is stored. Any previous key is revoked.",
    }


@router.delete("/automation/token", status_code=204)
def revoke_token(db: Session = Depends(get_db), user: User = Depends(current_user)):
    existing = db.get(WorkflowToken, user.id)
    if existing:
        db.delete(existing)
        db.commit()


@router.get("/automation/events")
def events(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    items = db.scalars(
        select(WorkflowEvent)
        .where(WorkflowEvent.user_id == user.id)
        .order_by(WorkflowEvent.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": e.id,
            "event_id": e.event_id,
            "kind": e.kind,
            "result": e.result,
            "created_at": e.created_at,
        }
        for e in items
    ]


@router.get("/automation/actions", response_model=list[ActionOut])
def actions(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return db.scalars(
        select(ApprovalAction)
        .where(ApprovalAction.user_id == user.id)
        .order_by(ApprovalAction.id.desc())
        .limit(limit)
    ).all()


@router.post("/automation/actions", response_model=ActionOut, status_code=201)
def new_action(
    data: ActionIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return create_action(db, user.id, data)


@router.post("/automation/actions/{action_id}/decision", response_model=ActionOut)
def decide(
    action_id: int,
    data: ActionDecision,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    item = db.scalar(
        select(ApprovalAction).where(
            ApprovalAction.id == action_id, ApprovalAction.user_id == user.id
        )
    )
    if not item:
        raise HTTPException(404, "Action not found")
    owned_client(db, user.id, item.client_id, lock=True)
    db.refresh(item)
    if item.status not in {"pending_approval", "approved"}:
        raise HTTPException(409, "This action can no longer be reviewed")
    next_status = "approved" if data.decision == "approve" else "rejected"
    # Compare-and-set prevents a decision racing an executor claim.
    result = db.execute(
        update(ApprovalAction)
        .where(ApprovalAction.id == item.id, ApprovalAction.status == item.status)
        .values(
            status=next_status,
            approved_at=datetime.now(timezone.utc)
            if next_status == "approved"
            else None,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Action changed. Refresh and try again")
    if item.action == "publish_content":
        content = owned_record(db, Content, item.client_id, item.resource_id)
        content.status = "approved" if next_status == "approved" else "draft"
    db.commit()
    db.refresh(item)
    return item


@router.post("/webhooks/leads")
def incoming_lead(
    data: LeadWebhook,
    db: Session = Depends(get_db),
    user: User = Depends(workflow_user),
):
    return process_event(db, user.id, "lead", data)


@router.post("/webhooks/reports")
def incoming_report(
    data: ReportWebhook,
    db: Session = Depends(get_db),
    user: User = Depends(workflow_user),
):
    return process_event(db, user.id, "report", data)


@router.get("/webhooks/actions", response_model=list[ActionOut])
def approved_actions(
    db: Session = Depends(get_db), user: User = Depends(workflow_user)
):
    return db.scalars(
        select(ApprovalAction)
        .where(
            ApprovalAction.user_id == user.id,
            ApprovalAction.status.in_(["approved", "executing"]),
        )
        .order_by(ApprovalAction.id)
        .limit(100)
    ).all()


@router.post("/webhooks/actions/{action_id}/claim")
def claim(
    action_id: int, db: Session = Depends(get_db), user: User = Depends(workflow_user)
):
    item = db.scalar(
        select(ApprovalAction).where(
            ApprovalAction.id == action_id, ApprovalAction.user_id == user.id
        )
    )
    if not item:
        raise HTTPException(404, "Action not found")
    owned_client(db, user.id, item.client_id, lock=True)
    db.refresh(item)
    if item.status == "approved":
        result = db.execute(
            update(ApprovalAction)
            .where(ApprovalAction.id == item.id, ApprovalAction.status == "approved")
            .values(status="executing")
        )
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Action changed. Retry")
        db.commit()
        db.refresh(item)
    elif item.status != "executing":
        raise HTTPException(409, "Only approved actions may be executed")
    return {
        "action": ActionOut.model_validate(item).model_dump(mode="json"),
        "idempotency_key": f"marketpilot-action-{item.id}",
        "instruction": "Use this idempotency key with the external provider. Complete only after confirmed external success.",
    }


@router.post("/webhooks/actions/{action_id}/complete", response_model=ActionOut)
def complete(
    action_id: int,
    data: ActionComplete,
    db: Session = Depends(get_db),
    user: User = Depends(workflow_user),
):
    item = db.scalar(
        select(ApprovalAction).where(
            ApprovalAction.id == action_id, ApprovalAction.user_id == user.id
        )
    )
    if not item:
        raise HTTPException(404, "Action not found")
    owned_client(db, user.id, item.client_id, lock=True)
    db.refresh(item)
    return apply_completion(db, item, data.external_reference)
