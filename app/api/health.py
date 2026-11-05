from typing import Literal
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Process liveness only; database readiness will be added in Phase 2."""
    return HealthResponse(status="ok", service=request.app.title, version=request.app.version)
