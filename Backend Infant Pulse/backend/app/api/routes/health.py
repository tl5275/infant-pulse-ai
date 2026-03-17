from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health check")
async def health_check(request: Request) -> dict[str, str | bool]:
    db_manager = request.app.state.db_manager
    monitoring_service = request.app.state.monitoring_service

    database_connected = await db_manager.check_connection()
    return {
        "status": "ok" if database_connected and monitoring_service.model_ready else "degraded",
        "database": "connected" if database_connected else "disconnected",
        "database_backend": db_manager.backend_name,
        "using_fallback": db_manager.using_fallback,
        "model": "loaded" if monitoring_service.model_ready else "unavailable",
        "stream": "ready",
    }
