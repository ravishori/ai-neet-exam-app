from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.database import check_database_connection, engine
from app.core.exceptions import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.shared.responses import envelope

settings = get_settings()
configure_logging(settings.environment)
logger = get_logger("startup")

redis_client: redis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    logger.info("starting_up", environment=settings.environment)
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    yield
    logger.info("shutting_down")
    if redis_client:
        await redis_client.aclose()
    await engine.dispose()


app = FastAPI(
    title="Trinetra AI Learning OS API",
    description="Modular monolith backend for TALOS. See CLAUDE.md and docs/decisions/ for frozen architecture.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/health")
async def health():
    return envelope(success=True, data={"status": "ok"})


@app.get("/live")
async def live():
    return envelope(success=True, data={"status": "alive"})


@app.get("/ready")
async def ready():
    db_ok = await check_database_connection()
    redis_ok = False
    if redis_client:
        try:
            redis_ok = await redis_client.ping()
        except Exception:
            redis_ok = False

    ok = db_ok and redis_ok
    return envelope(
        success=ok,
        data={"database": db_ok, "redis": redis_ok},
        status_code=200 if ok else 503,
    )
