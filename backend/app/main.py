"""Application factory.

Run with:  uvicorn app.main:create_app --factory --reload
A factory (instead of a module-level app) lets tests build an app with their
own Settings, e.g. an in-memory database, without touching the real one.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_error_handlers
from app.api.health import router as health_router
from app.core.config import Settings
from app.core.logging_config import configure_logging, get_logger
from app.infrastructure.db.init_db import init_database
from app.infrastructure.db.session import create_db_engine, create_session_factory

API_PREFIX = "/api"
logger = get_logger("main")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and wire the FastAPI application."""
    settings = settings or Settings.from_env()
    configure_logging()

    engine = create_db_engine(settings.database_url)
    init_database(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info("Auralis API started (LLM enabled: %s)", settings.llm_enabled)
        yield
        engine.dispose()

    app = FastAPI(title="Auralis API", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(health_router, prefix=API_PREFIX)
    return app
