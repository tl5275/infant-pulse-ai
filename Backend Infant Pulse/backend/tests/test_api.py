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


def test_overview_changes_on_every_request(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        first = client.get("/overview")
        second = client.get("/overview")

        assert first.status_code == 200
        assert second.status_code == 200

        first_body = first.json()
        second_body = second.json()
        assert first_body["generated_at"] != second_body["generated_at"]

        first_baby = first_body["babies"][0]
        second_baby = second_body["babies"][0]
        assert first_baby["vitals"] != second_baby["vitals"]
        assert first_baby["ecgChartData"] != second_baby["ecgChartData"]


def test_baby_endpoint_changes_every_request(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        baby = client.get("/babies").json()[0]

        first = client.get(f"/baby/{baby['nicu_bed']}")
        second = client.get(f"/baby/{baby['nicu_bed']}")

        assert first.status_code == 200
        assert second.status_code == 200

        first_body = first.json()
        second_body = second.json()
        assert first_body["timestamp"] != second_body["timestamp"]
        assert first_body["ecg"] != second_body["ecg"]
        assert (
            first_body["heart_rate"],
            first_body["spo2"],
            first_body["temperature"],
            first_body["bp"],
        ) != (
            second_body["heart_rate"],
            second_body["spo2"],
            second_body["temperature"],
            second_body["bp"],
        )
