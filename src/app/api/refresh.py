from fastapi import APIRouter, Query

from app.services.refresh import bootstrap_status, refresh_resource, rescan_status

router = APIRouter(prefix="/api", tags=["refresh"])


@router.post("/refresh")
async def post_refresh(resource: str = Query("all")) -> dict:
    return await refresh_resource(resource)


@router.get("/refresh/status")
async def get_refresh_status() -> dict:
    return rescan_status()


@router.get("/startup/status")
async def get_startup_status() -> dict:
    return bootstrap_status()
