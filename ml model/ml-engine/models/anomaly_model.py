"""Isolation Forest anomaly detection for Infant Pulse."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from joblib import dump, load
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DEFAULT_ANOMALY_PATH = Path(__file__).resolve().parents[1] / "saved_models" / "anomaly.pkl"


def train_anomaly_model(
    feature_matrix: np.ndarray,
    contamination: float = 0.08,
    save_path: Path = DEFAULT_ANOMALY_PATH,
    random_state: int = 42,
) -> Pipeline:
    """Train an Isolation Forest model on normal feature vectors and persist it."""
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
    """Load a persisted Isolation Forest pipeline from disk."""
    if not model_path.exists():
        raise FileNotFoundError(f"Anomaly model not found at {model_path}.")
    return load(model_path)


def detect_anomaly(
    features: np.ndarray,
    model: Pipeline | None = None,
    model_path: Path = DEFAULT_ANOMALY_PATH,
) -> dict[str, float | str]:
    """Score a feature vector and classify it as normal or anomalous."""
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
