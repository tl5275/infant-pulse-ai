"""Signal preprocessing helpers for ECG waveforms."""

from __future__ import annotations

import numpy as np


def normalize_signal(signal: np.ndarray) -> np.ndarray:
    """Normalize a 1D signal to zero mean and unit variance."""
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
    """Apply an FFT-domain bandpass filter to an ECG waveform."""
    values = np.asarray(signal, dtype=float)
    if values.size == 0:
        return values

    frequencies = np.fft.rfftfreq(values.size, d=1.0 / sampling_rate)
    spectrum = np.fft.rfft(values)
    band_mask = (frequencies >= low_cut) & (frequencies <= high_cut)
    filtered = np.fft.irfft(spectrum * band_mask, n=values.size)
    return filtered.astype(float)


def preprocess_ecg_signal(signal: np.ndarray, sampling_rate: float = 250.0) -> np.ndarray:
    """Filter and normalize an ECG signal for downstream modeling."""
    filtered = bandpass_filter(signal, sampling_rate=sampling_rate)
    return normalize_signal(filtered)
