import json
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.core.security import digest
from app.models import ApprovalAction, Campaign, Content, Lead, WorkflowEvent
from app.services.records import (
    owned_client,
    owned_record,
    qualify_lead,
    snapshot_report,
)


def cancel_actions(db, user_id, client_id, resource_id, action):
    if action is None:
        return
    actions = db.scalars(
        select(ApprovalAction).where(
            ApprovalAction.user_id == user_id,
            ApprovalAction.client_id == client_id,
            ApprovalAction.resource_id == resource_id,
            ApprovalAction.action == action,
            ApprovalAction.status.in_(["pending_approval", "approved", "executing"]),
        )
    ).all()
    if any(a.status == "executing" for a in actions):
        raise HTTPException(
            409,
            "An automation is executing for this record. Complete it before editing or deleting.",
        )
    for item in actions:
        changed = db.execute(
            update(ApprovalAction)
            .where(
                ApprovalAction.id == item.id,
                ApprovalAction.status.in_(["pending_approval", "approved"]),
            )
            .values(status="cancelled")
        )
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(
                409, "Action was claimed concurrently. Refresh before editing"
            )


def create_action(db, user_id, data):
    owned_client(db, user_id, data.client_id, lock=True)
    model = Content if data.action == "publish_content" else Campaign
    record = owned_record(db, model, data.client_id, data.resource_id)
    cancel_actions(db, user_id, data.client_id, data.resource_id, data.action)
    if data.action == "publish_content":
        if data.new_budget is not None or record.status == "published":
            raise HTTPException(
                422, "Choose an unpublished content item and omit new_budget"
            )
        payload = {
            "title": record.title,
            "body": record.body,
            "platform": record.platform,
            "scheduled_at": record.scheduled_at.isoformat()
            if record.scheduled_at
            else None,
        }
        record.status = "pending_approval"
    else:
        if data.new_budget is None:
            raise HTTPException(422, "new_budget is required")
        payload = {
            "campaign_name": record.campaign_name,
            "platform": record.platform,
            "previous_budget": str(record.budget),
            "new_budget": str(data.new_budget),
        }
    item = ApprovalAction(
        user_id=user_id,
        client_id=data.client_id,
        action=data.action,
        resource_id=data.resource_id,
        payload=payload,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def process_event(db, user_id, kind, data):
    owned_client(db, user_id, data.client_id, lock=True)
    payload_hash = digest(json.dumps(data.model_dump(mode="json"), sort_keys=True))

    def existing_result():
        existing = db.scalar(
            select(WorkflowEvent).where(
                WorkflowEvent.user_id == user_id,
                WorkflowEvent.event_id == data.event_id,
            )
        )
        if existing:
            if existing.kind != kind or existing.payload_hash != payload_hash:
                raise HTTPException(
                    409, "event_id was already used with a different payload"
                )
            return {**existing.result, "duplicate": True}
        return None

    previous = existing_result()
    if previous:
        return previous
    if kind == "lead":
        values = data.model_dump(exclude={"event_id", "client_id"})
        values["lead_score"] = qualify_lead(data)
        record = Lead(client_id=data.client_id, **values)
        db.add(record)
        db.flush()
        result = {
            "lead_id": record.id,
            "lead_score": record.lead_score,
            "scoring_basis": "20 base + 25 email + 25 inbound/referral/demo (otherwise 5) + 20 qualified, capped at 100",
        }
    else:
        record = snapshot_report(db, user_id, data.client_id, data.report_name)
        result = {"report_id": record.id}
    db.add(
        WorkflowEvent(
            user_id=user_id,
            event_id=data.event_id,
            kind=kind,
            payload_hash=payload_hash,
            result=result,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = existing_result()
        if previous:
            return previous
        raise HTTPException(
            409, "Workflow conflict. Retry with the same event_id"
        ) from None
    return {**result, "duplicate": False}


def apply_completion(db, item, reference):
    if item.status == "completed":
        if item.external_reference != reference:
            raise HTTPException(
                409, "Action already completed with a different reference"
            )
        return item
    if item.status != "executing":
        raise HTTPException(409, "Claim an approved action before completing it")
    if item.action == "publish_content":
        record = owned_record(db, Content, item.client_id, item.resource_id)
        record.status = "published"
    else:
        record = owned_record(db, Campaign, item.client_id, item.resource_id)
        record.budget = Decimal(item.payload["new_budget"])
    item.status = "completed"
    item.external_reference = reference
    db.commit()
    db.refresh(item)
    return item
