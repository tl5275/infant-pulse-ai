from fastapi import APIRouter, Request

from app.schemas.overview import OverviewResponse

router = APIRouter(tags=["overview"])


@router.get("/overview", response_model=OverviewResponse, summary="Get the live dashboard snapshot")
async def get_overview(request: Request) -> OverviewResponse:
    live_monitor = request.app.state.live_monitor
    return OverviewResponse.model_validate(live_monitor.get_overview())
