"""Frequency-domain feature extraction for ECG signals."""

from __future__ import annotations

import numpy as np


def extract_fft_features(
    ecg_signal: np.ndarray,
    sampling_rate: float = 250.0,
) -> dict[str, float]:
    """Extract dominant ECG frequency, spectral energy, and top frequency peaks."""
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

    top_k = min(3, non_dc_power.size)
    peak_indices = np.argsort(non_dc_power)[-top_k:][::-1]
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
