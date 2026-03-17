"""Early warning rules for neonatal monitoring."""

from __future__ import annotations

import numpy as np


def _compute_slope(values: list[float]) -> float:
    """Estimate a linear trend for a vital sign trajectory."""
    if len(values) < 2:
        return 0.0
    x_axis = np.arange(len(values), dtype=float)
    slope, _ = np.polyfit(x_axis, np.asarray(values, dtype=float), 1)
    return float(slope)


def _detect_peak_positions(ecg_signal: np.ndarray, sampling_rate: float) -> np.ndarray:
    """Identify likely ECG peaks using a local-maximum heuristic."""
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
    """Measure irregularity as the normalized spread of RR intervals."""
    peaks = _detect_peak_positions(ecg_signal, sampling_rate)
    if peaks.size < 3:
        return 0.0

    intervals = np.diff(peaks) / sampling_rate
    interval_mean = float(np.mean(intervals))
    if interval_mean <= 1e-8:
        return 0.0
    return float(np.std(intervals) / interval_mean)


def evaluate_early_warning(
    vitals_history: list[dict[str, float]] | None,
    ecg_signal: np.ndarray,
    sampling_rate: float = 250.0,
) -> dict[str, object]:
    """Detect early warning patterns from vitals trajectories and ECG rhythm."""
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
