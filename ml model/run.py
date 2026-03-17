"""Single-command launcher for the Infant Pulse live monitoring stack."""

from __future__ import annotations

import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent
ML_ENGINE_DIR = PROJECT_ROOT / "ml-engine"
for path in (PROJECT_ROOT, ML_ENGINE_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.main import app
from dashboard.dashboard import launch_dashboard
from predictor import get_predictor
from simulator.simulator import LiveSimulator

API_HOST = "127.0.0.1"
API_PORT = 8000
HEALTH_URL = f"http://{API_HOST}:{API_PORT}/health"
ANALYZE_URL = f"http://{API_HOST}:{API_PORT}/analyze"


def wait_for_api(timeout_seconds: float = 45.0) -> None:
    """Block until the backend health endpoint starts responding."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=5) as response:
                if response.status == 200:
                    return
        except urllib.error.URLError:
            time.sleep(0.5)
        except Exception:
            time.sleep(0.5)

    raise TimeoutError(f"API did not become ready within {timeout_seconds:.0f} seconds.")


def start_api(server_holder: dict[str, uvicorn.Server]) -> None:
    """Start FastAPI with uvicorn inside a background thread."""
    config = uvicorn.Config(app=app, host=API_HOST, port=API_PORT, log_level="info")
    server = uvicorn.Server(config)
    server_holder["server"] = server
    server.run()


def start_simulator(stop_event: threading.Event) -> None:
    """Start the ECG simulator loop in a background thread."""
    simulator = LiveSimulator(api_url=ANALYZE_URL, interval_seconds=0.75)
    simulator.run_forever(stop_event)


def main() -> None:
    """Warm the models, start the backend, and open the live dashboard."""
    stop_event = threading.Event()
    server_holder: dict[str, uvicorn.Server] = {}

    # Keep matplotlib on the main thread for more reliable GUI behavior.
    get_predictor()

    api_thread = threading.Thread(target=start_api, args=(server_holder,), daemon=True, name="infant-pulse-api")
    api_thread.start()

    wait_for_api()

    simulator_thread = threading.Thread(
        target=start_simulator,
        args=(stop_event,),
        daemon=True,
        name="infant-pulse-simulator",
    )
    simulator_thread.start()

    try:
        launch_dashboard(stop_event=stop_event)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server = server_holder.get("server")
        if server is not None:
            server.should_exit = True
        simulator_thread.join(timeout=2.0)
        api_thread.join(timeout=5.0)


if __name__ == "__main__":
    main()
