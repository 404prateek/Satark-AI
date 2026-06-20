"""
Satark AI – FastAPI application entry point.
"""

from __future__ import annotations

import logging
import sys

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware

from backend.armoriq.middleware import ArmorIQMiddleware
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.models.database import Base, engine
from backend.routers import auth as auth_router
from backend.routers import analyze as analyze_router
from backend.routers import armoriq_webhook
from backend.routers import history as history_router
# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

settings = get_settings()


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run startup tasks, yield control to the app, then run shutdown tasks."""
    logger.info("Starting up %s v%s …", settings.APP_NAME, settings.APP_VERSION)

    # Import all models so SQLAlchemy registers them with Base.metadata
    from backend.models import user  # noqa: F401 – side-effect import
    from backend.armoriq import audit_logger  # noqa: F401 – registers ArmorIQLog with Base

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables verified / created.")
    except Exception as exc:
        logger.error("Failed to connect to the database: %s", exc)
        logger.warning("Starting without a database connection!")

    yield  # ← application runs here

    logger.info("Shutting down …")
    await engine.dispose()


# ── Application factory ───────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Satark AI – Intelligent Phishing Detection Platform API. "
            "Analyse URLs, emails, and domains for phishing indicators."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── ArmorIQ Security Middleware ───────────────────────────────────────────
    # Must be added AFTER CORSMiddleware so CORS preflight OPTIONS requests
    # are resolved before ArmorIQ reads the request body.
    app.add_middleware(ArmorIQMiddleware)

    # ── Global exception handlers ─────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred."},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth_router.router, prefix="/api/v1")
    app.include_router(analyze_router.router, prefix="/api/v1/analyze", tags=["Analyze"])
    app.include_router(history_router.router, prefix="/api/v1")
    app.include_router(armoriq_webhook.router, prefix="/api/v1/armoriq", tags=["ArmorIQ Webhook"])

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"], summary="Health check")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": settings.APP_NAME}

    return app


app = create_app()
