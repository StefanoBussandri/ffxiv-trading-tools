import time

from fastapi import APIRouter, HTTPException

from app.services.collectibles import KINDS, rescan_collectible_item, scan_collectible

router = APIRouter(prefix="/api/collectibles", tags=["collectibles"])


def _validate(kind: str) -> None:
    if kind not in KINDS:
        raise HTTPException(status_code=404, detail=f"unknown kind {kind!r}")


@router.get("/{kind}")
async def get_collectibles(kind: str) -> dict:
    _validate(kind)
    rows = await scan_collectible(kind)
    return {"count": len(rows), "rows": rows, "ts": int(time.time() * 1000)}


@router.post("/{kind}/rescan/{item_id}")
async def rescan_collectible(kind: str, item_id: int) -> dict:
    _validate(kind)
    row = await rescan_collectible_item(kind, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="item not in tradeable catalogue")
    return {"row": row}
