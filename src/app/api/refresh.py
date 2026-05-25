import asyncio

from fastapi import APIRouter, Query

from app.services.refresh import (
    bootstrap_status,
    refresh_resource,
    rescan_status,
    trigger_manual_rescan,
)

router = APIRouter(prefix="/api", tags=["refresh"])


@router.post("/refresh")
async def post_refresh(resource: str = Query("all")) -> dict:
    return await refresh_resource(resource)


@router.post("/refresh/scans")
async def post_refresh_scans() -> dict:
    """Fire-and-forget: spawn the cross-world + vendor rescan and return
    immediately so the UI doesn't block on the upstream calls."""
    status = rescan_status()
    if status.get("in_progress"):
        return {"ok": False, "started": False, "reason": "already in progress"}
    asyncio.create_task(trigger_manual_rescan())
    return {"ok": True, "started": True}


@router.get("/refresh/status")
async def get_refresh_status() -> dict:
    return rescan_status()


@router.get("/startup/status")
async def get_startup_status() -> dict:
    return bootstrap_status()
