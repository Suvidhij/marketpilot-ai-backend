from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user
from app.models import ApprovalAction, Campaign, Client, Content, Lead, Report, User
from app.schemas.entities import (
    CampaignIn,
    CampaignOut,
    ClientIn,
    ClientOut,
    ContentIn,
    ContentOut,
    LeadIn,
    LeadOut,
    ReportOut,
    ReportRequest,
)
from app.services.records import (
    client_context,
    owned_client,
    owned_record,
    snapshot_report,
)

router = APIRouter(tags=["Workspace"])


@router.get("/clients", response_model=list[ClientOut])
def clients(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return db.scalars(
        select(Client)
        .where(Client.user_id == user.id)
        .order_by(Client.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()


@router.post("/clients", response_model=ClientOut, status_code=201)
def create_client(
    data: ClientIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    record = Client(user_id=user.id, **data.model_dump(mode="json"))
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/clients/{client_id}", response_model=ClientOut)
def get_client(
    client_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return owned_client(db, user.id, client_id)


@router.put("/clients/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    data: ClientIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    record = owned_client(db, user.id, client_id, lock=True)
    for key, value in data.model_dump(mode="json").items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/clients/{client_id}", status_code=204)
def delete_client(
    client_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    client = owned_client(db, user.id, client_id, lock=True)
    if db.scalar(
        select(ApprovalAction.id).where(
            ApprovalAction.client_id == client_id, ApprovalAction.status == "executing"
        )
    ):
        raise HTTPException(
            409, "An automation is executing. Complete it before deleting this client"
        )
    db.delete(client)
    db.commit()


@router.get("/clients/{client_id}/overview")
def overview(
    client_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return client_context(db, user.id, client_id)


def resource_router(resource, model, schema, output):
    nested = APIRouter(
        prefix="/clients/{client_id}/" + resource, tags=[resource.title()]
    )

    @nested.get("", response_model=list[output], name="list_" + resource)
    def list_records(
        client_id: int,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        owned_client(db, user.id, client_id)
        return db.scalars(
            select(model)
            .where(model.client_id == client_id)
            .order_by(model.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()

    @nested.post("", response_model=output, status_code=201, name="create_" + resource)
    def create_record(
        client_id: int,
        data: schema,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        owned_client(db, user.id, client_id, lock=True)
        record = model(client_id=client_id, **data.model_dump())
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @nested.get("/{record_id}", response_model=output, name="get_" + resource)
    def get_record(
        client_id: int,
        record_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        owned_client(db, user.id, client_id)
        return owned_record(db, model, client_id, record_id)

    @nested.put("/{record_id}", response_model=output, name="update_" + resource)
    def update_record(
        client_id: int,
        record_id: int,
        data: schema,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        owned_client(db, user.id, client_id, lock=True)
        record = owned_record(db, model, client_id, record_id)
        # Existing approvals describe a specific immutable snapshot. Editing cancels them.
        from app.services.automation import cancel_actions

        cancel_actions(
            db,
            user.id,
            client_id,
            record_id,
            "publish_content"
            if model is Content
            else "change_budget"
            if model is Campaign
            else None,
        )
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        if model is Content:
            record.status = "draft"
        db.commit()
        db.refresh(record)
        return record

    @nested.delete("/{record_id}", status_code=204, name="delete_" + resource)
    def delete_record(
        client_id: int,
        record_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        owned_client(db, user.id, client_id, lock=True)
        record = owned_record(db, model, client_id, record_id)
        from app.services.automation import cancel_actions

        cancel_actions(
            db,
            user.id,
            client_id,
            record_id,
            "publish_content"
            if model is Content
            else "change_budget"
            if model is Campaign
            else None,
        )
        db.delete(record)
        db.commit()

    return nested


for resource, model, schema, output in [
    ("leads", Lead, LeadIn, LeadOut),
    ("campaigns", Campaign, CampaignIn, CampaignOut),
    ("content", Content, ContentIn, ContentOut),
]:
    router.include_router(resource_router(resource, model, schema, output))


@router.get("/clients/{client_id}/reports", response_model=list[ReportOut])
def reports(
    client_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    owned_client(db, user.id, client_id)
    return db.scalars(
        select(Report)
        .where(Report.client_id == client_id)
        .order_by(Report.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()


@router.post("/clients/{client_id}/reports", response_model=ReportOut, status_code=201)
def create_report(
    client_id: int,
    data: ReportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    report = snapshot_report(db, user.id, client_id, data.report_name)
    db.commit()
    db.refresh(report)
    return report


@router.get("/clients/{client_id}/reports/{report_id}", response_model=ReportOut)
def get_report(
    client_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    owned_client(db, user.id, client_id)
    return owned_record(db, Report, client_id, report_id)


@router.delete("/clients/{client_id}/reports/{report_id}", status_code=204)
def delete_report(
    client_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    owned_client(db, user.id, client_id)
    db.delete(owned_record(db, Report, client_id, report_id))
    db.commit()
