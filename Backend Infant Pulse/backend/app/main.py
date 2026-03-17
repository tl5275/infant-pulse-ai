from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai import get_ml_service
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.database.session import DatabaseManager
from app.services.babies import list_babies, seed_default_babies
from app.services.ingestion import IngestionService
from app.services.live_monitor import LiveMonitorService
from app.services.monitoring import MonitoringService
from app.services.request_telemetry import RequestTelemetryService
from app.websocket.manager import ConnectionManager
from app.websocket.routes import router as websocket_router


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    setup_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db_manager = DatabaseManager(
            database_url=app_settings.database_url,
            fallback_url=app_settings.sqlite_fallback_url,
        )
        websocket_manager = ConnectionManager()
        live_websocket_manager = ConnectionManager()
        live_monitor = LiveMonitorService()
        ml_service = get_ml_service()

        await db_manager.initialize()
        await db_manager.create_tables()
        ml_service.load_models()

        if app_settings.enable_db_seed:
            async with db_manager.session_factory() as session:
                await seed_default_babies(session, app_settings.initial_baby_count)

        async with db_manager.session_factory() as session:
            babies = await list_babies(session)

        monitoring_service = MonitoringService(
            session_factory=db_manager.session_factory,
            ml_service=ml_service,
            event_broadcast=websocket_manager.broadcast,
            live_broadcast=live_websocket_manager.broadcast,
            live_monitor=live_monitor,
            recent_vitals_limit=app_settings.recent_vitals_limit,
        )
        await monitoring_service.bootstrap()
        request_telemetry_service = RequestTelemetryService(live_monitor=live_monitor)
        request_telemetry_service.seed_babies(babies)

        ingestion_service = IngestionService(
            monitoring_service=monitoring_service,
            queue_size=app_settings.ingest_queue_size,
        )

        app.state.settings = app_settings
        app.state.db_manager = db_manager
        app.state.websocket_manager = websocket_manager
        app.state.live_websocket_manager = live_websocket_manager
        app.state.live_monitor = live_monitor
        app.state.ml_service = ml_service
        app.state.monitoring_service = monitoring_service
        app.state.request_telemetry_service = request_telemetry_service
        app.state.ingestion_service = ingestion_service

        if app_settings.enable_background_worker:
            await ingestion_service.start()

        yield

        if app_settings.enable_background_worker:
            await ingestion_service.stop()

        await db_manager.dispose()

    app = FastAPI(title=app_settings.app_name, debug=app_settings.debug, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(websocket_router)
    return app


app = create_app()
