from fastapi import APIRouter, Query

from app.core.config import settings
from app.services.opportunities import (
    cached_rows_from_db,
    get_cross_world_cached,
    get_vendor_cached,
    rescan_single_item,
    scan_cross_world,
    scan_vendor,
)

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])

VALID_SORT = {
    "profit", "profit_per_day", "roi_pct", "velocity", "buy_price", "sell_price",
    "spread_pct", "recent_purchase_ts", "demand_pressure", "undercut_gap", "top_depth",
}

COMMODITY_MIN_VELOCITY = 20.0
COMMODITY_MAX_MARGIN_PCT = 15.0


def _shape_response(
    rows: list[dict],
    *,
    page: int,
    page_size: int | None,
    sort: str,
    sort_dir: str,
    quality: str,
    budget: int | None,
    commodity: bool = False,
    stale_only: bool = False,
    bargain_only: bool = False,
) -> dict:
    if quality in ("hq", "nq"):
        rows = [r for r in rows if r["quality"] == quality]
    if budget is not None and budget > 0:
        rows = [r for r in rows if r["buy_price"] is not None and r["buy_price"] <= budget]
    if commodity:
        rows = [
            r for r in rows
            if (r.get("velocity") or 0) >= COMMODITY_MIN_VELOCITY
            and (r.get("roi_pct") or 0) <= COMMODITY_MAX_MARGIN_PCT
        ]
    if stale_only:
        rows = [r for r in rows if r.get("stale_listing")]
    if bargain_only:
        rows = [r for r in rows if (r.get("spread_pct") or 0) < 0]
    if sort not in VALID_SORT:
        sort = "profit_per_day"
    reverse = sort_dir != "asc"
    rows = sorted(rows, key=lambda r: (r.get(sort) or 0), reverse=reverse)
    total = len(rows)
    size = page_size if page_size and page_size > 0 else settings.listings_ceiling
    if page < 1:
        page = 1
    pages = (total + size - 1) // size if total else 0
    start = (page - 1) * size
    paged = rows[start:start + size]
    return {
        "count": total,
        "page": page,
        "page_size": size,
        "pages": pages,
        "listings_ceiling": settings.listings_ceiling,
        "sort": sort,
        "sort_dir": sort_dir,
        "quality": quality,
        "budget": budget,
        "rows": paged,
    }


@router.get("/cross-world")
async def get_cross_world(
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None),
    sort: str = Query("profit_per_day"),
    sort_dir: str = Query("desc"),
    quality: str = Query("both"),
    budget: int | None = Query(None),
    force: bool = Query(False),
    cached: bool = Query(False),
    commodity: bool = Query(False),
    stale_only: bool = Query(False),
    bargain_only: bool = Query(False),
) -> dict:
    if force:
        rows = await scan_cross_world(force=True)
    elif cached:
        rows = await cached_rows_from_db("cross-world")
    else:
        rows = await get_cross_world_cached()
    return _shape_response(
        rows, page=page, page_size=page_size, sort=sort, sort_dir=sort_dir,
        quality=quality, budget=budget,
        commodity=commodity, stale_only=stale_only, bargain_only=bargain_only,
    )


@router.get("/vendor")
async def get_vendor(
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None),
    sort: str = Query("profit_per_day"),
    sort_dir: str = Query("desc"),
    quality: str = Query("both"),
    budget: int | None = Query(None),
    force: bool = Query(False),
    cached: bool = Query(False),
    commodity: bool = Query(False),
    stale_only: bool = Query(False),
    bargain_only: bool = Query(False),
) -> dict:
    if force:
        rows = await scan_vendor(force=True)
    elif cached:
        rows = await cached_rows_from_db("vendor")
    else:
        rows = await get_vendor_cached()
    return _shape_response(
        rows, page=page, page_size=page_size, sort=sort, sort_dir=sort_dir,
        quality=quality, budget=budget,
        commodity=commodity, stale_only=stale_only, bargain_only=bargain_only,
    )


@router.post("/cross-world/rescan/{item_id}")
async def rescan_cross_world(item_id: int) -> dict:
    row = await rescan_single_item("cross-world", item_id)
    return {"ok": True, "row": row, "filtered_out": row is None}


@router.post("/vendor/rescan/{item_id}")
async def rescan_vendor(item_id: int) -> dict:
    row = await rescan_single_item("vendor", item_id)
    return {"ok": True, "row": row, "filtered_out": row is None}
