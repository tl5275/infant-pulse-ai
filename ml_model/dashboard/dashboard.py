"""Matplotlib dashboard for live ECG and predicted waveform streaming."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import websocket

DEFAULT_WS_URL = "ws://127.0.0.1:8000/ws/live"


class LiveECGDashboard:
    """Display the latest ECG segment and short-horizon prediction live."""

    def __init__(
        self,
        websocket_url: str = DEFAULT_WS_URL,
        stop_event: threading.Event | None = None,
    ) -> None:
        self.websocket_url = websocket_url
        self.external_stop_event = stop_event
        self.local_stop_event = threading.Event()
        self.data_lock = threading.Lock()
        self.latest_data: dict[str, Any] = {
            "baby_id": "waiting",
            "ecg_signal": [],
            "predicted_ecg": [],
            "risk_score": 0.0,
            "anomaly": "normal",
            "early_warning": False,
            "status": "WAITING",
            "message": "Waiting for live ECG stream...",
        }
        self.ws_app: websocket.WebSocketApp | None = None

    def _should_stop(self) -> bool:
        return self.local_stop_event.is_set() or (
            self.external_stop_event is not None and self.external_stop_event.is_set()
        )

    def _on_open(self, _: websocket.WebSocketApp) -> None:
        print("[DASH] Connected to live WebSocket stream", flush=True)

    def _on_message(self, _: websocket.WebSocketApp, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return

        if isinstance(payload, dict):
            with self.data_lock:
                self.latest_data = payload

    def _on_error(self, _: websocket.WebSocketApp, error: Any) -> None:
        if not self._should_stop():
            print(f"[DASH] WebSocket error: {error}", flush=True)

    def _on_close(
        self,
        _: websocket.WebSocketApp,
        status_code: int | None,
        message: str | None,
    ) -> None:
        if not self._should_stop():
            print(
                f"[DASH] WebSocket closed (code={status_code}, message={message}), retrying...",
                flush=True,
            )

    def _receive_forever(self) -> None:
        while not self._should_stop():
            self.ws_app = websocket.WebSocketApp(
                self.websocket_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            self.ws_app.run_forever(ping_interval=20, ping_timeout=10)
            if not self._should_stop():
                time.sleep(1.0)

    def stop(self) -> None:
        """Request shutdown for both the plot loop and WebSocket client."""
        self.local_stop_event.set()
        if self.ws_app is not None:
            self.ws_app.keep_running = False
            self.ws_app.close()

    def run(self) -> None:
        """Start the WebSocket receiver and keep the dashboard updated."""
        receiver_thread = threading.Thread(target=self._receive_forever, daemon=True, name="live-websocket")
        receiver_thread.start()

        plt.ion()
        figure, axis = plt.subplots(figsize=(12, 5))
        real_line, = axis.plot([], [], linewidth=2.0, color="#0f766e", label="Real ECG")
        predicted_line, = axis.plot([], [], "--", linewidth=2.0, color="#dc2626", label="Predicted ECG")
        info_text = axis.text(
            0.02,
            0.97,
            "Waiting for ECG stream...",
            transform=axis.transAxes,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
        )

        axis.set_title("Infant Pulse Live ECG Monitor")
        axis.set_xlabel("Sample")
        axis.set_ylabel("Normalized Amplitude")
        axis.grid(alpha=0.25)
        axis.legend(loc="upper right")
        plt.show(block=False)

        try:
            while not self._should_stop() and plt.fignum_exists(figure.number):
                with self.data_lock:
                    payload = dict(self.latest_data)

                real_signal = np.asarray(payload.get("ecg_signal", []), dtype=float)
                predicted_signal = np.asarray(payload.get("predicted_ecg", []), dtype=float)

                real_x = np.arange(real_signal.size)
                predicted_x = np.arange(real_signal.size, real_signal.size + predicted_signal.size)
                real_line.set_data(real_x, real_signal)
                predicted_line.set_data(predicted_x, predicted_signal)

                combined = np.concatenate([real_signal, predicted_signal]) if (real_signal.size or predicted_signal.size) else np.asarray([0.0])
                axis.set_xlim(0, max(int(real_signal.size + predicted_signal.size), 1))
                amplitude_padding = max(float(np.ptp(combined)) * 0.15, 0.5)
                axis.set_ylim(float(np.min(combined)) - amplitude_padding, float(np.max(combined)) + amplitude_padding)

                info_text.set_text(
                    "\n".join(
                        [
                            f"Baby: {payload.get('baby_id', 'waiting')}",
                            f"Risk: {payload.get('risk_score', 0.0)}",
                            f"Anomaly: {payload.get('anomaly', 'normal')}",
                            f"Early warning: {payload.get('early_warning', False)}",
                            f"Status: {payload.get('status', 'WAITING')}",
                        ]
                    )
                )

                figure.canvas.draw_idle()
                plt.pause(0.1)
        finally:
            self.stop()
            plt.close(figure)


def launch_dashboard(
    websocket_url: str = DEFAULT_WS_URL,
    stop_event: threading.Event | None = None,
) -> None:
    """Run the live matplotlib dashboard."""
    LiveECGDashboard(websocket_url=websocket_url, stop_event=stop_event).run()


if __name__ == "__main__":
    launch_dashboard()
