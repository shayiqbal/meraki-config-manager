"""GrayBar Meraki Manager - Web Application Entry Point."""
from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Ensure parent directory is on path so existing modules are importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── Session store ──────────────────────────────────────────────────────────────
_sessions: dict[str, dict[str, Any]] = {}
SESSION_TIMEOUT_HOURS = 8


def create_session(api_key: str) -> str:
    sid = str(uuid.uuid4())
    _sessions[sid] = {
        "api_key": api_key,
        "created": datetime.now(),
        "last_accessed": datetime.now(),
        "dry_runs": {},          # network_id -> DryRun
        "clone_configs": {},     # network_id -> CloneableConfig
    }
    return sid


def get_session(sid: str | None) -> dict[str, Any] | None:
    if not sid:
        return None
    s = _sessions.get(sid)
    if not s:
        return None
    if datetime.now() - s["last_accessed"] > timedelta(hours=SESSION_TIMEOUT_HOURS):
        _sessions.pop(sid, None)
        return None
    s["last_accessed"] = datetime.now()
    return s


def delete_session(sid: str) -> None:
    _sessions.pop(sid, None)


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(title="GrayBar Meraki Manager")

_BASE = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(_BASE / "templates"))

# Attach session helpers to app state for routers
app.state.create_session = create_session
app.state.get_session = get_session
app.state.delete_session = delete_session

# ── Routers ────────────────────────────────────────────────────────────────────
from webapp.routers import auth, compare, copy, exclusions, network_mgmt, networks  # noqa: E402

app.include_router(auth.router, prefix="/api")
app.include_router(networks.router, prefix="/api")
app.include_router(exclusions.router, prefix="/api")
app.include_router(copy.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(network_mgmt.router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    uvicorn.run("webapp.app:app", host="0.0.0.0", port=8000, reload=False)
