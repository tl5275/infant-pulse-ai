from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vital import Vital
from app.schemas.vital import VitalCreate


async def list_recent_vitals(session: AsyncSession, baby_id: int, limit: int) -> list[Vital]:
    result = await session.scalars(
        select(Vital)
        .where(Vital.baby_id == baby_id)
        .order_by(Vital.timestamp.desc())
        .limit(limit)
    )
    return list(result.all())


def build_vital_model(payload: VitalCreate) -> Vital:
    timestamp = payload.timestamp or datetime.now(timezone.utc)
    return Vital(
        baby_id=payload.baby_id,
        heart_rate=payload.heart_rate,
        spo2=payload.spo2,
        temperature=payload.temperature,
        resp_rate=payload.resp_rate,
        timestamp=timestamp,
    )

