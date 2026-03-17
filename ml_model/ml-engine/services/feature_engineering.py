"""Feature engineering pipeline for Infant Pulse inference."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from models.fft_features import extract_fft_features


@dataclass(slots=True)
class FeatureBundle:
    """Container for model-ready features and their named values."""

    names: list[str]
    values: dict[str, float]
    vector: np.ndarray


def _coerce_vital_history(vitals_history: list[dict[str, float]] | None) -> list[dict[str, float]]:
    """Normalize incoming vital history records into plain dictionaries."""
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


def _compute_slope(values: list[float]) -> float:
    """Estimate a linear trend slope for a sequence of scalar values."""
    if len(values) < 2:
        return 0.0
    x_axis = np.arange(len(values), dtype=float)
    slope, _ = np.polyfit(x_axis, np.asarray(values, dtype=float), 1)
    return float(slope)


def _detect_r_peaks(ecg_signal: np.ndarray, sampling_rate: float) -> np.ndarray:
    """Detect approximate R-peaks using local maxima and a refractory period."""
    signal = np.asarray(ecg_signal, dtype=float)
    if signal.size < 3:
        return np.asarray([], dtype=int)

    dynamic_threshold = float(np.mean(signal) + 0.8 * np.std(signal))
    dynamic_threshold = max(dynamic_threshold, 0.4)
    local_maxima = np.where(
        (signal[1:-1] > signal[:-2])
        & (signal[1:-1] >= signal[2:])
        & (signal[1:-1] > dynamic_threshold)
    )[0] + 1

    refractory_samples = max(int(0.25 * sampling_rate), 1)
    selected: list[int] = []
    for peak_index in local_maxima.tolist():
        if not selected or peak_index - selected[-1] >= refractory_samples:
            selected.append(peak_index)
            continue
        if signal[peak_index] > signal[selected[-1]]:
            selected[-1] = peak_index

    return np.asarray(selected, dtype=int)


def _estimate_rr_irregularity(ecg_signal: np.ndarray, sampling_rate: float) -> float:
    """Estimate heartbeat irregularity from normalized RR interval variation."""
    peaks = _detect_r_peaks(ecg_signal, sampling_rate)
    if peaks.size < 3:
        return 0.0

    rr_intervals = np.diff(peaks) / sampling_rate
    rr_mean = float(np.mean(rr_intervals))
    if rr_mean <= 1e-8:
        return 0.0
    return float(np.std(rr_intervals) / rr_mean)


def build_feature_vector(
    ecg_signal: np.ndarray,
    vitals_history: list[dict[str, float]] | None,
    sampling_rate: float = 250.0,
) -> FeatureBundle:
    """Combine waveform statistics, vitals trends, and FFT features into one vector."""
    signal = np.asarray(ecg_signal, dtype=float)
    vitals = _coerce_vital_history(vitals_history)
    latest_vitals = vitals[-1] if vitals else {
        "heart_rate": 0.0,
        "spo2": 0.0,
        "temperature": 0.0,
        "respiration": 0.0,
    }

    signal_trend = _compute_slope(signal.tolist()) if signal.size > 1 else 0.0
    rr_irregularity = _estimate_rr_irregularity(signal, sampling_rate)
    fft_features = extract_fft_features(signal, sampling_rate=sampling_rate)

    heart_rates = [item["heart_rate"] for item in vitals]
    spo2_values = [item["spo2"] for item in vitals]
    temperatures = [item["temperature"] for item in vitals]
    respirations = [item["respiration"] for item in vitals]

    ordered_values = {
        "ecg_mean": float(np.mean(signal)) if signal.size else 0.0,
        "ecg_std": float(np.std(signal)) if signal.size else 0.0,
        "ecg_min": float(np.min(signal)) if signal.size else 0.0,
        "ecg_max": float(np.max(signal)) if signal.size else 0.0,
        "ecg_median": float(np.median(signal)) if signal.size else 0.0,
        "ecg_peak_to_peak": float(np.ptp(signal)) if signal.size else 0.0,
        "ecg_trend": signal_trend,
        "ecg_rr_irregularity": rr_irregularity,
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

    return FeatureBundle(
        names=list(ordered_values.keys()),
        values=ordered_values,
        vector=np.asarray(list(ordered_values.values()), dtype=float),
    )
