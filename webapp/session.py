"""Shared session + client helpers for all routers."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Header, HTTPException, Request

from config.settings import Settings
from meraki_client.client_v1 import MerakiVpnClientV1


def require_session(
    request: Request,
    x_session_id: str | None = Header(default=None),
) -> dict[str, Any]:
    session = request.app.state.get_session(x_session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    return session


def make_client(session: dict[str, Any]) -> MerakiVpnClientV1:
    settings = Settings(api_key=session["api_key"])
    return MerakiVpnClientV1(settings=settings, logger=logging.getLogger("webapp.meraki"))
