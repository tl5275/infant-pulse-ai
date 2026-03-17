"""PyTorch LSTM model for short-horizon ECG forecasting."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

DEFAULT_LSTM_PATH = Path(__file__).resolve().parents[1] / "saved_models" / "lstm.pth"
DEFAULT_INPUT_WINDOW = 100
DEFAULT_HORIZON = 20


class ECGLSTMPredictor(nn.Module):
    """Sequence-to-vector LSTM that predicts the next ECG segment."""

    def __init__(
        self,
        input_size: int = 1,
        hidden_size: int = 48,
        num_layers: int = 1,
        horizon: int = DEFAULT_HORIZON,
    ) -> None:
        """Initialize the LSTM forecasting network."""
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
        """Predict the next horizon samples from a rolling ECG window."""
        outputs, _ = self.lstm(inputs)
        return self.head(outputs[:, -1, :])


def _resolve_device(device: str | None = None) -> torch.device:
    """Select a torch device with a CPU fallback."""
    if device:
        return torch.device(device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def create_training_sequences(
    signal: np.ndarray,
    input_window: int = DEFAULT_INPUT_WINDOW,
    horizon: int = DEFAULT_HORIZON,
    stride: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """Split a waveform into supervised windows for autoregressive training."""
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
    """Persist a trained LSTM checkpoint and its configuration."""
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
    """Train the ECG LSTM on one or more waveform arrays and save the result."""
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
    """Load a persisted LSTM checkpoint and return the model with its input window."""
    if not model_path.exists():
        raise FileNotFoundError(f"LSTM model not found at {model_path}.")

    runtime_device = _resolve_device(device)
    checkpoint = torch.load(model_path, map_location=runtime_device)
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
    """Predict the next ECG horizon from the most recent ECG history."""
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
