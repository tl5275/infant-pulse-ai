# Infant Pulse ML Engine

Production-style AI module for NICU monitoring with synthetic ECG simulation, preprocessing, anomaly detection, ECG forecasting, early warnings, and explainable risk outputs.

## Features

- Real-time ECG and vitals simulator for multiple babies
- ECG preprocessing with FFT-based 0.5-40 Hz bandpass filtering and normalization
- FFT feature extraction and handcrafted feature engineering
- Isolation Forest anomaly detection
- PyTorch LSTM ECG waveform prediction from the last 100 samples to the next 20 samples
- Early warning detection for dropping SpO2, rising HR, and irregular ECG peaks
- Fused risk scoring with explainable output
- FastAPI `/analyze` endpoint

## Project Structure

```text
ml-engine/
├── app/
│   ├── main.py
│   ├── routes.py
│   └── schemas.py
├── data/
│   ├── sample_dataset.py
│   └── simulator.py
├── models/
│   ├── anomaly_model.py
│   ├── fft_features.py
│   └── lstm_model.py
├── saved_models/
├── services/
│   ├── early_warning.py
│   ├── feature_engineering.py
│   ├── prediction_service.py
│   └── risk_engine.py
├── utils/
│   └── preprocessing.py
├── requirements.txt
└── train_models.py
```

## Setup

```bash
cd ml-engine
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Train Models

```bash
python train_models.py --dataset-size 150
```

This generates:

- `saved_models/anomaly.pkl`
- `saved_models/lstm.pth`
- `artifacts/synthetic_requests.jsonl`
- `artifacts/synthetic_summary.csv`

## Run The API

```bash
uvicorn app.main:app --reload
```

## Example API Call

```bash
curl -X POST http://127.0.0.1:8000/analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"baby_id\":\"baby_01\",\"vitals\":[{\"heart_rate\":142,\"spo2\":98,\"temperature\":36.8,\"respiration\":40},{\"heart_rate\":146,\"spo2\":96,\"temperature\":36.9,\"respiration\":42}],\"ecg\":[0.01,0.12,0.42,0.95,0.21,-0.12,0.05,0.18,0.09,0.02],\"sampling_rate\":250}"
```

## Real-Time Simulation Client

Start the API first, then stream five babies every second:

```bash
python data/simulator.py --api-url http://127.0.0.1:8000/analyze --num-babies 5 --interval 1 --iterations 10
```

## Notes

- The service bootstraps models automatically if `saved_models/` is empty.
- Synthetic data is useful for local demos and backend integration, but real deployment should retrain on validated NICU waveforms and clinically reviewed thresholds.
