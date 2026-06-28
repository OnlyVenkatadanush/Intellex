import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.config import settings
from backend.app.database import engine, Base
from backend.app.presentation.api.auth import router as auth_router
from backend.app.presentation.api.sessions import router as sessions_router
from backend.app.presentation.api.documents import router as documents_router
from backend.app.presentation.api.health import router as health_router
from backend.app.presentation.api.analytics import router as analytics_router
# Import graph models so SQLAlchemy creates their tables on startup
import backend.app.infrastructure.db.graph_models  # noqa: F401

# ── Structured Logging Setup ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%SZ"
)
logger = logging.getLogger("intellex.api")


# ── Application Lifespan (startup/shutdown hooks) ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database tables
    logger.info("Initializing Intellex Research API...")
    Base.metadata.create_all(bind=engine)
    logger.info(
        f"Database initialized. Environment: {settings.ENVIRONMENT}. "
        f"DB: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'sqlite'}"
    )
    yield
    # Shutdown
    logger.info("Intellex Research API shutting down.")


# ── FastAPI Application ───────────────────────────────────────────────────────
app = FastAPI(
    title="Intellex – Multi-Agent Autonomous Research Platform",
    description="Production-grade autonomous research platform utilizing multi-agent orchestration.",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
)

# ── CORS Middleware (environment-aware) ────────────────────────────────────────
# In development: permissive. In production: strict origin list from env var.
cors_origins = settings.cors_origins_list
if not settings.is_production:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
)


# ── Correlation ID Middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id

    start_time = time.monotonic()
    response: Response = await call_next(request)
    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

    logger.info(
        f"method={request.method} path={request.url.path} "
        f"status={response.status_code} duration_ms={elapsed_ms} "
        f"correlation_id={correlation_id}"
    )
    return response


# ── Register Routers ──────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(documents_router)
app.include_router(health_router)
app.include_router(analytics_router)


# ── Root Endpoint ─────────────────────────────────────────────────────────────
@app.get("/", tags=["root"])
async def root():
    return {
        "status": "online",
        "service": "Intellex Research API Engine",
        "version": "1.1.0",
        "environment": settings.ENVIRONMENT,
        "docs": "/api/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=not settings.is_production,
        log_level="info"
    )
