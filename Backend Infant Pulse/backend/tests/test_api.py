import time
from math import sin
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def build_test_client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "test.db"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
        enable_db_seed=True,
        initial_baby_count=5,
        simulator_baby_count=5,
    )
    app = create_app(settings)
    return TestClient(app)


def test_list_babies_and_store_vitals(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        babies_response = client.get("/babies")
        assert babies_response.status_code == 200
        babies = babies_response.json()
        assert len(babies) == 5

        baby_id = babies[0]["id"]
        ingest_response = client.post(
            "/vitals",
            json={
                "baby_id": baby_id,
                "heart_rate": 156,
                "spo2": 96,
                "temperature": 36.8,
                "resp_rate": 40,
            },
        )
        assert ingest_response.status_code == 202

        time.sleep(0.2)

        vitals_response = client.get(f"/vitals/{baby_id}")
        assert vitals_response.status_code == 200
        vitals = vitals_response.json()
        assert len(vitals) >= 1
        assert vitals[0]["baby_id"] == baby_id


def test_alert_generation(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        baby_id = client.get("/babies").json()[0]["id"]
        ingest_response = client.post(
            "/vitals",
            json={
                "baby_id": baby_id,
                "heart_rate": 176,
                "spo2": 88,
                "temperature": 37.9,
                "resp_rate": 44,
            },
        )
        assert ingest_response.status_code == 202

        time.sleep(0.2)

        alerts_response = client.get("/alerts")
        assert alerts_response.status_code == 200
        alerts = alerts_response.json()
        severities = {alert["severity"] for alert in alerts}
        alert_types = {alert["alert_type"] for alert in alerts}

        assert "CRITICAL" in severities
        assert "LOW_SPO2" in alert_types
        assert "HIGH_HEART_RATE" in alert_types
        assert "HIGH_TEMPERATURE" in alert_types


def test_analyze_returns_bp_series(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        baby_id = client.get("/babies").json()[0]["id"]
        vitals = [
            {
                "heart_rate": 142 + index,
                "spo2": 97 - (index % 2),
                "temperature": 36.7 + (index * 0.05),
                "respiration": 40 + index,
            }
            for index in range(6)
        ]
        ecg = [round(sin(index / 7), 6) for index in range(180)]

        analyze_response = client.post(
            "/analyze",
            json={
                "baby_id": baby_id,
                "vitals": vitals,
                "ecg": ecg,
                "persist": False,
            },
        )

        assert analyze_response.status_code == 200
        body = analyze_response.json()
        assert body["baby_numeric_id"] == baby_id
        assert "bp" in body
        assert len(body["bp"]["systolic"]) == len(vitals)
        assert len(body["bp"]["diastolic"]) == len(vitals)
        assert all(60 <= value <= 90 for value in body["bp"]["systolic"])
        assert all(30 <= value <= 60 for value in body["bp"]["diastolic"])
        assert all(
            systolic > diastolic
            for systolic, diastolic in zip(body["bp"]["systolic"], body["bp"]["diastolic"])
        )
