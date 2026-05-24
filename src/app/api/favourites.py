import time

from fastapi import APIRouter, HTTPException

from app.clients.universalis import UniversalisClient
from app.core.config import settings
from app.models.favourite import FavouriteAdd, FavouriteAlert
from app.services.favourites import (
    add_favourite,
    list_favourites,
    remove_favourite,
    set_favourite_alert,
)
from app.services.enrichment import enrich_rows
from app.services.opportunities import (
    _extract_signals,
    _icon_url,
    _load_items,
    _load_worlds,
    _spread_pct,
    _tax_pct,
    mark_stale,
)

router = APIRouter(prefix="/api/favourites", tags=["favourites"])


@router.get("")
async def get_favourites() -> dict:
    rows = await list_favourites()
    return {"count": len(rows), "rows": rows}


@router.post("")
async def post_favourite(body: FavouriteAdd) -> dict:
    if body.quality not in ("hq", "nq"):
        raise HTTPException(status_code=400, detail="quality must be hq or nq")
    await add_favourite(body.item_id, body.quality)
    return {"ok": True}


@router.delete("/{item_id}/{quality}")
async def delete_favourite(item_id: int, quality: str) -> dict:
    if quality not in ("hq", "nq"):
        raise HTTPException(status_code=400, detail="quality must be hq or nq")
    removed = await remove_favourite(item_id, quality)
    return {"ok": True, "removed": removed}


@router.put("/{item_id}/{quality}/alert")
async def put_favourite_alert(
    item_id: int, quality: str, body: FavouriteAlert
) -> dict:
    if quality not in ("hq", "nq"):
        raise HTTPException(status_code=400, detail="quality must be hq or nq")
    for d in (body.buy_dir, body.sell_dir):
        if d is not None and d not in ("below", "above"):
            raise HTTPException(status_code=400, detail="dir must be below or above")
    ok = await set_favourite_alert(
        item_id, quality, body.buy_target, body.buy_dir,
        body.sell_target, body.sell_dir,
    )
    return {"ok": ok}


@router.get("/snapshot")
async def get_snapshot() -> dict:
    favs = await list_favourites()
    if not favs:
        return {
            "rows": [],
            "ts": int(time.time() * 1000),
        }
    item_ids = sorted({f["item_id"] for f in favs})
    chunks = [item_ids[i:i + 100] for i in range(0, len(item_ids), 100)]
    u = UniversalisClient()
    worlds_by_id, worlds_by_name = _load_worlds()
    items_by_id = _load_items()
    home_id = worlds_by_name.get(settings.HOME_WORLD)
    if home_id is None:
        raise HTTPException(500, "HOME_WORLD not in worlds cache")
    tax = _tax_pct()

    by_iid: dict[int, dict] = {}
    for chunk in chunks:
        data = await u.get_aggregated(settings.HOME_WORLD, chunk)
        for r in data.get("results", []):
            by_iid[int(r["itemId"])] = r

    out: list[dict] = []
    for f in favs:
        iid = int(f["item_id"])
        q = f["quality"]
        r = by_iid.get(iid)
        row = {
            "itemId": iid,
            "name": items_by_id.get(iid, str(iid)),
            "icon_url": _icon_url(iid),
            "quality": q,
            "source": "favourite",
            "buy_target": f.get("buy_target"),
            "buy_dir": f.get("buy_dir"),
            "sell_target": f.get("sell_target"),
            "sell_dir": f.get("sell_dir"),
            "buy_world": None,
            "buy_price": None,
            "sell_world": settings.HOME_WORLD,
            "sell_price": None,
            "profit": None,
            "roi_pct": None,
            "velocity": 0,
            "profit_per_day": None,
            "buy_upload_ts": 0,
            "sell_upload_ts": 0,
            "added_at": f["added_at"],
            "median_listing": None,
            "avg_sale_price": None,
            "recent_purchase_price": None,
            "recent_purchase_ts": None,
            "spread_pct": None,
        }
        if r:
            qd = r.get(q) or {}
            ml = qd.get("minListing") or {}
            world_ml = ml.get("world") or {}
            dc_ml = ml.get("dc") or {}
            uploads = {ut["worldId"]: ut["timestamp"] for ut in r.get("worldUploadTimes", [])}
            sell_price = world_ml.get("price")
            dc_min_price = dc_ml.get("price")
            dc_min_wid = dc_ml.get("worldId")
            velocity = ((qd.get("dailySaleVelocity") or {}).get("world") or {}).get("quantity") or 0
            signals = _extract_signals(qd)
            row["sell_price"] = int(sell_price) if sell_price else None
            row["velocity"] = round(velocity, 3) if velocity else 0
            row["sell_upload_ts"] = int(uploads.get(home_id, 0))
            row.update(signals)
            row["spread_pct"] = _spread_pct(
                int(sell_price) if sell_price else None,
                signals["recent_purchase_price"],
            )
            if dc_min_wid and dc_min_wid != home_id and dc_min_price:
                row["buy_world"] = worlds_by_id.get(dc_min_wid)
                row["buy_price"] = int(dc_min_price)
                row["buy_upload_ts"] = int(uploads.get(dc_min_wid, 0))
                if sell_price and dc_min_price < sell_price:
                    profit = int(round(sell_price * (1 - tax) - dc_min_price))
                    row["profit"] = profit
                    if dc_min_price > 0:
                        row["roi_pct"] = round(profit / dc_min_price * 100, 2)
                    if velocity:
                        row["profit_per_day"] = round(profit * velocity, 2)
        out.append(row)
    mark_stale(out)
    try:
        await enrich_rows(out, top_n=None)
    except Exception as e:
        import logging
        logging.getLogger("favourites").warning("favourites enrichment failed: %s", e)
    return {
        "rows": out,
        "ts": int(time.time() * 1000),
    }
