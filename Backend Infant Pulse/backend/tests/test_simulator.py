import random

from app.simulator.device_simulator import DeviceSimulator


def test_simulator_payload_shape_and_ranges() -> None:
    simulator = DeviceSimulator(
        api_url="http://127.0.0.1:8000",
        baby_count=5,
        interval_seconds=1.0,
        anomaly_probability=0.0,
        rng=random.Random(7),
    )

    payload = simulator.build_payload(1)

    assert payload.baby_id == 1
    assert 110 <= payload.heart_rate <= 165
    assert 92 <= payload.spo2 <= 100
    assert 36.0 <= payload.temperature <= 37.7
    assert 30 <= payload.resp_rate <= 60
