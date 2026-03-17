from __future__ import annotations

import asyncio
import importlib
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "Backend Infant Pulse" / "backend"
FRONTEND_ROOT = PROJECT_ROOT / "Frontend InfantPlus"
FRONTEND_URL = "http://127.0.0.1:3000"
API_URL = "http://127.0.0.1:8000"
HEALTH_URL = f"{API_URL}/health"
PYTHON_DEPENDENCIES = {
    "uvicorn": "uvicorn[standard]>=0.34,<0.42",
    "fastapi": "fastapi>=0.115,<1.0",
    "sqlalchemy": "sqlalchemy>=2.0,<2.1",
    "httpx": "httpx>=0.28,<0.29",
    "pytest": "pytest>=8.3,<9.0",
    "aiosqlite": "aiosqlite>=0.20,<1.0",
    "numpy": "numpy>=1.26",
    "sklearn": "scikit-learn>=1.5",
    "torch": "torch>=2.2",
    "pydantic_settings": "pydantic-settings>=2.7,<3.0",
}


def log(tag: str, message: str) -> None:
    print(f"[{tag}] {message}", flush=True)


def ensure_backend_path() -> None:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))


def resolve_command(*candidates: str) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def init() -> None:
    (PROJECT_ROOT / "runtime").mkdir(parents=True, exist_ok=True)


def install_missing_python_modules(missing_modules: list[str]) -> None:
    packages = [PYTHON_DEPENDENCIES[module_name] for module_name in missing_modules]
    log("INIT", f"Installing missing Python modules for {Path(sys.executable).name}: {', '.join(missing_modules)}")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            *packages,
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )
    importlib.invalidate_caches()


def find_missing_python_modules() -> list[str]:
    missing_modules = []
    for module_name in PYTHON_DEPENDENCIES:
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing_modules.append(module_name)
    return missing_modules


def check_env() -> None:
    missing_modules = find_missing_python_modules()
    if missing_modules:
        install_missing_python_modules(missing_modules)
        missing_modules = find_missing_python_modules()

    missing_tools = []
    if resolve_command("node.exe", "node") is None:
        missing_tools.append("node")
    if resolve_command("npm.cmd", "npm") is None:
        missing_tools.append("npm")
    if missing_modules or missing_tools:
        issues = []
        if missing_modules:
            issues.append(f"missing Python modules: {', '.join(missing_modules)}")
        if missing_tools:
            issues.append(f"missing CLI tools: {', '.join(missing_tools)}")
        raise RuntimeError("; ".join(issues))

    log("INIT", "OK")


def preflight_stack() -> None:
    ensure_backend_path()

    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as client:
        response = client.get("/health")
        response.raise_for_status()
        health = response.json()

    if health["database"] != "connected":
        raise RuntimeError("Database preflight failed.")
    if health["model"] != "loaded":
        raise RuntimeError("Model preflight failed.")

    backend_label = health["database_backend"]
    if health.get("using_fallback"):
        backend_label = f"{backend_label} fallback"

    log("DB", f"Connected ({backend_label})")
    log("MODEL", "Loaded")


def build_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "")
    pythonpath_parts = [str(BACKEND_ROOT)]
    if current_pythonpath:
        pythonpath_parts.append(current_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    env.setdefault("NEXT_PUBLIC_API_BASE_URL", API_URL)
    return env


def run_tests() -> None:
    env = build_subprocess_env()
    npm_command = resolve_command("npm.cmd", "npm")
    if npm_command is None:
        raise RuntimeError("npm executable not found.")
    subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_pipeline.py"],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )
    subprocess.run(
        [npm_command, "run", "build"],
        cwd=FRONTEND_ROOT,
        env=env,
        check=True,
    )
    log("TEST", "Passed")


def wait_for_url(url: str, label: str, timeout_seconds: float = 60.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return
        except urllib.error.URLError:
            time.sleep(0.5)
        except Exception:
            time.sleep(0.5)

    raise TimeoutError(f"{label} did not become ready within {timeout_seconds:.0f} seconds.")


def start_backend() -> tuple[threading.Thread, dict[str, uvicorn.Server]]:
    ensure_backend_path()
    import uvicorn

    from app.main import app

    server_holder: dict[str, uvicorn.Server] = {}

    def run_server() -> None:
        config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="info")
        server = uvicorn.Server(config)
        server_holder["server"] = server
        server.run()

    thread = threading.Thread(target=run_server, daemon=True, name="infant-pulse-backend")
    thread.start()
    wait_for_url(HEALTH_URL, "Backend API")
    log("API", "Running")
    return thread, server_holder


def start_stream() -> tuple[threading.Thread, threading.Event]:
    ensure_backend_path()

    from app.core.config import get_settings
    from app.simulator.analysis_streamer import MultiBabyAnalysisStreamer

    settings = get_settings()
    stop_event = threading.Event()

    def run_streamer() -> None:
        streamer = MultiBabyAnalysisStreamer(
            api_url=settings.simulator_api_url,
            baby_count=settings.simulator_baby_count,
            interval_seconds=settings.simulator_interval_seconds,
            anomaly_probability=settings.simulator_anomaly_probability,
        )
        asyncio.run(streamer.run(stop_event))

    thread = threading.Thread(target=run_streamer, daemon=True, name="infant-pulse-stream")
    thread.start()
    time.sleep(2.0)
    log("STREAM", "Active")
    return thread, stop_event


def start_frontend() -> subprocess.Popen:
    env = build_subprocess_env()
    npm_command = resolve_command("npm.cmd", "npm")
    if npm_command is None:
        raise RuntimeError("npm executable not found.")
    process = subprocess.Popen(
        [npm_command, "run", "start", "--", "--hostname", "127.0.0.1", "--port", "3000"],
        cwd=FRONTEND_ROOT,
        env=env,
    )
    wait_for_url(FRONTEND_URL, "Frontend")
    return process


def main() -> None:
    backend_thread: threading.Thread | None = None
    server_holder: dict[str, uvicorn.Server] = {}
    stream_thread: threading.Thread | None = None
    stop_event: threading.Event | None = None
    frontend_process: subprocess.Popen | None = None

    try:
        init()
        check_env()
        preflight_stack()
        run_tests()
        backend_thread, server_holder = start_backend()
        stream_thread, stop_event = start_stream()
        frontend_process = start_frontend()

        while backend_thread.is_alive():
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        log("ERROR", str(exc))
        raise
    finally:
        if stop_event is not None:
            stop_event.set()
        if frontend_process is not None:
            frontend_process.terminate()
        server = server_holder.get("server")
        if server is not None:
            server.should_exit = True
        if stream_thread is not None:
            stream_thread.join(timeout=5.0)
        if backend_thread is not None:
            backend_thread.join(timeout=5.0)
        if frontend_process is not None:
            try:
                frontend_process.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                frontend_process.kill()


if __name__ == "__main__":
    main()
