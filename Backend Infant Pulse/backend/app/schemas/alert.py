from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    baby_id: int
    alert_type: str
    severity: str
    message: str
    timestamp: datetime
