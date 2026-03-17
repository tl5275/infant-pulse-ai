"""Training bootstrap for Infant Pulse saved models."""

from __future__ import annotations

import argparse
from pathlib import Path

from data.sample_dataset import generate_sample_dataset
from services.prediction_service import PredictionService


def main() -> None:
    """Generate sample data and retrain the saved models."""
    parser = argparse.ArgumentParser(description="Train Infant Pulse models on synthetic data")
    parser.add_argument("--dataset-size", type=int, default=120)
    parser.add_argument("--artifact-dir", default="artifacts")
    arguments = parser.parse_args()

    artifact_dir = Path(arguments.artifact_dir)
    dataset_files = generate_sample_dataset(artifact_dir, num_samples=arguments.dataset_size)

    service = PredictionService(auto_bootstrap=False)
    service.bootstrap_models(force_retrain=True)

    print(f"Sample dataset written to: {dataset_files['requests']}")
    print(f"Summary CSV written to: {dataset_files['summary']}")
    print(f"Anomaly model: {service.anomaly_path}")
    print(f"LSTM model: {service.lstm_path}")


if __name__ == "__main__":
    main()
