from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Register(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password", mode="before")
    @classmethod
    def preserve_password(cls, value):
        # Field-level whitespace is significant for passwords.
        return value

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class Login(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class Profile(StrictModel):
    name: str = Field(min_length=1, max_length=120)


class PasswordChange(StrictModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    created_at: datetime


class ClientIn(StrictModel):
    company_name: str = Field(min_length=1, max_length=200)
    website: HttpUrl | None = None
    industry: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=10000)


class LeadIn(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    source: str = Field(default="manual", min_length=1, max_length=120)
    status: Literal["new", "qualified", "contacted", "won", "lost"] = "new"
    lead_score: int = Field(default=0, ge=0, le=100)


class CampaignIn(StrictModel):
    campaign_name: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=80)
    objective: str = Field(default="", max_length=200)
    budget: Decimal = Field(default=0, ge=0, max_digits=14, decimal_places=2)
    status: Literal["draft", "active", "paused", "completed"] = "draft"
    impressions: int = Field(default=0, ge=0, le=2_000_000_000)
    clicks: int = Field(default=0, ge=0, le=2_000_000_000)
    conversions: int = Field(default=0, ge=0, le=2_000_000_000)
    lead_count: int = Field(default=0, ge=0, le=2_000_000_000)
    spend: Decimal = Field(default=0, ge=0, max_digits=14, decimal_places=2)
    revenue: Decimal = Field(default=0, ge=0, max_digits=14, decimal_places=2)


class ContentIn(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=80)
    content_type: str = Field(default="social_post", min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=50000)
    scheduled_at: datetime | None = None

    @field_validator("scheduled_at")
    @classmethod
    def aware_time(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("Include a timezone, for example +00:00")
        return value


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    created_at: datetime
    updated_at: datetime


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_name: str
    website: str | None
    industry: str
    description: str
    created_at: datetime
    updated_at: datetime


class LeadOut(LeadIn, RecordOut):
    pass


class CampaignOut(CampaignIn, RecordOut):
    pass


class ContentOut(ContentIn, RecordOut):
    status: str


class ReportOut(RecordOut):
    report_name: str
    report_type: str
    report_data: dict


class ReportRequest(StrictModel):
    report_name: str = Field(
        default="Performance snapshot", min_length=1, max_length=200
    )


class AgentRequest(StrictModel):
    agent: Literal["research", "content", "campaign", "lead", "reporting", "strategist"]
    question: str = Field(
        default="Recommend the next best marketing actions.",
        min_length=1,
        max_length=2000,
    )


class AgentResult(BaseModel):
    summary: str
    insights: list[str]
    recommendations: list[str]
    evidence: list[str]
    limitations: list[str]
    draft_content: str | None


class LeadWebhook(LeadIn):
    event_id: str = Field(min_length=1, max_length=120)
    client_id: int = Field(gt=0)


class ReportWebhook(ReportRequest):
    event_id: str = Field(min_length=1, max_length=120)
    client_id: int = Field(gt=0)


class ActionIn(StrictModel):
    client_id: int = Field(gt=0)
    action: Literal["publish_content", "change_budget"]
    resource_id: int = Field(gt=0)
    new_budget: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    action: str
    resource_id: int
    payload: dict
    status: str
    created_at: datetime
    external_reference: str | None


class ActionDecision(StrictModel):
    decision: Literal["approve", "reject"]


class ActionComplete(StrictModel):
    external_reference: str = Field(min_length=1, max_length=200)
