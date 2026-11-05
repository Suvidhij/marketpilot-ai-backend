from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.models import Campaign, Client, Content, Lead, Report


def owned_client(
    db: Session, user_id: int, client_id: int, lock: bool = False
) -> Client:
    if lock:
        # A no-op write serializes SQLite mutations before reading approval state.
        # PostgreSQL uses the same statement to lock this client row.
        db.execute(
            update(Client)
            .where(Client.id == client_id, Client.user_id == user_id)
            .values(updated_at=Client.updated_at)
        )
    client = db.scalar(
        select(Client).where(Client.id == client_id, Client.user_id == user_id)
    )
    if client is None:
        raise HTTPException(404, "Client not found")
    return client


def owned_record(db: Session, model, client_id: int, record_id: int):
    record = db.scalar(
        select(model).where(model.id == record_id, model.client_id == client_id)
    )
    if record is None:
        raise HTTPException(404, "Record not found")
    return record


def metrics(campaigns):
    total = {
        key: sum(float(getattr(c, key)) for c in campaigns)
        for key in (
            "impressions",
            "clicks",
            "conversions",
            "lead_count",
            "spend",
            "revenue",
        )
    }

    def ratio(a, b, factor=1):
        return round(total[a] / total[b] * factor, 4) if total[b] else None

    return {
        **total,
        "ctr": ratio("clicks", "impressions", 100),
        "cpc": ratio("spend", "clicks"),
        "cpm": ratio("spend", "impressions", 1000),
        "cpl": ratio("spend", "lead_count"),
        "roas": ratio("revenue", "spend"),
    }


def client_context(db: Session, user_id: int, client_id: int):
    client = owned_client(db, user_id, client_id)
    campaigns = db.scalars(
        select(Campaign).where(Campaign.client_id == client_id).order_by(Campaign.id)
    ).all()
    leads = db.scalars(select(Lead).where(Lead.client_id == client_id)).all()
    contents = db.scalars(select(Content).where(Content.client_id == client_id)).all()
    previous = db.scalars(
        select(Report)
        .where(Report.client_id == client_id, Report.report_type == "performance")
        .order_by(Report.created_at.desc(), Report.id.desc())
        .limit(6)
    ).all()
    history = [
        {
            "report_id": r.id,
            "created_at": r.created_at.isoformat(),
            "metrics": r.report_data.get("metrics"),
            "lead_summary": r.report_data.get("lead_summary"),
        }
        for r in previous
    ]
    return {
        "previous_snapshots": history,
        "client": {
            "id": client.id,
            "company_name": client.company_name,
            "website": client.website,
            "industry": client.industry,
            "description": client.description[:10000],
        },
        "campaigns": [
            {
                "id": c.id,
                "name": c.campaign_name,
                "platform": c.platform,
                "objective": c.objective,
                "status": c.status,
                "budget": str(c.budget),
                "metrics": metrics([c]),
            }
            for c in campaigns[:100]
        ],
        "metrics": metrics(campaigns),
        "lead_summary": {
            "total": len(leads),
            "qualified": sum(l.status == "qualified" for l in leads),
            "won": sum(l.status == "won" for l in leads),
            "average_score": round(sum(l.lead_score for l in leads) / len(leads), 2)
            if leads
            else None,
        },
        "content_summary": {
            "total": len(contents),
            "drafts": sum(c.status == "draft" for c in contents),
        },
        "limitations": [
            "Metrics are user-entered, not synchronized from advertising platforms.",
            "No live website crawl, competitor search, keyword feed, or retrieval source is connected.",
            "Campaign detail is limited to the first 100; aggregate metrics include all campaigns.",
        ],
    }


def snapshot_report(db, user_id, client_id, name):
    context = client_context(db, user_id, client_id)
    record = Report(
        client_id=client_id,
        report_name=name,
        report_type="performance",
        report_data=context,
    )
    db.add(record)
    db.flush()
    return record


def qualify_lead(data):
    # Transparent deterministic scoring, never an inference about a person's worth.
    return min(
        100,
        20
        + (25 if data.email else 0)
        + (25 if data.source.lower() in {"referral", "demo", "inbound"} else 5)
        + (20 if data.status == "qualified" else 0),
    )
