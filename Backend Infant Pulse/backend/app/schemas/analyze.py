from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeVitalSigns(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heart_rate: float = Field(..., gt=0)
    spo2: float = Field(..., ge=0, le=100)
    temperature: float = Field(..., gt=0)
    respiration: float = Field(..., gt=0)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baby_id: int | str
    vitals: list[AnalyzeVitalSigns] = Field(min_length=1)
    ecg: list[float] = Field(min_length=1)
    sampling_rate: float = Field(default=250.0, gt=10)
    persist: bool = True


class AnalyzeBloodPressureSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    systolic: list[float] = Field(min_length=1)
    diastolic: list[float] = Field(min_length=1)


class AnalyzeResponse(BaseModel):
    baby_id: str
    baby_numeric_id: int
    ecg_signal: list[float]
    predicted_ecg: list[float]
    bp: AnalyzeBloodPressureSeries
    risk_score: float
    anomaly: str
    anomaly_score: float
    early_warning: bool
    status: str
    message: str
    fft_features: dict[str, float]
    explanation: dict[str, Any]
    components: dict[str, float]
