"""End-to-end inference service for Infant Pulse."""

from __future__ import annotations

from pathlib import Path

import numpy as np

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
from services.feature_engineering import FeatureBundle, build_feature_vector
from services.risk_engine import compute_risk_score
from utils.preprocessing import preprocess_ecg_signal


class PredictionService:
    """Coordinates preprocessing, ML inference, warnings, and explanations."""

    def __init__(self, auto_bootstrap: bool = True) -> None:
        """Initialize model paths and optionally load or bootstrap persisted models."""
        self.base_dir = Path(__file__).resolve().parents[1]
        self.anomaly_path = DEFAULT_ANOMALY_PATH
        self.lstm_path = DEFAULT_LSTM_PATH
        self.anomaly_model = None
        self.lstm_model: ECGLSTMPredictor | None = None
        self.lstm_input_window = DEFAULT_INPUT_WINDOW
        if auto_bootstrap:
            self.bootstrap_models()

    def bootstrap_models(self, force_retrain: bool = False) -> None:
        """Train synthetic models when artifacts do not exist and then load them."""
        if force_retrain or not self.anomaly_path.exists():
            self._train_default_anomaly_model()
        self.anomaly_model = load_anomaly_model(self.anomaly_path)

        if force_retrain or not self.lstm_path.exists():
            self._train_default_lstm_model()
        self.lstm_model, self.lstm_input_window = load_lstm_model(self.lstm_path)

    def _train_default_anomaly_model(self) -> None:
        """Train the anomaly detector on synthetic normal payloads."""
        payloads = generate_training_payloads(num_samples=260, force_anomaly=False)
        feature_rows: list[np.ndarray] = []
        for payload in payloads:
            clean_ecg = preprocess_ecg_signal(
                np.asarray(payload["ecg"], dtype=float),
                sampling_rate=float(payload["sampling_rate"]),
            )
            feature_rows.append(
                build_feature_vector(
                    clean_ecg,
                    vitals_history=payload["vitals"],  # type: ignore[arg-type]
                    sampling_rate=float(payload["sampling_rate"]),
                ).vector
            )
        train_anomaly_model(np.vstack(feature_rows), save_path=self.anomaly_path)

    def _train_default_lstm_model(self) -> None:
        """Train the ECG forecasting model on synthetic normal waveforms."""
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

    def _build_explanation(
        self,
        feature_bundle: FeatureBundle,
        anomaly_result: dict[str, float | str],
        early_warning_result: dict[str, object],
        risk_result: dict[str, object],
    ) -> dict[str, object]:
        """Create a structured explanation for clinical traceability."""
        trend_context = {
            "heart_rate_slope": round(feature_bundle.values["heart_rate_slope"], 4),
            "spo2_slope": round(feature_bundle.values["spo2_slope"], 4),
            "ecg_rr_irregularity": round(feature_bundle.values["ecg_rr_irregularity"], 4),
            "dominant_frequency": round(feature_bundle.values["dominant_frequency"], 4),
        }
        feature_snapshot = {
            key: round(feature_bundle.values[key], 4)
            for key in (
                "heart_rate",
                "spo2",
                "temperature",
                "respiration",
                "ecg_std",
                "spectral_energy",
            )
        }
        top_reasons = [str(reason) for reason in risk_result.get("reasons", [])[:3]]
        summary = (
            "Attention required: abnormal trends were detected."
            if risk_result["status"] != "STABLE"
            else "Signal and vital signs are currently within expected bounds."
        )

        return {
            "summary": summary,
            "top_reasons": top_reasons,
            "feature_snapshot": feature_snapshot,
            "trend_context": trend_context,
            "anomaly_context": {
                "label": anomaly_result["label"],
                "anomaly_score": anomaly_result["anomaly_score"],
                "raw_score": anomaly_result["raw_score"],
            },
            "warning_context": {
                "early_warning": early_warning_result["early_warning"],
                "message": early_warning_result["message"],
            },
            "model_sources": {
                "anomaly_model": str(self.anomaly_path),
                "lstm_model": str(self.lstm_path),
            },
        }

    def analyze(
        self,
        baby_id: str,
        vitals_history: list[dict[str, float]],
        ecg: list[float],
        sampling_rate: float = 250.0,
    ) -> dict[str, object]:
        """Run the full Infant Pulse inference pipeline for a single infant."""
        if self.anomaly_model is None or self.lstm_model is None:
            self.bootstrap_models()

        raw_ecg = np.asarray(ecg, dtype=float)
        clean_ecg = preprocess_ecg_signal(raw_ecg, sampling_rate=sampling_rate)
        feature_bundle = build_feature_vector(clean_ecg, vitals_history, sampling_rate=sampling_rate)
        anomaly_result = detect_anomaly(feature_bundle.vector, model=self.anomaly_model)
        early_warning_result = evaluate_early_warning(vitals_history, clean_ecg, sampling_rate=sampling_rate)
        latest_vitals = vitals_history[-1] if vitals_history else {}
        risk_result = compute_risk_score(anomaly_result, latest_vitals, early_warning_result)

        predicted_ecg = predict_next_samples(
            self.lstm_model,
            clean_ecg[-self.lstm_input_window :],
            input_window=self.lstm_input_window,
        )
        explanation = self._build_explanation(
            feature_bundle,
            anomaly_result,
            early_warning_result,
            risk_result,
        )

        return {
            "baby_id": baby_id,
            "anomaly": {
                "anomaly_score": anomaly_result["anomaly_score"],
                "label": anomaly_result["label"],
            },
            "risk_score": risk_result["risk_score"],
            "status": risk_result["status"],
            "predicted_ecg": [round(float(value), 6) for value in predicted_ecg],
            "early_warning": bool(early_warning_result["early_warning"]),
            "message": str(early_warning_result["message"]),
            "explanation": explanation,
        }


_service_instance: PredictionService | None = None


def get_prediction_service() -> PredictionService:
    """Return a process-wide prediction service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = PredictionService()
    return _service_instance
