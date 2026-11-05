from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base, UTCDateTime


def now():
    return datetime.now(timezone.utc)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=now, onupdate=now
    )


class User(Timestamps, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    clients: Mapped[list["Client"]] = relationship(
        back_populates="owner", passive_deletes="all"
    )


class UserSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now, index=True)


class Client(Timestamps, Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    owner: Mapped["User"] = relationship(back_populates="clients")
    leads: Mapped[list["Lead"]] = relationship(passive_deletes="all")
    campaigns: Mapped[list["Campaign"]] = relationship(passive_deletes="all")
    contents: Mapped[list["Content"]] = relationship(passive_deletes="all")
    reports: Mapped[list["Report"]] = relationship(passive_deletes="all")
    company_name: Mapped[str] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    industry: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")


class Lead(Timestamps, Base):
    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint("lead_score >= 0 AND lead_score <= 100"),
        CheckConstraint("status IN ('new','qualified','contacted','won','lost')"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    source: Mapped[str] = mapped_column(String(120), default="manual")
    status: Mapped[str] = mapped_column(String(30), default="new")
    lead_score: Mapped[int] = mapped_column(Integer, default=0)


class Campaign(Timestamps, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint("budget >= 0 AND spend >= 0 AND revenue >= 0"),
        CheckConstraint(
            "impressions >= 0 AND clicks >= 0 AND conversions >= 0 AND lead_count >= 0"
        ),
        CheckConstraint("status IN ('draft','active','paused','completed')"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    campaign_name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(80))
    objective: Mapped[str] = mapped_column(String(200), default="")
    budget: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    impressions: Mapped[int] = mapped_column(default=0)
    clicks: Mapped[int] = mapped_column(default=0)
    conversions: Mapped[int] = mapped_column(default=0)
    lead_count: Mapped[int] = mapped_column(default=0)
    spend: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)


class Content(Timestamps, Base):
    __tablename__ = "content"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','pending_approval','approved','published')"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(80))
    content_type: Mapped[str] = mapped_column(String(80), default="social_post")
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Report(Timestamps, Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    report_name: Mapped[str] = mapped_column(String(200))
    report_type: Mapped[str] = mapped_column(String(80))
    report_data: Mapped[dict] = mapped_column(JSON)


class WorkflowToken(Base):
    __tablename__ = "workflow_tokens"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)


class WorkflowEvent(Timestamps, Base):
    __tablename__ = "workflow_events"
    __table_args__ = (UniqueConstraint("user_id", "event_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(50))
    payload_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)


class ApprovalAction(Timestamps, Base):
    __tablename__ = "approval_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending_approval")
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
