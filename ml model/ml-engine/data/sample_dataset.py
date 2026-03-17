"""Sample synthetic dataset generation for Infant Pulse."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from data.simulator import generate_training_payloads


def _summarize_payload(payload: dict[str, object]) -> dict[str, float | str]:
    """Flatten a simulator payload into a tabular training summary."""
    vitals = payload["vitals"][-1]  # type: ignore[index]
    ecg = payload["ecg"]  # type: ignore[assignment]
    return {
        "baby_id": str(payload["baby_id"]),
        "heart_rate": float(vitals["heart_rate"]),  # type: ignore[index]
        "spo2": float(vitals["spo2"]),  # type: ignore[index]
        "temperature": float(vitals["temperature"]),  # type: ignore[index]
        "respiration": float(vitals["respiration"]),  # type: ignore[index]
        "ecg_length": float(len(ecg)),  # type: ignore[arg-type]
        "ecg_mean": float(sum(ecg) / len(ecg)),  # type: ignore[arg-type]
    }


def generate_sample_dataset(output_dir: str | Path, num_samples: int = 100) -> dict[str, Path]:
    """Generate JSONL request payloads and a flattened CSV summary."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    payloads = generate_training_payloads(num_samples=num_samples, force_anomaly=None)
    requests_path = output_path / "synthetic_requests.jsonl"
    summary_path = output_path / "synthetic_summary.csv"

    with requests_path.open("w", encoding="utf-8") as handle:
        for payload in payloads:
            handle.write(json.dumps(payload) + "\n")

    pd.DataFrame([_summarize_payload(item) for item in payloads]).to_csv(summary_path, index=False)
    return {"requests": requests_path, "summary": summary_path}


def main() -> None:
    """Create synthetic training/demo data on disk."""
    parser = argparse.ArgumentParser(description="Generate a synthetic Infant Pulse dataset")
    parser.add_argument("--output-dir", default="artifacts")
    parser.add_argument("--num-samples", type=int, default=100)
    arguments = parser.parse_args()

    files = generate_sample_dataset(arguments.output_dir, num_samples=arguments.num_samples)
    for name, path in files.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
