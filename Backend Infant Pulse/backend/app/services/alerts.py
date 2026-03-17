from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert


async def list_alerts(session: AsyncSession, baby_id: int | None, limit: int) -> list[Alert]:
    query = select(Alert).order_by(Alert.timestamp.desc()).limit(limit)
    if baby_id is not None:
        query = query.where(Alert.baby_id == baby_id)

    result = await session.scalars(query)
    return list(result.all())

