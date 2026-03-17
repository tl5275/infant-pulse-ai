from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class Baby(Base):
    __tablename__ = "babies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    nicu_bed: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    vitals: Mapped[list["Vital"]] = relationship(back_populates="baby", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="baby", cascade="all, delete-orphan")

