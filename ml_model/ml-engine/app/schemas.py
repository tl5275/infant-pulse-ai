"""Pydantic schemas for the Infant Pulse API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VitalSigns(BaseModel):
    """One timestamped set of bedside vital signs."""

    model_config = ConfigDict(extra="forbid")

    heart_rate: float = Field(..., gt=0)
    spo2: float = Field(..., ge=0, le=100)
    temperature: float = Field(..., gt=0)
    respiration: float = Field(..., gt=0)


class AnalyzeRequest(BaseModel):
    """Input payload for the `/analyze` endpoint."""

    model_config = ConfigDict(extra="forbid")

    baby_id: str
    vitals: list[VitalSigns]
    ecg: list[float]
    sampling_rate: float = Field(default=250.0, gt=10)


class AnomalyOutput(BaseModel):
    """Serialized anomaly detector response."""

    anomaly_score: float
    label: str


class ExplanationOutput(BaseModel):
    """Structured explanation for downstream UI or audit consumers."""

    summary: str
    top_reasons: list[str]
    feature_snapshot: dict[str, float]
    trend_context: dict[str, float]
    anomaly_context: dict[str, Any]
    warning_context: dict[str, Any]
    model_sources: dict[str, str]


class AnalyzeResponse(BaseModel):
    """Full API response for one analysis request."""

    baby_id: str
    anomaly: AnomalyOutput
    risk_score: float
    status: str
    predicted_ecg: list[float]
    early_warning: bool
    message: str
    explanation: ExplanationOutput
