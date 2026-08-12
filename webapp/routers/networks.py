"""Networks router — organizations and network lists."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from webapp.session import make_client, require_session

router = APIRouter(tags=["networks"])


@router.get("/orgs")
async def list_orgs(session=Depends(require_session)) -> list:
    try:
        return make_client(session).organizations()
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/networks")
async def list_networks(
    org_id: str = Query(...),
    session=Depends(require_session),
) -> list:
    try:
        return make_client(session).networks(org_id)
    except Exception as exc:
        raise HTTPException(502, str(exc))
