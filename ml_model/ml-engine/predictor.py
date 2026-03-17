"""Realtime predictor used by the dashboard backend."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.fft import fft

from data.simulator import generate_training_payloads, generate_training_signals
from models.anomaly_model import (
    DEFAULT_ANOMALY_PATH,
    detect_anomaly,
    load_anomaly_model,
    train_anomaly_model,
)
from models.lstm_model import (
    DEFAULT_INPUT_WINDOW,
    DEFAULT_LSTM_PATH,
    ECGLSTMPredictor,
    load_lstm_model,
    predict_next_samples,
    train_lstm_model,
)
from services.early_warning import evaluate_early_warning
from services.feature_engineering import build_feature_vector
from services.risk_engine import compute_risk_score
from utils.preprocessing import preprocess_ecg_signal


class RealtimePredictor:
    """Wrap the saved anomaly detector and LSTM for live inference."""

    def __init__(self, prediction_points: int = 10) -> None:
        self.base_dir = Path(__file__).resolve().parent
        self.anomaly_path = DEFAULT_ANOMALY_PATH
        self.lstm_path = DEFAULT_LSTM_PATH
        self.prediction_points = prediction_points
        self.anomaly_model = None
        self.lstm_model: ECGLSTMPredictor | None = None
        self.lstm_input_window = DEFAULT_INPUT_WINDOW
        self.bootstrap_models()

    def bootstrap_models(self, force_retrain: bool = False) -> None:
        """Load saved models and retrain them if the artifacts are missing or invalid."""
        try:
            if force_retrain or not self.anomaly_path.exists():
                self._train_default_anomaly_model()
            self.anomaly_model = load_anomaly_model(self.anomaly_path)

            if force_retrain or not self.lstm_path.exists():
                self._train_default_lstm_model()
            self.lstm_model, self.lstm_input_window = load_lstm_model(self.lstm_path)
        except Exception:
            if force_retrain:
                raise
            self._train_default_anomaly_model()
            self._train_default_lstm_model()
            self.anomaly_model = load_anomaly_model(self.anomaly_path)
            self.lstm_model, self.lstm_input_window = load_lstm_model(self.lstm_path)

    def _train_default_anomaly_model(self) -> None:
        """Train the anomaly model on synthetic normal traces."""
        payloads = generate_training_payloads(num_samples=260, force_anomaly=False)
        feature_rows: list[np.ndarray] = []

        for payload in payloads:
            sampling_rate = float(payload["sampling_rate"])
            clean_ecg = preprocess_ecg_signal(
                np.asarray(payload["ecg"], dtype=float),
                sampling_rate=sampling_rate,
            )
            feature_rows.append(
                build_feature_vector(
                    clean_ecg,
                    vitals_history=payload["vitals"],  # type: ignore[arg-type]
                    sampling_rate=sampling_rate,
                ).vector
            )

        train_anomaly_model(np.vstack(feature_rows), save_path=self.anomaly_path)

    def _train_default_lstm_model(self) -> None:
        """Train the ECG forecaster on synthetic normal waveforms."""
        signals = [
            preprocess_ecg_signal(signal, sampling_rate=250.0)
            for signal in generate_training_signals(num_signals=32, anomaly_ratio=0.0)
        ]
        train_lstm_model(
            signals,
            epochs=4,
            batch_size=128,
            save_path=self.lstm_path,
        )

    @staticmethod
    def _extract_fft_features(ecg_signal: np.ndarray, sampling_rate: float) -> dict[str, float]:
        """Compute lightweight FFT features for the live stream payload."""
        signal = np.asarray(ecg_signal, dtype=float).flatten()
        if signal.size == 0:
            return {
                "dominant_frequency": 0.0,
                "spectral_energy": 0.0,
            }

        spectrum = fft(signal)
        frequencies = np.fft.fftfreq(signal.size, d=1.0 / sampling_rate)
        positive_mask = frequencies >= 0
        positive_frequencies = frequencies[positive_mask]
        positive_power = np.abs(spectrum[positive_mask]) ** 2

        if positive_power.size <= 1:
            return {
                "dominant_frequency": 0.0,
                "spectral_energy": float(np.sum(positive_power)),
            }

        dominant_index = int(np.argmax(positive_power[1:]) + 1)
        return {
            "dominant_frequency": float(positive_frequencies[dominant_index]),
            "spectral_energy": float(np.sum(positive_power)),
        }

    def predict(
        self,
        baby_id: str,
        vitals_history: list[dict[str, float]],
        ecg_signal: list[float],
        sampling_rate: float = 250.0,
    ) -> dict[str, object]:
        """Run the live prediction pipeline and return dashboard-ready output."""
        if self.anomaly_model is None or self.lstm_model is None:
            self.bootstrap_models()

        raw_signal = np.asarray(ecg_signal, dtype=float).flatten()
        if raw_signal.size == 0:
            raise ValueError("ECG signal cannot be empty.")

        clean_signal = preprocess_ecg_signal(raw_signal, sampling_rate=sampling_rate)
        fft_features = self._extract_fft_features(clean_signal, sampling_rate=sampling_rate)
        feature_bundle = build_feature_vector(clean_signal, vitals_history, sampling_rate=sampling_rate)
        anomaly_result = detect_anomaly(feature_bundle.vector, model=self.anomaly_model)
        early_warning_result = evaluate_early_warning(vitals_history, clean_signal, sampling_rate=sampling_rate)
        latest_vitals = vitals_history[-1] if vitals_history else {}
        risk_result = compute_risk_score(anomaly_result, latest_vitals, early_warning_result)

        last_50_points = clean_signal[-50:]
        predicted_ecg = predict_next_samples(
            self.lstm_model,
            last_50_points,
            input_window=self.lstm_input_window,
        )[: self.prediction_points]

        return {
            "baby_id": baby_id,
            "ecg_signal": [round(float(value), 6) for value in clean_signal.tolist()],
            "predicted_ecg": [round(float(value), 6) for value in predicted_ecg],
            "risk_score": round(float(risk_result["risk_score"]), 4),
            "anomaly": str(anomaly_result["label"]),
            "early_warning": bool(early_warning_result["early_warning"]),
            "status": str(risk_result["status"]),
            "message": str(early_warning_result["message"]),
            "fft_features": {
                "dominant_frequency": round(fft_features["dominant_frequency"], 4),
                "spectral_energy": round(fft_features["spectral_energy"], 4),
            },
        }


_predictor_instance: RealtimePredictor | None = None


def get_predictor() -> RealtimePredictor:
    """Return a singleton predictor for the API process."""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = RealtimePredictor()
    return _predictor_instance
