import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.api import agents, auth, automation, clients
from app.api.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.database import make_engine
from app.core.security import csrf_guard

logger = logging.getLogger("marketpilot")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    application = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Marketing workspace API with revocable sessions, owned records, structured AI and approval-controlled automation.",
        lifespan=lifespan,
        dependencies=[Depends(csrf_guard)],
    )
    application.state.settings = settings
    application.state.engine = engine
    application.state.session_factory = sessionmaker(
        bind=engine, expire_on_commit=False
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.cors_origins],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Accept", "Content-Type", "X-MarketPilot-CSRF"],
    )
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts
    )

    @application.middleware("http")
    async def request_logging(request, call_next):
        request_id = uuid.uuid4().hex
        start = time.monotonic()
        # Stream the body with a bound, including chunked requests. Never log body/cookies.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 1_048_576:
                return JSONResponse(
                    status_code=413, content={"detail": "Request body exceeds 1 MB"}
                )
        request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        logger.info(
            "request_id=%s method=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            response.status_code,
            (time.monotonic() - start) * 1000,
        )
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Pydantic's default errors include submitted input, which may contain passwords.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                    for e in exc.errors()
                ]
            },
        )

    @application.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return JSONResponse(
            status_code=409,
            content={"detail": "The record conflicts with existing data"},
        )

    for router in (
        health_router,
        auth.router,
        clients.router,
        agents.router,
        automation.router,
    ):
        application.include_router(router, prefix=settings.api_prefix)
    return application


app = create_app()
