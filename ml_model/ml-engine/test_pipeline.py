"""Simple smoke test for the live predictor."""

from __future__ import annotations

from data.simulator import InfantPulseSimulator
from predictor import get_predictor

payload = InfantPulseSimulator(num_babies=1).get_next_payload("baby_01")
result = get_predictor().predict(
    baby_id=payload["baby_id"],
    vitals_history=payload["vitals"],
    ecg_signal=payload["ecg"],
    sampling_rate=payload["sampling_rate"],
)

print(result)
