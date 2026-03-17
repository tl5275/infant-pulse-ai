"""FastAPI entrypoint for the Infant Pulse ML engine."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routes import router
from services.prediction_service import get_prediction_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Warm model artifacts during application startup."""
    get_prediction_service()
    yield


app = FastAPI(
    title="Infant Pulse ML Engine",
    version="1.0.0",
    description="NICU-focused ECG forecasting, anomaly detection, and risk scoring service.",
    lifespan=lifespan,
)
app.include_router(router)
