"""Unified runner for the Infant Pulse ML engine."""

from __future__ import annotations

import json
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import uvicorn
from sklearn.exceptions import InconsistentVersionWarning

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from data.sample_dataset import generate_sample_dataset
from data.simulator import InfantPulseSimulator, generate_training_payloads, generate_training_signals
from models.anomaly_model import DEFAULT_ANOMALY_PATH, train_anomaly_model
from models.lstm_model import DEFAULT_LSTM_PATH, train_lstm_model
from services.feature_engineering import build_feature_vector
from services.prediction_service import PredictionService
from utils.preprocessing import preprocess_ecg_signal

API_HOST = "127.0.0.1"
API_PORT = 8000
API_URL = f"http://{API_HOST}:{API_PORT}/analyze"
HEALTH_URL = f"http://{API_HOST}:{API_PORT}/health"
SIMULATOR_INTERVAL_SECONDS = 1.0
SIMULATOR_BABIES = 5


def log_info(message: str) -> None:
    """Print a standard informational log line."""
    print(f"[INFO] {message}", flush=True)


def log_error(message: str) -> None:
    """Print a standard error log line."""
    print(f"[ERROR] {message}", flush=True)


def generate_dataset(output_dir: str | Path = BASE_DIR / "artifacts", num_samples: int = 120) -> dict[str, Path]:
    """Generate a synthetic dataset for local training artifacts."""
    return generate_sample_dataset(output_dir=output_dir, num_samples=num_samples)


def generate_signal(simulator: InfantPulseSimulator | None = None) -> dict[str, Any]:
    """Generate one synthetic payload for smoke testing."""
    active_simulator = simulator or InfantPulseSimulator(num_babies=1)
    return active_simulator.get_next_payload("baby_01")


def analyze(service: PredictionService, payload: dict[str, Any]) -> dict[str, Any]:
    """Run one payload through the local prediction service."""
    return service.analyze(
        baby_id=str(payload["baby_id"]),
        vitals_history=payload["vitals"],
        ecg=payload["ecg"],
        sampling_rate=float(payload.get("sampling_rate", 250.0)),
    )


def _train_anomaly_artifact() -> None:
    """Train and persist the anomaly model from synthetic normal data."""
    payloads = generate_training_payloads(num_samples=260, force_anomaly=False)
    feature_rows: list[np.ndarray] = []

    for payload in payloads:
        sampling_rate = float(payload["sampling_rate"])
        clean_ecg = preprocess_ecg_signal(np.asarray(payload["ecg"], dtype=float), sampling_rate=sampling_rate)
        feature_rows.append(
            build_feature_vector(
                clean_ecg,
                vitals_history=payload["vitals"],
                sampling_rate=sampling_rate,
            ).vector
        )

    train_anomaly_model(np.vstack(feature_rows), save_path=DEFAULT_ANOMALY_PATH)


def _train_lstm_artifact() -> None:
    """Train and persist the LSTM ECG forecasting model."""
    signals = [
        preprocess_ecg_signal(signal, sampling_rate=250.0)
        for signal in generate_training_signals(num_signals=32, anomaly_ratio=0.0)
    ]
    train_lstm_model(signals, epochs=4, batch_size=128, save_path=DEFAULT_LSTM_PATH)


def _validate_saved_models() -> None:
    """Ensure saved model artifacts can be loaded in the current environment."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", InconsistentVersionWarning)
        service = PredictionService(auto_bootstrap=False)
        service.bootstrap_models()


def ensure_models() -> None:
    """Check saved models and train missing artifacts automatically."""
    train_anomaly = not DEFAULT_ANOMALY_PATH.exists()
    train_lstm = not DEFAULT_LSTM_PATH.exists()

    if not train_anomaly and not train_lstm:
        try:
            _validate_saved_models()
            log_info("Models loaded")
            return
        except Exception as exc:
            log_info(f"Existing model artifacts are incompatible or corrupted, retraining: {exc}")
            train_anomaly = True
            train_lstm = True

    log_info("Training started")
    generate_dataset()

    try:
        if train_anomaly:
            log_info(f"Training anomaly model -> {DEFAULT_ANOMALY_PATH}")
            _train_anomaly_artifact()
        if train_lstm:
            log_info(f"Training LSTM model -> {DEFAULT_LSTM_PATH}")
            _train_lstm_artifact()
        _validate_saved_models()
    except Exception as exc:
        log_error(f"Model training failed: {exc}")
        raise

    log_info("Models loaded")


def run_smoke_test() -> None:
    """Run one in-process inference pass and print the result."""
    log_info("Running pipeline smoke test")
    service = PredictionService(auto_bootstrap=False)
    service.bootstrap_models()

    payload = generate_signal()
    result = analyze(service, payload)
    print(json.dumps(result, indent=2), flush=True)


def start_api() -> None:
    """Start the FastAPI service using uvicorn."""
    try:
        log_info(f"API running on http://{API_HOST}:{API_PORT}")
        uvicorn.run("app.main:app", host=API_HOST, port=API_PORT, reload=False)
    except Exception as exc:
        log_error(f"API server crashed: {exc}")
        traceback.print_exc()


def _post_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Send one simulator payload to the local API and parse the response."""
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_api(timeout_seconds: float = 45.0) -> None:
    """Wait until the FastAPI server responds to health checks."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=5) as response:
                if response.status == 200:
                    return
        except urllib.error.URLError:
            time.sleep(1.0)
        except Exception:
            time.sleep(1.0)
    raise TimeoutError(f"API did not become ready within {timeout_seconds:.0f} seconds.")


def start_simulator(stop_event: threading.Event) -> None:
    """Continuously generate NICU payloads and send them to the local API."""
    simulator = InfantPulseSimulator(num_babies=SIMULATOR_BABIES)
    log_info("Simulator started")

    while not stop_event.is_set():
        for payload in simulator.generate_batch():
            if stop_event.is_set():
                break
            try:
                result = _post_payload(payload)
                print(
                    f"[SIM] baby_id={result['baby_id']} status={result['status']} "
                    f"risk={result['risk_score']} anomaly={result['anomaly']['label']} "
                    f"early_warning={result['early_warning']}",
                    flush=True,
                )
            except urllib.error.URLError as exc:
                log_error(f"Simulator request failed for {payload['baby_id']}: {exc}")
            except Exception as exc:
                log_error(f"Simulator crashed for {payload['baby_id']}: {exc}")
        stop_event.wait(SIMULATOR_INTERVAL_SECONDS)


def main() -> None:
    """Train missing models, test the pipeline, and run the live stack."""
    stop_event = threading.Event()

    try:
        ensure_models()
        run_smoke_test()

        api_thread = threading.Thread(target=start_api, name="infant-pulse-api", daemon=True)
        api_thread.start()

        wait_for_api()

        simulator_thread = threading.Thread(
            target=start_simulator,
            args=(stop_event,),
            name="infant-pulse-simulator",
            daemon=True,
        )
        simulator_thread.start()

        while api_thread.is_alive() and simulator_thread.is_alive():
            time.sleep(1.0)
    except KeyboardInterrupt:
        log_info("Shutdown requested by user")
    except Exception as exc:
        log_error(f"run.py failed: {exc}")
        traceback.print_exc()
        raise
    finally:
        stop_event.set()
        time.sleep(1.0)


if __name__ == "__main__":
    main()
