"""Enrich opportunity rows with live listing-depth signals from /currentlyShown.

Fetches the cheapest listings + units-for-sale/units-sold per item, derives
top_depth, undercut_gap, stale_listing, demand_pressure, seller_count. Caches
per item with short TTL to avoid hammering Universalis between scans.
"""
import asyncio
import logging
import time
from typing import Any, Iterable

from app.clients.universalis import UniversalisClient, begin_batch, end_batch
from app.core.config import settings

log = logging.getLogger("enrichment")

CHUNK = 100
DEFAULT_TOP_N = 500
STALE_AGE_SECONDS = 7 * 86400
POOL_TTL = 60.0

# Per-item cache: itemId -> (timestamp, payload dict from /currentlyShown items[item])
_pool: dict[int, tuple[float, dict[str, Any]]] = {}


def _now() -> float:
    return time.time()


def _cached_item(item_id: int) -> dict[str, Any] | None:
    entry = _pool.get(int(item_id))
    if not entry:
        return None
    ts, payload = entry
    if _now() - ts > POOL_TTL:
        return None
    return payload


def _set_cached(item_id: int, payload: dict[str, Any]) -> None:
    _pool[int(item_id)] = (_now(), payload)


def reset_pool() -> None:
    _pool.clear()


def _derive_signals(payload: dict[str, Any], quality: str, now_s: float) -> dict[str, Any]:
    is_hq = quality == "hq"
    raw_listings = payload.get("listings") or []
    listings = [l for l in raw_listings if bool(l.get("hq")) == is_hq]
    listings.sort(key=lambda l: int(l.get("pricePerUnit") or 0))

    units_for_sale = int(payload.get("unitsForSale") or 0)
    units_sold = int(payload.get("unitsSold") or 0)
    demand_pressure = (units_sold / units_for_sale) if units_for_sale > 0 else None

    top_depth: int | None = None
    undercut_gap: float | None = None
    stale_listing: bool | None = None
    top_listing_age: int | None = None
    if listings:
        top = listings[0]
        top_price = int(top.get("pricePerUnit") or 0)
        top_depth = int(top.get("quantity") or 0)
        last_review = int(top.get("lastReviewTime") or 0)
        if last_review > 0:
            top_listing_age = int(now_s - last_review)
            stale_listing = top_listing_age > STALE_AGE_SECONDS
        if len(listings) >= 2 and top_price > 0:
            second_price = int(listings[1].get("pricePerUnit") or 0)
            undercut_gap = round((second_price - top_price) / top_price * 100, 2)
    return {
        "top_depth": top_depth,
        "undercut_gap": undercut_gap,
        "stale_listing": stale_listing,
        "top_listing_age_s": top_listing_age,
        "demand_pressure": round(demand_pressure, 3) if demand_pressure is not None else None,
        "units_for_sale": units_for_sale or None,
        "units_sold_window": units_sold or None,
    }


async def _fetch_currently_shown(item_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Fetch /currentlyShown for items not in cache. Returns full per-item payloads."""
    needed = [iid for iid in item_ids if _cached_item(iid) is None]
    if not needed:
        return {iid: _cached_item(iid) for iid in item_ids if _cached_item(iid) is not None}
    u = UniversalisClient()
    chunks = [needed[i:i + CHUNK] for i in range(0, len(needed), CHUNK)]
    log.info(
        "enrichment fetching %d items (%d chunks); cache hits=%d",
        len(needed), len(chunks), len(item_ids) - len(needed),
    )
    begin_batch("currently_shown", len(needed))
    try:
        results = await asyncio.gather(
            *(u.get_currently_shown(settings.HOME_WORLD, c) for c in chunks),
            return_exceptions=True,
        )
    finally:
        end_batch("currently_shown")
    for res in results:
        if isinstance(res, Exception):
            log.warning("enrichment chunk failed: %s", res)
            continue
        items = res.get("items") if isinstance(res, dict) else None
        if items:
            for iid, payload in items.items():
                _set_cached(int(iid), payload)
        elif isinstance(res, dict) and "itemID" in res:
            iid = res.get("itemID")
            if iid is not None:
                _set_cached(int(iid), res)
    out: dict[int, dict[str, Any]] = {}
    for iid in item_ids:
        cached = _cached_item(iid)
        if cached is not None:
            out[int(iid)] = cached
    return out


async def enrich_rows(
    rows: list[dict[str, Any]],
    *,
    top_n: int | None = DEFAULT_TOP_N,
    sort_key: str = "profit_per_day",
) -> int:
    """Mutate rows in place: attach listing-depth signals. Returns count enriched.

    Enriches at most ``top_n`` rows sorted by ``sort_key`` desc. Pass top_n=None
    to enrich all rows (use for small lists: maps, favourites).
    """
    if not rows:
        return 0
    if top_n is None or len(rows) <= top_n:
        target = rows
    else:
        target = sorted(rows, key=lambda r: r.get(sort_key) or 0, reverse=True)[:top_n]
    item_ids = sorted({int(r["itemId"]) for r in target if r.get("itemId") is not None})
    payloads = await _fetch_currently_shown(item_ids)
    now_s = _now()
    enriched = 0
    target_keys = {(int(r["itemId"]), r.get("quality")) for r in target}
    for r in rows:
        if r.get("itemId") is None:
            continue
        if (int(r["itemId"]), r.get("quality")) not in target_keys:
            continue
        payload = payloads.get(int(r["itemId"]))
        if not payload:
            continue
        signals = _derive_signals(payload, r.get("quality") or "nq", now_s)
        r.update(signals)
        enriched += 1
    return enriched
