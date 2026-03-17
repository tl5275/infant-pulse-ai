from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OverviewVitals(BaseModel):
    heartRate: int
    spo2: int
    respiration: int
    temperature: float


class OverviewTrend(BaseModel):
    heartRate: str
    spo2: str


class OverviewPrediction(BaseModel):
    predictedHeartRate: int
    predictedSpo2: int
    riskLevel: str
    reasons: list[str]
    anomalyLabel: str
    earlyWarning: bool


class OverviewChartPoint(BaseModel):
    label: str
    heartRate: float | None = None
    predictedHeartRate: float | None = None
    spo2: float | None = None
    predictedSpo2: float | None = None


class OverviewECGPoint(BaseModel):
    label: str
    ecg: float | None = None
    predictedEcg: float | None = None


class OverviewBPPoint(BaseModel):
    label: str
    systolic: float | None = None
    predictedSystolic: float | None = None
    diastolic: float | None = None
    predictedDiastolic: float | None = None


class OverviewBaby(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    numericId: int
    bed: str
    name: str
    ageLabel: str
    gestation: str
    status: str
    riskScore: int
    vitals: OverviewVitals
    trend: OverviewTrend
    prediction: OverviewPrediction
    chartData: list[OverviewChartPoint]
    ecgChartData: list[OverviewECGPoint]
    bpChartData: list[OverviewBPPoint]
    lastUpdated: str


class OverviewAlert(BaseModel):
    id: str
    babyId: str
    type: str
    severity: str
    title: str
    message: str
    timestamp: datetime


class OverviewResponse(BaseModel):
    generated_at: datetime
    babies: list[OverviewBaby]
    alerts: list[OverviewAlert]
