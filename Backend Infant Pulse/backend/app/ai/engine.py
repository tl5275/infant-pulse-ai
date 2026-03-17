"""Backend-owned ML inference and synthetic ECG helpers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
from joblib import dump, load
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from app.services.blood_pressure import build_bp_series


LOCAL_MODEL_DIR = Path(__file__).resolve().parent / "saved_models"
MODEL_DIR = LOCAL_MODEL_DIR

DEFAULT_ANOMALY_PATH = MODEL_DIR / "anomaly.pkl"
DEFAULT_LSTM_PATH = MODEL_DIR / "lstm.pth"
DEFAULT_INPUT_WINDOW = 100
DEFAULT_HORIZON = 20


@dataclass(slots=True)
class InferenceInput:
    """Input payload expected by the backend-owned ML service."""

    baby_id: str
    vitals_history: list[dict[str, float]]
    ecg: list[float]
    sampling_rate: float = 250.0


@dataclass(slots=True)
class SyntheticBabyState:
    """Mutable simulator state for one infant stream."""

    baby_id: str
    heart_rate: float
    spo2: float
    temperature: float
    respiration: float
    vitals_history: deque[dict[str, float]] = field(default_factory=lambda: deque(maxlen=12))


class ECGLSTMPredictor(nn.Module):
    """Sequence-to-vector LSTM that predicts the next ECG segment."""

    def __init__(
        self,
        input_size: int = 1,
        hidden_size: int = 48,
        num_layers: int = 1,
        horizon: int = DEFAULT_HORIZON,
    ) -> None:
        super().__init__()
        self.horizon = horizon
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.1 if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, horizon),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        outputs, _ = self.lstm(inputs)
        return self.head(outputs[:, -1, :])


def _clamp(value: float, lower: float, upper: float) -> float:
    return float(max(lower, min(value, upper)))


def _resolve_device(device: str | None = None) -> torch.device:
    if device:
        return torch.device(device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def normalize_signal(signal: np.ndarray) -> np.ndarray:
    values = np.asarray(signal, dtype=float)
    if values.size == 0:
        return values

    mean = float(np.mean(values))
    std = float(np.std(values))
    if std < 1e-8:
        return values - mean
    return (values - mean) / std


def bandpass_filter(
    signal: np.ndarray,
    sampling_rate: float,
    low_cut: float = 0.5,
    high_cut: float = 40.0,
) -> np.ndarray:
    values = np.asarray(signal, dtype=float)
    if values.size == 0:
        return values

    frequencies = np.fft.rfftfreq(values.size, d=1.0 / sampling_rate)
    spectrum = np.fft.rfft(values)
    band_mask = (frequencies >= low_cut) & (frequencies <= high_cut)
    filtered = np.fft.irfft(spectrum * band_mask, n=values.size)
    return filtered.astype(float)


def preprocess_ecg_signal(signal: np.ndarray, sampling_rate: float = 250.0) -> np.ndarray:
    return normalize_signal(bandpass_filter(signal, sampling_rate=sampling_rate))


def extract_fft_features(ecg_signal: np.ndarray, sampling_rate: float = 250.0) -> dict[str, float]:
    signal = np.asarray(ecg_signal, dtype=float)
    if signal.size == 0:
        return {
            "dominant_frequency": 0.0,
            "spectral_energy": 0.0,
            "peak_frequency_1": 0.0,
            "peak_frequency_2": 0.0,
            "peak_frequency_3": 0.0,
        }

    spectrum = np.fft.rfft(signal)
    frequencies = np.fft.rfftfreq(signal.size, d=1.0 / sampling_rate)
    power = np.abs(spectrum) ** 2

    if power.size <= 1:
        return {
            "dominant_frequency": 0.0,
            "spectral_energy": float(np.sum(power)),
            "peak_frequency_1": 0.0,
            "peak_frequency_2": 0.0,
            "peak_frequency_3": 0.0,
        }

    non_dc_power = power[1:]
    non_dc_frequencies = frequencies[1:]
    dominant_index = int(np.argmax(non_dc_power))
    peak_indices = np.argsort(non_dc_power)[-min(3, non_dc_power.size) :][::-1]
    peak_frequencies = list(non_dc_frequencies[peak_indices])
    while len(peak_frequencies) < 3:
        peak_frequencies.append(0.0)

    return {
        "dominant_frequency": float(non_dc_frequencies[dominant_index]),
        "spectral_energy": float(np.sum(power)),
        "peak_frequency_1": float(peak_frequencies[0]),
        "peak_frequency_2": float(peak_frequencies[1]),
        "peak_frequency_3": float(peak_frequencies[2]),
    }


def _compute_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    x_axis = np.arange(len(values), dtype=float)
    slope, _ = np.polyfit(x_axis, np.asarray(values, dtype=float), 1)
    return float(slope)


def _detect_peak_positions(ecg_signal: np.ndarray, sampling_rate: float) -> np.ndarray:
    signal = np.asarray(ecg_signal, dtype=float)
    if signal.size < 3:
        return np.asarray([], dtype=int)

    threshold = max(float(np.mean(signal) + 0.8 * np.std(signal)), 0.4)
    local_maxima = np.where(
        (signal[1:-1] > signal[:-2])
        & (signal[1:-1] >= signal[2:])
        & (signal[1:-1] > threshold)
    )[0] + 1

    refractory = max(int(0.25 * sampling_rate), 1)
    selected: list[int] = []
    for peak_index in local_maxima.tolist():
        if not selected or peak_index - selected[-1] >= refractory:
            selected.append(peak_index)
            continue
        if signal[peak_index] > signal[selected[-1]]:
            selected[-1] = peak_index

    return np.asarray(selected, dtype=int)


def _peak_irregularity(ecg_signal: np.ndarray, sampling_rate: float) -> float:
    peaks = _detect_peak_positions(ecg_signal, sampling_rate)
    if peaks.size < 3:
        return 0.0

    intervals = np.diff(peaks) / sampling_rate
    interval_mean = float(np.mean(intervals))
    if interval_mean <= 1e-8:
        return 0.0
    return float(np.std(intervals) / interval_mean)


def _coerce_vital_history(vitals_history: list[dict[str, float]] | None) -> list[dict[str, float]]:
    if not vitals_history:
        return []
    return [
        {
            "heart_rate": float(item.get("heart_rate", 0.0)),
            "spo2": float(item.get("spo2", 0.0)),
            "temperature": float(item.get("temperature", 0.0)),
            "respiration": float(item.get("respiration", 0.0)),
        }
        for item in vitals_history
    ]


def build_feature_vector(
    ecg_signal: np.ndarray,
    vitals_history: list[dict[str, float]] | None,
    sampling_rate: float = 250.0,
) -> dict[str, Any]:
    signal = np.asarray(ecg_signal, dtype=float)
    vitals = _coerce_vital_history(vitals_history)
    latest_vitals = vitals[-1] if vitals else {
        "heart_rate": 0.0,
        "spo2": 0.0,
        "temperature": 0.0,
        "respiration": 0.0,
    }

    heart_rates = [item["heart_rate"] for item in vitals]
    spo2_values = [item["spo2"] for item in vitals]
    temperatures = [item["temperature"] for item in vitals]
    respirations = [item["respiration"] for item in vitals]

    fft_features = extract_fft_features(signal, sampling_rate=sampling_rate)
    ordered_values = {
        "ecg_mean": float(np.mean(signal)) if signal.size else 0.0,
        "ecg_std": float(np.std(signal)) if signal.size else 0.0,
        "ecg_min": float(np.min(signal)) if signal.size else 0.0,
        "ecg_max": float(np.max(signal)) if signal.size else 0.0,
        "ecg_median": float(np.median(signal)) if signal.size else 0.0,
        "ecg_peak_to_peak": float(np.ptp(signal)) if signal.size else 0.0,
        "ecg_trend": _compute_slope(signal.tolist()) if signal.size > 1 else 0.0,
        "ecg_rr_irregularity": _peak_irregularity(signal, sampling_rate),
        "heart_rate": float(latest_vitals["heart_rate"]),
        "spo2": float(latest_vitals["spo2"]),
        "temperature": float(latest_vitals["temperature"]),
        "respiration": float(latest_vitals["respiration"]),
        "heart_rate_slope": _compute_slope(heart_rates),
        "spo2_slope": _compute_slope(spo2_values),
        "temperature_slope": _compute_slope(temperatures),
        "respiration_slope": _compute_slope(respirations),
        "dominant_frequency": fft_features["dominant_frequency"],
        "spectral_energy": fft_features["spectral_energy"],
        "peak_frequency_1": fft_features["peak_frequency_1"],
        "peak_frequency_2": fft_features["peak_frequency_2"],
        "peak_frequency_3": fft_features["peak_frequency_3"],
    }

    return {
        "names": list(ordered_values.keys()),
        "values": ordered_values,
        "vector": np.asarray(list(ordered_values.values()), dtype=float),
    }


def assess_vital_thresholds(latest_vitals: dict[str, float]) -> dict[str, object]:
    heart_rate = float(latest_vitals.get("heart_rate", 0.0))
    spo2 = float(latest_vitals.get("spo2", 0.0))
    temperature = float(latest_vitals.get("temperature", 0.0))
    respiration = float(latest_vitals.get("respiration", 0.0))

    score = 0.0
    reasons: list[str] = []

    if heart_rate < 100 or heart_rate > 180:
        score += 0.35
        reasons.append(f"Heart rate {heart_rate:.1f} bpm is outside the NICU target range.")
    elif heart_rate < 110 or heart_rate > 170:
        score += 0.15

    if spo2 < 90:
        score += 0.4
        reasons.append(f"SpO2 {spo2:.1f}% is critically low.")
    elif spo2 < 94:
        score += 0.2
        reasons.append(f"SpO2 {spo2:.1f}% is trending below the preferred range.")

    if temperature < 36.2 or temperature > 37.8:
        score += 0.15
        reasons.append(f"Temperature {temperature:.1f} C is outside the expected range.")

    if respiration < 25 or respiration > 70:
        score += 0.15
        reasons.append(f"Respiration {respiration:.1f} rpm is abnormal for the infant.")

    return {"score": float(np.clip(score, 0.0, 1.0)), "reasons": reasons}


def evaluate_early_warning(
    vitals_history: list[dict[str, float]] | None,
    ecg_signal: np.ndarray,
    sampling_rate: float = 250.0,
) -> dict[str, object]:
    vitals = vitals_history or []
    if not vitals:
        return {
            "early_warning": False,
            "message": "No vital history available for early warning analysis.",
            "reasons": [],
        }

    latest = vitals[-1]
    spo2_values = [float(item.get("spo2", 0.0)) for item in vitals]
    heart_rates = [float(item.get("heart_rate", 0.0)) for item in vitals]
    irregularity = _peak_irregularity(ecg_signal, sampling_rate)

    reasons: list[str] = []
    if latest.get("spo2", 100.0) < 90.0 or _compute_slope(spo2_values[-5:]) < -0.45:
        reasons.append("SpO2 is dropping and may indicate desaturation.")
    if latest.get("heart_rate", 0.0) > 180.0 or _compute_slope(heart_rates[-5:]) > 1.75:
        reasons.append("Heart rate is rising faster than the expected neonatal range.")
    if irregularity > 0.18:
        reasons.append("ECG peak timing is irregular compared with recent rhythm.")

    return {
        "early_warning": bool(reasons),
        "message": " | ".join(reasons) if reasons else "No early warning trends detected.",
        "reasons": reasons,
    }


def _categorize_status(risk_score: float) -> str:
    if risk_score >= 0.7:
        return "CRITICAL"
    if risk_score >= 0.4:
        return "WARNING"
    return "STABLE"


def compute_risk_score(
    anomaly_result: dict[str, float | str],
    latest_vitals: dict[str, float],
    early_warning_result: dict[str, object],
) -> dict[str, object]:
    anomaly_score = float(anomaly_result.get("anomaly_score", 0.0))
    vital_result = assess_vital_thresholds(latest_vitals)
    warning_active = bool(early_warning_result.get("early_warning", False))
    warning_bonus = 0.2 if warning_active else 0.0

    risk_score = float(
        np.clip(
            0.45 * anomaly_score + 0.35 * float(vital_result["score"]) + warning_bonus,
            0.0,
            1.0,
        )
    )

    reasons = list(vital_result["reasons"])
    reasons.extend(str(reason) for reason in early_warning_result.get("reasons", []))
    if anomaly_result.get("label") == "anomaly":
        reasons.insert(0, "Isolation Forest flagged the current pattern as an outlier.")
    if not reasons:
        reasons.append("All monitored features remain within expected operating bounds.")

    return {
        "risk_score": round(risk_score, 4),
        "status": _categorize_status(risk_score),
        "reasons": reasons,
        "components": {
            "anomaly_score": round(anomaly_score, 4),
            "vital_score": round(float(vital_result["score"]), 4),
            "warning_score": round(warning_bonus, 4),
        },
    }


def train_anomaly_model(
    feature_matrix: np.ndarray,
    contamination: float = 0.08,
    save_path: Path = DEFAULT_ANOMALY_PATH,
    random_state: int = 42,
) -> Pipeline:
    features = np.asarray(feature_matrix, dtype=float)
    if features.ndim != 2 or features.shape[0] < 10:
        raise ValueError("feature_matrix must contain at least 10 training rows.")

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "isolation_forest",
                IsolationForest(
                    contamination=contamination,
                    n_estimators=200,
                    random_state=random_state,
                ),
            ),
        ]
    )
    model.fit(features)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    dump(model, save_path)
    return model


def load_anomaly_model(model_path: Path = DEFAULT_ANOMALY_PATH) -> Pipeline:
    if not model_path.exists():
        raise FileNotFoundError(f"Anomaly model not found at {model_path}.")
    return load(model_path)


def detect_anomaly(
    features: np.ndarray,
    model: Pipeline | None = None,
    model_path: Path = DEFAULT_ANOMALY_PATH,
) -> dict[str, float | str]:
    feature_vector = np.asarray(features, dtype=float).reshape(1, -1)
    estimator = model if model is not None else load_anomaly_model(model_path=model_path)

    raw_score = float(estimator.decision_function(feature_vector)[0])
    prediction = int(estimator.predict(feature_vector)[0])
    anomaly_score = float(1.0 / (1.0 + np.exp(8.0 * raw_score)))
    return {
        "anomaly_score": round(anomaly_score, 4),
        "label": "anomaly" if prediction == -1 else "normal",
        "raw_score": round(raw_score, 4),
    }


def create_training_sequences(
    signal: np.ndarray,
    input_window: int = DEFAULT_INPUT_WINDOW,
    horizon: int = DEFAULT_HORIZON,
    stride: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(signal, dtype=float)
    sequences: list[np.ndarray] = []
    targets: list[np.ndarray] = []

    max_start = values.size - input_window - horizon + 1
    for start_index in range(0, max(0, max_start), stride):
        end_index = start_index + input_window
        horizon_end = end_index + horizon
        sequences.append(values[start_index:end_index].reshape(-1, 1))
        targets.append(values[end_index:horizon_end])

    if not sequences:
        return (
            np.empty((0, input_window, 1), dtype=np.float32),
            np.empty((0, horizon), dtype=np.float32),
        )

    return (
        np.asarray(sequences, dtype=np.float32),
        np.asarray(targets, dtype=np.float32),
    )


def save_lstm_model(
    model: ECGLSTMPredictor,
    save_path: Path = DEFAULT_LSTM_PATH,
    input_window: int = DEFAULT_INPUT_WINDOW,
) -> None:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "model_state": model.state_dict(),
        "config": {
            "input_size": 1,
            "hidden_size": model.lstm.hidden_size,
            "num_layers": model.lstm.num_layers,
            "horizon": model.horizon,
            "input_window": input_window,
        },
    }
    torch.save(checkpoint, save_path)


def train_lstm_model(
    training_signals: Sequence[np.ndarray],
    epochs: int = 4,
    batch_size: int = 128,
    learning_rate: float = 1e-3,
    input_window: int = DEFAULT_INPUT_WINDOW,
    horizon: int = DEFAULT_HORIZON,
    save_path: Path = DEFAULT_LSTM_PATH,
    device: str | None = None,
) -> ECGLSTMPredictor:
    feature_batches: list[np.ndarray] = []
    target_batches: list[np.ndarray] = []

    for signal in training_signals:
        features, targets = create_training_sequences(
            signal,
            input_window=input_window,
            horizon=horizon,
        )
        if features.size == 0:
            continue
        feature_batches.append(features)
        target_batches.append(targets)

    if not feature_batches:
        raise ValueError("No LSTM training sequences could be generated.")

    x_train = torch.tensor(np.concatenate(feature_batches, axis=0), dtype=torch.float32)
    y_train = torch.tensor(np.concatenate(target_batches, axis=0), dtype=torch.float32)
    train_loader = DataLoader(TensorDataset(x_train, y_train), batch_size=batch_size, shuffle=True)

    runtime_device = _resolve_device(device)
    model = ECGLSTMPredictor(horizon=horizon).to(runtime_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_function = nn.MSELoss()

    model.train()
    for _ in range(epochs):
        for batch_features, batch_targets in train_loader:
            batch_features = batch_features.to(runtime_device)
            batch_targets = batch_targets.to(runtime_device)

            optimizer.zero_grad()
            predictions = model(batch_features)
            loss = loss_function(predictions, batch_targets)
            loss.backward()
            optimizer.step()

    model.eval()
    save_lstm_model(model, save_path=save_path, input_window=input_window)
    return model.cpu()


def load_lstm_model(
    model_path: Path = DEFAULT_LSTM_PATH,
    device: str | None = None,
) -> tuple[ECGLSTMPredictor, int]:
    if not model_path.exists():
        raise FileNotFoundError(f"LSTM model not found at {model_path}.")

    runtime_device = _resolve_device(device)
    checkpoint = torch.load(model_path, map_location=runtime_device, weights_only=False)
    config = checkpoint["config"]
    model = ECGLSTMPredictor(
        input_size=config["input_size"],
        hidden_size=config["hidden_size"],
        num_layers=config["num_layers"],
        horizon=config["horizon"],
    )
    model.load_state_dict(checkpoint["model_state"])
    model.to(runtime_device)
    model.eval()
    return model, int(config["input_window"])


def predict_next_samples(
    model: ECGLSTMPredictor,
    history: np.ndarray,
    input_window: int = DEFAULT_INPUT_WINDOW,
    device: str | None = None,
) -> list[float]:
    values = np.asarray(history, dtype=np.float32).flatten()
    if values.size < input_window:
        padding = np.full(input_window - values.size, values[0] if values.size else 0.0, dtype=np.float32)
        values = np.concatenate([padding, values], axis=0)
    values = values[-input_window:]

    runtime_device = _resolve_device(device)
    model = model.to(runtime_device)
    with torch.no_grad():
        tensor = torch.tensor(values.reshape(1, input_window, 1), dtype=torch.float32, device=runtime_device)
        predictions = model(tensor).cpu().numpy().reshape(-1)
    return predictions.astype(float).tolist()


def simulate_ecg_waveform(
    duration_seconds: float = 4.0,
    sampling_rate: float = 250.0,
    heart_rate: float = 140.0,
    noise_scale: float = 0.02,
    anomaly: bool = False,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    generator = rng or np.random.default_rng()
    sample_count = int(duration_seconds * sampling_rate)
    timeline = np.arange(sample_count, dtype=float) / sampling_rate
    beat_period = 60.0 / max(heart_rate, 1.0)
    phase = np.mod(timeline, beat_period) / beat_period

    p_wave = 0.08 * np.exp(-((phase - 0.16) ** 2) / (2 * 0.018**2))
    q_wave = -0.12 * np.exp(-((phase - 0.30) ** 2) / (2 * 0.006**2))
    r_wave = 1.1 * np.exp(-((phase - 0.32) ** 2) / (2 * 0.004**2))
    s_wave = -0.22 * np.exp(-((phase - 0.35) ** 2) / (2 * 0.008**2))
    t_wave = 0.28 * np.exp(-((phase - 0.55) ** 2) / (2 * 0.05**2))

    baseline_wander = 0.03 * np.sin(2 * np.pi * 0.33 * timeline)
    rhythm = 0.02 * np.sin(2 * np.pi * (heart_rate / 60.0) * timeline)
    ecg = p_wave + q_wave + r_wave + s_wave + t_wave + baseline_wander + rhythm

    if anomaly:
        for burst_center in generator.choice(sample_count, size=3, replace=False):
            width = int(generator.integers(5, 18))
            amplitude = float(generator.uniform(-0.7, 0.9))
            end_index = min(sample_count, burst_center + width)
            ecg[burst_center:end_index] += amplitude * np.hanning(max(end_index - burst_center, 1))
        ecg += 0.05 * np.sin(2 * np.pi * 6.0 * timeline)

    ecg += generator.normal(0.0, noise_scale, sample_count)
    return ecg.astype(float)


def _next_vitals(
    state: SyntheticBabyState,
    rng: np.random.Generator,
    force_anomaly: bool | None = None,
) -> dict[str, float]:
    anomaly = bool(force_anomaly) if force_anomaly is not None else bool(rng.random() < 0.12)

    heart_rate_shift = float(rng.normal(0.0, 1.4))
    spo2_shift = float(rng.normal(0.0, 0.18))
    temperature_shift = float(rng.normal(0.0, 0.04))
    respiration_shift = float(rng.normal(0.0, 0.9))

    if anomaly:
        heart_rate_shift += float(rng.uniform(1.5, 3.5))
        spo2_shift -= float(rng.uniform(0.4, 1.2))
        respiration_shift += float(rng.uniform(0.8, 2.0))

    state.heart_rate = _clamp(state.heart_rate + heart_rate_shift, 95.0, 195.0)
    state.spo2 = _clamp(state.spo2 + spo2_shift, 82.0, 100.0)
    state.temperature = _clamp(state.temperature + temperature_shift, 35.8, 38.6)
    state.respiration = _clamp(state.respiration + respiration_shift, 20.0, 78.0)

    return {
        "heart_rate": round(state.heart_rate, 2),
        "spo2": round(state.spo2, 2),
        "temperature": round(state.temperature, 2),
        "respiration": round(state.respiration, 2),
    }


def generate_training_payloads(
    num_samples: int = 240,
    num_babies: int = 8,
    seed: int = 42,
    force_anomaly: bool | None = False,
) -> list[dict[str, object]]:
    rng = np.random.default_rng(seed)
    babies = {
        f"baby_{index + 1:02d}": SyntheticBabyState(
            baby_id=f"baby_{index + 1:02d}",
            heart_rate=float(rng.normal(142.0, 6.0)),
            spo2=float(rng.normal(97.0, 1.0)),
            temperature=float(rng.normal(36.8, 0.15)),
            respiration=float(rng.normal(42.0, 4.0)),
            vitals_history=deque(maxlen=12),
        )
        for index in range(num_babies)
    }

    for state in babies.values():
        for _ in range(12):
            state.vitals_history.append(_next_vitals(state, rng, force_anomaly=False))

    payloads: list[dict[str, object]] = []
    baby_ids = list(babies.keys())
    for index in range(num_samples):
        baby_id = baby_ids[index % len(baby_ids)]
        state = babies[baby_id]
        latest_vitals = _next_vitals(state, rng, force_anomaly=force_anomaly)
        state.vitals_history.append(latest_vitals)

        anomaly = bool(force_anomaly) if force_anomaly is not None else latest_vitals["spo2"] < 92 or latest_vitals["heart_rate"] > 175
        ecg = simulate_ecg_waveform(
            duration_seconds=4.0,
            sampling_rate=250.0,
            heart_rate=latest_vitals["heart_rate"],
            anomaly=anomaly,
            rng=rng,
        )
        payloads.append(
            {
                "baby_id": baby_id,
                "vitals": list(state.vitals_history),
                "ecg": np.round(ecg, 6).tolist(),
                "sampling_rate": 250.0,
            }
        )

    return payloads


def generate_training_signals(
    num_signals: int = 64,
    duration_seconds: float = 6.0,
    sampling_rate: float = 250.0,
    anomaly_ratio: float = 0.0,
    seed: int = 42,
) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    signals: list[np.ndarray] = []
    for _ in range(num_signals):
        heart_rate = float(rng.normal(142.0, 8.0))
        anomaly = bool(rng.random() < anomaly_ratio)
        signals.append(
            simulate_ecg_waveform(
                duration_seconds=duration_seconds,
                sampling_rate=sampling_rate,
                heart_rate=heart_rate,
                anomaly=anomaly,
                rng=rng,
            )
        )
    return signals


class MLInferenceService:
    """Coordinates ECG preprocessing, anomaly detection, and risk scoring."""

    def __init__(self, prediction_points: int = 20) -> None:
        self.anomaly_path = DEFAULT_ANOMALY_PATH
        self.lstm_path = DEFAULT_LSTM_PATH
        self.prediction_points = prediction_points
        self.anomaly_model: Pipeline | None = None
        self.lstm_model: ECGLSTMPredictor | None = None
        self.lstm_input_window = DEFAULT_INPUT_WINDOW

    @property
    def is_ready(self) -> bool:
        return self.anomaly_model is not None and self.lstm_model is not None

    def load_models(self, force_retrain: bool = False) -> None:
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
                )["vector"]
            )
        train_anomaly_model(np.vstack(feature_rows), save_path=self.anomaly_path)

    def _train_default_lstm_model(self) -> None:
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

    def run_inference(self, input_data: InferenceInput) -> dict[str, object]:
        if not self.is_ready:
            self.load_models()

        if self.anomaly_model is None or self.lstm_model is None:
            raise RuntimeError("ML models are not ready.")

        raw_ecg = np.asarray(input_data.ecg, dtype=float).flatten()
        if raw_ecg.size == 0:
            raise ValueError("ECG signal cannot be empty.")

        clean_ecg = preprocess_ecg_signal(raw_ecg, sampling_rate=input_data.sampling_rate)
        feature_bundle = build_feature_vector(
            clean_ecg,
            input_data.vitals_history,
            sampling_rate=input_data.sampling_rate,
        )
        anomaly_result = detect_anomaly(feature_bundle["vector"], model=self.anomaly_model)
        early_warning_result = evaluate_early_warning(
            input_data.vitals_history,
            clean_ecg,
            sampling_rate=input_data.sampling_rate,
        )
        latest_vitals = input_data.vitals_history[-1] if input_data.vitals_history else {}
        risk_result = compute_risk_score(anomaly_result, latest_vitals, early_warning_result)
        bp_series = build_bp_series(input_data.vitals_history)

        predicted_ecg = predict_next_samples(
            self.lstm_model,
            clean_ecg[-self.lstm_input_window :],
            input_window=self.lstm_input_window,
        )[: self.prediction_points]

        explanation = {
            "summary": (
                "Attention required: abnormal trends were detected."
                if risk_result["status"] != "STABLE"
                else "Signal and vital signs are currently within expected bounds."
            ),
            "top_reasons": [str(reason) for reason in risk_result["reasons"][:3]],
            "feature_snapshot": {
                key: round(float(feature_bundle["values"][key]), 4)
                for key in (
                    "heart_rate",
                    "spo2",
                    "temperature",
                    "respiration",
                    "ecg_std",
                    "spectral_energy",
                )
            },
            "trend_context": {
                "heart_rate_slope": round(float(feature_bundle["values"]["heart_rate_slope"]), 4),
                "spo2_slope": round(float(feature_bundle["values"]["spo2_slope"]), 4),
                "ecg_rr_irregularity": round(float(feature_bundle["values"]["ecg_rr_irregularity"]), 4),
                "dominant_frequency": round(float(feature_bundle["values"]["dominant_frequency"]), 4),
            },
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

        return {
            "baby_id": input_data.baby_id,
            "ecg_signal": [round(float(value), 6) for value in clean_ecg.tolist()],
            "predicted_ecg": [round(float(value), 6) for value in predicted_ecg],
            "bp": bp_series,
            "risk_score": round(float(risk_result["risk_score"]), 4),
            "anomaly": str(anomaly_result["label"]),
            "anomaly_score": round(float(anomaly_result["anomaly_score"]), 4),
            "early_warning": bool(early_warning_result["early_warning"]),
            "status": str(risk_result["status"]),
            "message": str(early_warning_result["message"]),
            "fft_features": {
                "dominant_frequency": round(float(feature_bundle["values"]["dominant_frequency"]), 4),
                "spectral_energy": round(float(feature_bundle["values"]["spectral_energy"]), 4),
                "peak_frequency_1": round(float(feature_bundle["values"]["peak_frequency_1"]), 4),
                "peak_frequency_2": round(float(feature_bundle["values"]["peak_frequency_2"]), 4),
                "peak_frequency_3": round(float(feature_bundle["values"]["peak_frequency_3"]), 4),
            },
            "explanation": explanation,
            "components": risk_result["components"],
        }


_ml_service: MLInferenceService | None = None


def get_ml_service() -> MLInferenceService:
    global _ml_service
    if _ml_service is None:
        _ml_service = MLInferenceService()
    return _ml_service
