from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse

router = APIRouter(tags=["analysis"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Persist a live reading and run ECG inference",
)
async def analyze_payload(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    monitoring_service = request.app.state.monitoring_service
    try:
        return await monitoring_service.analyze_payload(payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
