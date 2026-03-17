from typing import Annotated

from fastapi import APIRouter, Depends
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

