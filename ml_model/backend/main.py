"""FastAPI backend for live neonatal ECG monitoring."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ML_ENGINE_DIR = PROJECT_ROOT / "ml-engine"
if str(ML_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ML_ENGINE_DIR))

from predictor import get_predictor

from backend.websocket import attach_live_websocket


class VitalSigns(BaseModel):
    """One bedside vitals reading bundled with an ECG segment."""

    heart_rate: float = Field(..., gt=0)
    spo2: float = Field(..., ge=0, le=100)
    temperature: float = Field(..., gt=0)
    respiration: float = Field(..., gt=0)


class AnalyzeRequest(BaseModel):
    """Incoming payload posted by the simulator."""

    baby_id: str
    vitals: list[VitalSigns]
    ecg: list[float]
    sampling_rate: float = Field(default=250.0, gt=10)


class AnalyzeResponse(BaseModel):
    """Live inference result returned to the dashboard and simulator."""

    baby_id: str
    ecg_signal: list[float]
    predicted_ecg: list[float]
    risk_score: float
    anomaly: str
    early_warning: bool
    status: str
    message: str
    fft_features: dict[str, float]


latest_data: dict[str, object] = {}
latest_data_lock = Lock()


def get_latest_data() -> dict[str, object]:
    """Return the latest prediction snapshot or a waiting-state payload."""
    with latest_data_lock:
        if latest_data:
            return dict(latest_data)

    return {
        "baby_id": "waiting",
        "ecg_signal": [],
        "predicted_ecg": [],
        "risk_score": 0.0,
        "anomaly": "normal",
        "early_warning": False,
        "status": "WAITING",
        "message": "Waiting for simulator data...",
        "fft_features": {
            "dominant_frequency": 0.0,
            "spectral_energy": 0.0,
        },
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Warm the ML models during API startup."""
    get_predictor()
    yield


app = FastAPI(
    title="Infant Pulse Live Monitoring API",
    version="2.0.0",
    lifespan=lifespan,
)
attach_live_websocket(app, get_latest_data)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return a minimal liveness payload."""
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_payload(request: AnalyzeRequest) -> dict[str, object]:
    """Analyze the latest ECG segment and cache it for WebSocket subscribers."""
    try:
        result = get_predictor().predict(
            baby_id=request.baby_id,
            vitals_history=[item.model_dump() for item in request.vitals],
            ecg_signal=request.ecg,
            sampling_rate=request.sampling_rate,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    global latest_data
    with latest_data_lock:
        latest_data = dict(result)
    return result
