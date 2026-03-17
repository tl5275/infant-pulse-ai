"""Render-compatible entrypoint for the Infant Pulse FastAPI backend.

This file allows the deployment command `uvicorn app:app` to work from the
`Backend Infant Pulse` root directory without shadowing the real `app` package
located under `backend/app`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
BACKEND_PACKAGE_ROOT = BACKEND_ROOT / "app"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Treat this launcher module as the package container for backend/app so that
# imports like `from app.ai import ...` continue to resolve when Render loads
# the project through `uvicorn app:app`.
__path__ = [str(BACKEND_PACKAGE_ROOT)]

from app.main import app as backend_app  # noqa: E402


app = backend_app

if not any(getattr(route, "path", None) == "/" for route in app.router.routes):
    @app.get("/", tags=["health"])
    async def root_health() -> dict[str, str]:
        return {"status": "ok"}


def main() -> None:
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
