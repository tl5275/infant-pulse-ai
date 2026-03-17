from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class DatabaseManager:
    def __init__(self, database_url: str, fallback_url: str) -> None:
        self.requested_database_url = database_url
        self.fallback_database_url = fallback_url
        self.database_url: str | None = None
        self.backend_name = "uninitialized"
        self.using_fallback = False
        self.engine = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None

    async def initialize(self) -> None:
        last_error: Exception | None = None
        for index, candidate in enumerate(self._candidate_urls()):
            engine = None
            try:
                normalized = self._normalize_database_url(candidate)
                self._ensure_sqlite_directory(normalized)
                engine = create_async_engine(normalized, pool_pre_ping=True)
                async with engine.begin() as connection:
                    await connection.execute(text("SELECT 1"))

                self.engine = engine
                self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
                self.database_url = normalized
                self.backend_name = "sqlite" if normalized.startswith("sqlite") else "postgresql"
                self.using_fallback = index > 0
                return
            except Exception as exc:
                last_error = exc
                if engine is not None:
                    await engine.dispose()

        raise RuntimeError("Unable to connect to either the primary or fallback database.") from last_error

    async def create_tables(self) -> None:
        if self.engine is None:
            raise RuntimeError("Database engine is not initialized.")

        from app.models import alert, baby, vital  # noqa: F401

        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def check_connection(self) -> bool:
        if self.engine is None:
            return False

        async with self.engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
        return True

    async def dispose(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()

    def _candidate_urls(self) -> list[str]:
        candidates = [self.requested_database_url]
        if self.fallback_database_url not in candidates:
            candidates.append(self.fallback_database_url)
        return candidates

    def _normalize_database_url(self, database_url: str) -> str:
        if database_url.startswith("sqlite:///"):
            return database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return database_url

    def _ensure_sqlite_directory(self, database_url: str) -> None:
        if not database_url.startswith("sqlite+aiosqlite:///"):
            return

        database_path = Path(database_url.replace("sqlite+aiosqlite:///", "", 1))
        if database_path.drive:
            target = database_path
        else:
            target = Path.cwd() / database_path
        target.parent.mkdir(parents=True, exist_ok=True)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.db_manager.session_factory
    async with session_factory() as session:
        yield session
