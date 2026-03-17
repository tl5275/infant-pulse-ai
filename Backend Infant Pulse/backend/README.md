# Infant Pulse Backend

Production-style FastAPI backend for neonatal vital ingestion, persistence, alerting, and real-time WebSocket streaming.

## Features

- Async FastAPI REST API
- PostgreSQL with SQLAlchemy ORM
- Background ingestion pipeline using `asyncio.Queue`
- WebSocket broadcast for live vitals and alerts
- Rule-based alert engine
- Async medical device simulator for multiple babies
- Environment-based configuration
- Docker Compose support
- Basic API and simulator tests

## Project Structure

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── websocket/
│   ├── simulator/
│   ├── database/
│   └── alerts/
├── tests/
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Setup

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example environment file and adjust it if needed:

```bash
cp .env.example .env
```

4. Start PostgreSQL locally, or use Docker Compose.

## Run With Docker

```bash
docker compose up --build
```

This starts PostgreSQL and the FastAPI application on `http://127.0.0.1:8000`.

## Run Locally

1. Start PostgreSQL and make sure `DATABASE_URL` in `.env` points to it.
2. Start the server from the `backend` directory:

```bash
uvicorn app.main:app --reload
```

3. Start the simulator in another terminal:

```bash
python -m app.simulator.runner
```

The API seeds 5 babies on startup by default. The simulator fetches those babies and streams vitals once per second.

## REST API

### List babies

```bash
curl http://127.0.0.1:8000/babies
```

### Ingest vitals manually

```bash
curl -X POST http://127.0.0.1:8000/vitals \
  -H "Content-Type: application/json" \
  -d '{
    "baby_id": 1,
    "heart_rate": 176,
    "spo2": 88,
    "temperature": 37.9,
    "resp_rate": 42
  }'
```

### Get recent vitals for a baby

```bash
curl http://127.0.0.1:8000/vitals/1
```

### Get alerts

```bash
curl http://127.0.0.1:8000/alerts
```

## WebSocket Testing

Connect to the live stream:

```text
ws://127.0.0.1:8000/ws/vitals
```

Example using `wscat`:

```bash
npx wscat -c ws://127.0.0.1:8000/ws/vitals
```

The server broadcasts JSON events in this form:

```json
{
  "event": "vital",
  "data": {
    "id": 101,
    "baby_id": 1,
    "heart_rate": 148,
    "spo2": 97,
    "temperature": 36.9,
    "resp_rate": 41,
    "timestamp": "2026-03-17T06:30:00Z"
  }
}
```

Alert events are broadcast with `"event": "alert"`.

## Tests

Run the basic test suite from the `backend` directory:

```bash
pytest
```

