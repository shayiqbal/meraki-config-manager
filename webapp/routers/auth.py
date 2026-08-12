"""Auth router — API key login / logout."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from config.settings import Settings
from meraki_client.client_v1 import MerakiVpnClientV1
from meraki_client.exceptions import AuthenticationError

router = APIRouter(tags=["auth"])
log = logging.getLogger("webapp.auth")


class LoginRequest(BaseModel):
    api_key: str


@router.post("/login")
async def login(body: LoginRequest, request: Request) -> dict:
    key = body.api_key.strip()
    if not key:
        raise HTTPException(400, "API key is required.")
    try:
        client = MerakiVpnClientV1(
            settings=Settings(api_key=key),
            logger=log,
        )
        orgs = client.organizations()
    except AuthenticationError:
        raise HTTPException(401, "Invalid API key — Meraki rejected authentication.")
    except Exception as exc:
        raise HTTPException(502, f"Could not reach Meraki: {exc}")

    sid = request.app.state.create_session(key)
    return {"session_id": sid, "orgs": orgs}


@router.post("/logout")
async def logout(
    request: Request,
    x_session_id: str | None = Header(default=None),
) -> dict:
    if x_session_id:
        request.app.state.delete_session(x_session_id)
    return {"ok": True}
