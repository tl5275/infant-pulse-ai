from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VitalCreate(BaseModel):
    baby_id: int = Field(ge=1)
    heart_rate: int = Field(ge=0, le=300)
    spo2: int = Field(ge=0, le=100)
    temperature: float = Field(ge=20.0, le=45.0)
    resp_rate: int = Field(ge=0, le=120)
    timestamp: datetime | None = None


class VitalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    baby_id: int
    heart_rate: int
    spo2: int
    temperature: float
    resp_rate: int
    timestamp: datetime


class QueueResponse(BaseModel):
    status: str
    message: str
    queued_at: datetime

