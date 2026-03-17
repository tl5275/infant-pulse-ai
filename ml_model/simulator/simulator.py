"""Continuous simulator that posts ECG payloads to the backend."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ML_ENGINE_DIR = PROJECT_ROOT / "ml-engine"
if str(ML_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ML_ENGINE_DIR))

from data.simulator import InfantPulseSimulator

DEFAULT_API_URL = "http://127.0.0.1:8000/analyze"


class LiveSimulator:
    """Generate synthetic ECG segments and post them to the live backend."""

    def __init__(
        self,
        api_url: str = DEFAULT_API_URL,
        interval_seconds: float = 0.75,
        baby_id: str = "baby_01",
    ) -> None:
        self.api_url = api_url
        self.interval_seconds = interval_seconds
        self.baby_id = baby_id
        self.simulator = InfantPulseSimulator(num_babies=1)

    def _build_payload(self) -> dict[str, object]:
        """Generate the next ECG payload for the monitored infant."""
        return self.simulator.get_next_payload(self.baby_id)

    def _post_payload(self, payload: dict[str, object]) -> dict[str, object]:
        """Send a single ECG segment to the backend and return the JSON response."""
        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        """Continuously send ECG payloads until the caller requests shutdown."""
        active_stop_event = stop_event or threading.Event()
        while not active_stop_event.is_set():
            payload = self._build_payload()
            try:
                result = self._post_payload(payload)
                print(
                    f"[SIM] baby={result['baby_id']} risk={result['risk_score']} "
                    f"anomaly={result['anomaly']} early_warning={result['early_warning']}",
                    flush=True,
                )
            except urllib.error.URLError as exc:
                print(f"[SIM] backend unavailable: {exc}", flush=True)
            except Exception as exc:
                print(f"[SIM] simulator error: {exc}", flush=True)

            active_stop_event.wait(self.interval_seconds)


def main() -> None:
    """Run the simulator as a standalone process."""
    parser = argparse.ArgumentParser(description="Infant Pulse live simulator")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--interval", type=float, default=0.75)
    args = parser.parse_args()

    simulator = LiveSimulator(api_url=args.api_url, interval_seconds=args.interval)
    simulator.run_forever()


if __name__ == "__main__":
    main()
