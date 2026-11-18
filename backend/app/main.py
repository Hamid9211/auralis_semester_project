"""Application factory (composition root).

Run with:  uvicorn app.main:create_app --factory --reload
A factory (instead of a module-level app) lets tests build an app with their
own Settings, e.g. an in-memory database, without touching the real one.
This is the only place where concrete infrastructure classes are chosen and
injected into the services (Dependency Inversion).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from app.api.error_handlers import register_error_handlers
from app.api.health import router as health_router
from app.api.reports import router as reports_router
from app.core.config import Settings
from app.core.logging_config import configure_logging, get_logger
from app.domain.lab_reports import ExplanationGenerator, TextExtractor
from app.infrastructure.db.init_db import init_database
from app.infrastructure.db.report_repository import SqlLabReportRepository
from app.infrastructure.db.session import create_db_engine, create_session_factory
from app.infrastructure.explanation_factory import ExplanationGeneratorFactory
from app.infrastructure.pymupdf_extractor import PyMuPDFTextExtractor
from app.services.report_service import ReportService, ReportWorker

# pylint: disable=unsubscriptable-object
# False positive on sessionmaker[Session]; see the note in session.py.

API_PREFIX = "/api"
REPORT_WORKER_COUNT = 2
logger = get_logger("main")


def build_report_service(settings: Settings, session_factory: sessionmaker[Session], *,
                         text_extractor: TextExtractor | None = None,
                         explanation_generator: ExplanationGenerator | None = None,
                         ) -> ReportService:
    """Wire ReportService with its concrete dependencies (overridable in tests)."""
    factory = ExplanationGeneratorFactory(settings)
    return ReportService(
        repository=SqlLabReportRepository(session_factory),
        extractor=text_extractor or PyMuPDFTextExtractor(),
        generator=explanation_generator or factory.create(),
        fallback=factory.create_fallback(),
        max_upload_bytes=settings.max_upload_bytes,
    )


def create_app(settings: Settings | None = None, *,
               text_extractor: TextExtractor | None = None,
               explanation_generator: ExplanationGenerator | None = None) -> FastAPI:
    """Build and wire the FastAPI application."""
    settings = settings or Settings.from_env()
    configure_logging()

    engine = create_db_engine(settings.database_url)
    init_database(engine)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # The service owns an asyncio.Queue and Lock, so it is created inside the
        # running event loop, together with the background workers.
        service = build_report_service(settings, session_factory,
                                       text_extractor=text_extractor,
                                       explanation_generator=explanation_generator)
        app.state.report_service = service
        workers = [
            asyncio.create_task(ReportWorker(service, f"report-worker-{i}").run())
            for i in range(1, REPORT_WORKER_COUNT + 1)
        ]
        logger.info("Auralis API started (LLM enabled: %s, report workers: %d)",
                    settings.llm_enabled, len(workers))
        yield
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        engine.dispose()

    app = FastAPI(title="Auralis API", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(reports_router, prefix=API_PREFIX)
    return app
