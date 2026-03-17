from fastapi import APIRouter, Request

from app.schemas.overview import OverviewResponse

router = APIRouter(tags=["overview"])


@router.get("/overview", response_model=OverviewResponse, summary="Get the live dashboard snapshot")
async def get_overview(request: Request) -> OverviewResponse:
    request_telemetry_service = request.app.state.request_telemetry_service
    overview = request_telemetry_service.refresh_all()
    return OverviewResponse.model_validate(overview)
