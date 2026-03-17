from fastapi import APIRouter

from app.api.routes import alerts, analyze, babies, health, overview, vitals

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(babies.router)
api_router.include_router(vitals.router)
api_router.include_router(alerts.router)
api_router.include_router(analyze.router)
api_router.include_router(overview.router)
