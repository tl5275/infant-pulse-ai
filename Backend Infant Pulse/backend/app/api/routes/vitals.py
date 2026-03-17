from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.schemas.vital import QueueResponse, VitalCreate, VitalRead
from app.services.babies import get_baby
from app.services.ingestion import QueueSaturatedError
from app.services.vitals import list_recent_vitals

router = APIRouter(tags=["vitals"])
DBSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/vitals",
    response_model=QueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue incoming vitals for processing",
)
async def ingest_vitals(
    payload: VitalCreate,
    request: Request,
    db: DBSession,
) -> QueueResponse:
    baby = await get_baby(db, payload.baby_id)
    if baby is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")

    ingestion_service = request.app.state.ingestion_service

    try:
        await ingestion_service.enqueue(payload)
    except QueueSaturatedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion queue is full",
        ) from exc

    return QueueResponse(
        status="queued",
        message="Vital sample accepted for asynchronous processing",
        queued_at=datetime.now(timezone.utc),
    )


@router.get(
    "/vitals/{baby_id}",
    response_model=list[VitalRead],
    summary="Get recent vitals for a baby",
)
async def get_recent_baby_vitals(
    baby_id: int,
    db: DBSession,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[VitalRead]:
    baby = await get_baby(db, baby_id)
    if baby is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")

    vitals = await list_recent_vitals(db, baby_id=baby_id, limit=limit)
    return [VitalRead.model_validate(vital) for vital in vitals]

