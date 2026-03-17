from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BabyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    nicu_bed: str
    created_at: datetime

