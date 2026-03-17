from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "Backend Infant Pulse" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai import InferenceInput, get_ml_service, simulate_ecg_waveform  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def build_test_client(tmp_path: Path) -> TestClient:
    sqlite_path = tmp_path / "pipeline.db"
    settings = Settings(
        database_url="postgresql+asyncpg://invalid:invalid@127.0.0.1:6543/infant_pulse",
        sqlite_fallback_url=f"sqlite+aiosqlite:///{sqlite_path.as_posix()}",
        enable_db_seed=True,
        initial_baby_count=5,
        simulator_baby_count=5,
        enable_background_worker=True,
        recent_vitals_limit=24,
    )
    app = create_app(settings)
    return TestClient(app)


def build_analyze_payload(baby_id: int) -> dict[str, object]:
    vitals = []
    for index in range(12):
        vitals.append(
            {
                "heart_rate": 138 + index,
                "spo2": 97 - (index % 2),
                "temperature": 36.7 + (index * 0.02),
                "respiration": 41 + (index % 3),
            }
        )

    latest = vitals[-1]
    ecg = simulate_ecg_waveform(
        heart_rate=latest["heart_rate"],
        anomaly=False,
    )
    return {
        "baby_id": baby_id,
        "vitals": vitals,
        "ecg": ecg.round(6).tolist(),
        "sampling_rate": 250.0,
        "persist": True,
    }


def test_backend_health_and_database_fallback(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()

        assert payload["status"] == "ok"
        assert payload["database"] == "connected"
        assert payload["database_backend"] == "sqlite"
        assert payload["using_fallback"] is True
        assert payload["model"] == "loaded"


def test_database_connection_and_overview_payload(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        overview_response = client.get("/overview")
        assert overview_response.status_code == 200

        overview = overview_response.json()
        assert len(overview["babies"]) == 5
        assert "generated_at" in overview
        assert client.app.state.db_manager.backend_name == "sqlite"
        assert client.app.state.monitoring_service.model_ready is True


def test_ml_inference_service() -> None:
    service = get_ml_service()
    vitals_history = [
        {
            "heart_rate": 140.0 + index,
            "spo2": 97.0,
            "temperature": 36.8,
            "respiration": 42.0,
        }
        for index in range(12)
    ]
    ecg = simulate_ecg_waveform(heart_rate=vitals_history[-1]["heart_rate"], anomaly=False)

    result = service.run_inference(
        InferenceInput(
            baby_id="NICU-101",
            vitals_history=vitals_history,
            ecg=ecg.round(6).tolist(),
            sampling_rate=250.0,
        )
    )

    assert result["baby_id"] == "NICU-101"
    assert result["status"] in {"STABLE", "WARNING", "CRITICAL"}
    assert "predicted_ecg" in result
    assert len(result["predicted_ecg"]) > 0


def test_api_response_and_persistence(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        baby = client.get("/babies").json()[0]
        response = client.post("/analyze", json=build_analyze_payload(baby["id"]))
        assert response.status_code == 200

        result = response.json()
        assert result["baby_numeric_id"] == baby["id"]
        assert result["baby_id"] == baby["nicu_bed"]
        assert result["anomaly"] in {"normal", "anomaly"}

        overview = client.get("/overview").json()
        snapshot = next(item for item in overview["babies"] if item["numericId"] == baby["id"])
        assert snapshot["id"] == baby["nicu_bed"]
        assert snapshot["prediction"]["riskLevel"] in {"STABLE", "WARNING", "CRITICAL"}


def test_websocket_live_snapshot(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        baby = client.get("/babies").json()[0]

        with client.websocket_connect("/ws/live") as websocket:
            initial_snapshot = websocket.receive_json()
            assert len(initial_snapshot["babies"]) == 5

            response = client.post("/analyze", json=build_analyze_payload(baby["id"]))
            assert response.status_code == 200

            updated_snapshot = websocket.receive_json()
            updated_baby = next(item for item in updated_snapshot["babies"] if item["numericId"] == baby["id"])
            assert updated_baby["id"] == baby["nicu_bed"]
            assert updated_baby["ecgChartData"]
