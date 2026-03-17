"""HTTP routes for the Infant Pulse ML engine."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import AnalyzeRequest, AnalyzeResponse
from services.prediction_service import get_prediction_service

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return a minimal liveness response."""
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_payload(request: AnalyzeRequest) -> dict[str, object]:
    """Analyze one infant payload and return the fused AI output."""
    try:
        service = get_prediction_service()
        return service.analyze(
            baby_id=request.baby_id,
            vitals_history=[item.model_dump() for item in request.vitals],
            ecg=request.ecg,
            sampling_rate=request.sampling_rate,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
