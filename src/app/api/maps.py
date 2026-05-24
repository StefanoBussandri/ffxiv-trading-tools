import time

from fastapi import APIRouter

from app.services.maps import scan_maps

router = APIRouter(prefix="/api/maps", tags=["maps"])


@router.get("")
async def get_maps() -> dict:
    rows = await scan_maps()
    return {"count": len(rows), "rows": rows, "ts": int(time.time() * 1000)}
