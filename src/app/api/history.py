from fastapi import APIRouter, Query

from app.services.history import top_history
from app.services.opportunities import _icon_url, _load_items

router = APIRouter(prefix="/api/history", tags=["history"])

VALID_METRICS = {"profit", "profit_per_day", "roi_pct", "velocity", "appearances"}
VALID_SOURCES = {"all", "cross-world", "vendor"}


@router.get("/top")
async def get_top(
    days: int = Query(7, ge=1, le=365),
    metric: str = Query("profit_per_day"),
    source: str = Query("all"),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    if metric not in VALID_METRICS:
        metric = "profit_per_day"
    if source not in VALID_SOURCES:
        source = "all"
    rows = await top_history(days=days, metric=metric, source=source, limit=limit)
    items_by_id = _load_items()
    for r in rows:
        iid = int(r["item_id"])
        r["name"] = items_by_id.get(iid, str(iid))
        r["icon_url"] = _icon_url(iid)
    return {
        "count": len(rows),
        "days": days,
        "metric": metric,
        "source": source,
        "rows": rows,
    }
