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
    return HealthResponse(
        status="ok", service=request.app.title, version=request.app.version
    )


@router.get("/ready")
def readiness(request: Request):
    from fastapi.responses import JSONResponse
    from sqlalchemy import select
    from sqlalchemy.exc import SQLAlchemyError
    from app.models import User

    try:
        with request.app.state.session_factory() as db:
            db.execute(select(User.id).limit(1))
        return {"status": "ready"}
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Database is unavailable or migrations have not been applied"
            },
        )
