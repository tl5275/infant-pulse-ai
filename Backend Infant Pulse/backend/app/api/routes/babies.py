from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.schemas.baby import BabyRead
from app.services.babies import list_babies

router = APIRouter(tags=["babies"])
DBSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/babies", response_model=list[BabyRead], summary="List monitored babies")
async def get_babies(db: DBSession) -> list[BabyRead]:
    babies = await list_babies(db)
    return [BabyRead.model_validate(baby) for baby in babies]


@router.get("/baby/{baby_id}", summary="Get a fresh bedside payload for one baby")
async def get_baby_live_snapshot(baby_id: str, request: Request) -> dict[str, Any]:
    request_telemetry_service = request.app.state.request_telemetry_service
    payload = request_telemetry_service.get_baby_payload(baby_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Baby not found")
    return payload
