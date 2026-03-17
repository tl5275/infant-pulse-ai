from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.baby import Baby


async def list_babies(session: AsyncSession) -> list[Baby]:
    result = await session.scalars(select(Baby).order_by(Baby.nicu_bed.asc()))
    return list(result.all())


async def get_baby(session: AsyncSession, baby_id: int) -> Baby | None:
    return await session.get(Baby, baby_id)


async def seed_default_babies(session: AsyncSession, count: int) -> None:
    existing_count = await session.scalar(select(func.count(Baby.id)))
    if existing_count is None:
        existing_count = 0

    if existing_count >= count:
        return

    for index in range(existing_count + 1, count + 1):
        session.add(Baby(name=f"Infant {index}", nicu_bed=f"NICU-{100 + index}"))

    await session.commit()

