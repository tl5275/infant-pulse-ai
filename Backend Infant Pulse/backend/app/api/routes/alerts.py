from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.schemas.alert import AlertRead
from app.services.alerts import list_alerts

router = APIRouter(tags=["alerts"])
DBSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/alerts", response_model=list[AlertRead], summary="List generated alerts")
async def get_alerts(
    db: DBSession,
    baby_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AlertRead]:
    alerts = await list_alerts(db, baby_id=baby_id, limit=limit)
    return [AlertRead.model_validate(alert) for alert in alerts]

