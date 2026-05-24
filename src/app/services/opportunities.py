import asyncio
import logging
import time
from typing import Any

import aiosqlite

from app.clients.universalis import UniversalisClient, begin_batch, end_batch
from app.core import cache
from app.core.config import settings
from app.services.enrichment import enrich_rows
from app.services.history import record_opportunities, record_scan_run

log = logging.getLogger("opportunities")

CHUNK = 100

_items_cache: dict[int, str] | None = None
_icons_cache: dict[int, str] | None = None
_scan_cache: dict[str, tuple[float, list[dict]]] = {}
_scan_locks: dict[str, asyncio.Lock] = {}
_aggregated_pool: dict[int, dict] = {}
_aggregated_pool_ts: float = 0.0
_AGG_POOL_TTL = 60.0


async def _fetch_aggregated_for_items(
    item_ids: list[int], *, reset_pool: bool = False
) -> dict[int, dict]:
    """Fetch /aggregated for item_ids. Caches per-item results across scans.
    With reset_pool=True (or expired TTL) clears and refetches everything.
    """
    global _aggregated_pool_ts
    if reset_pool or (time.time() - _aggregated_pool_ts > _AGG_POOL_TTL):
        _aggregated_pool.clear()
    needed = [int(i) for i in item_ids if int(i) not in _aggregated_pool]
    if needed:
        u = UniversalisClient()
        chunks = [needed[i:i + CHUNK] for i in range(0, len(needed), CHUNK)]
        log.info(
            "agg pool fetching %d items (%d chunks); pool hits=%d",
            len(needed), len(chunks), len(item_ids) - len(needed),
        )
        begin_batch("aggregated", len(needed))
        try:
            results = await asyncio.gather(
                *(u.get_aggregated(settings.HOME_WORLD, c) for c in chunks),
                return_exceptions=True,
            )
        finally:
            end_batch("aggregated")
        for res in results:
            if isinstance(res, Exception):
                log.warning("agg chunk failed: %s", res)
                continue
            for r in res.get("results", []):
                iid = r.get("itemId")
                if iid is not None:
                    _aggregated_pool[int(iid)] = r
        _aggregated_pool_ts = time.time()
    else:
        log.info("agg pool full hit for %d items (no fetch needed)", len(item_ids))
    return {int(i): _aggregated_pool[int(i)] for i in item_ids if int(i) in _aggregated_pool}


def _scan_lock(key: str) -> asyncio.Lock:
    if key not in _scan_locks:
        _scan_locks[key] = asyncio.Lock()
    return _scan_locks[key]


def _load_icons() -> dict[int, str]:
    global _icons_cache
    if _icons_cache:
        return _icons_cache
    raw = cache.read("item_icons") or {}
    _icons_cache = {int(k): v for k, v in raw.items()}
    return _icons_cache


def reset_icons_cache() -> None:
    global _icons_cache
    _icons_cache = None


def _icon_url(item_id: int) -> str | None:
    return f"/api/icon/{item_id}" if _load_icons().get(item_id) else None


def _load_items() -> dict[int, str]:
    global _items_cache
    if _items_cache is not None:
        return _items_cache
    import json
    path = settings.cache_dir / "items.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    _items_cache = {int(k): (v.get("en") or "") for k, v in raw.items()}
    return _items_cache


def _load_worlds() -> tuple[dict[int, str], dict[str, int]]:
    worlds = cache.read("worlds") or []
    by_id = {int(w["id"]): w["name"] for w in worlds}
    by_name = {w["name"]: int(w["id"]) for w in worlds}
    return by_id, by_name


def _tax_pct() -> float:
    rates = cache.read("tax_rates") or {}
    return float(rates.get(settings.TAX_CITY) or 0) / 100.0


def _cached(key: str) -> list[dict] | None:
    entry = _scan_cache.get(key)
    if not entry:
        return None
    return entry[1]


def _cached_ts(key: str) -> float | None:
    entry = _scan_cache.get(key)
    return entry[0] if entry else None


def _set_cached(key: str, val: list[dict]) -> None:
    _scan_cache[key] = (time.time(), val)


def _extract_signals(qd: dict[str, Any]) -> dict[str, Any]:
    """Pull median/avg/recent-purchase world-scope fields from /aggregated quality block.

    Also extracts DC-scope fallback signals (velocity_dc, recent_purchase_dc_ts)
    used for display when home-world data is empty.
    """
    median = ((qd.get("medianListing") or {}).get("world") or {}).get("price")
    avg = ((qd.get("averageSalePrice") or {}).get("world") or {}).get("price")
    rp_world = (qd.get("recentPurchase") or {}).get("world") or {}
    rp_world_price = rp_world.get("price")
    rp_world_ts = rp_world.get("timestamp")
    rp_dc = (qd.get("recentPurchase") or {}).get("dc") or {}
    rp_dc_price = rp_dc.get("price")
    rp_dc_ts = rp_dc.get("timestamp")
    vel_dc = ((qd.get("dailySaleVelocity") or {}).get("dc") or {}).get("quantity") or 0
    return {
        "median_listing": int(median) if median else None,
        "avg_sale_price": float(avg) if avg else None,
        "recent_purchase_price": int(rp_world_price) if rp_world_price else None,
        "recent_purchase_ts": int(rp_world_ts) if rp_world_ts else None,
        "recent_purchase_dc_price": int(rp_dc_price) if rp_dc_price else None,
        "recent_purchase_dc_ts": int(rp_dc_ts) if rp_dc_ts else None,
        "velocity_dc": round(float(vel_dc), 3) if vel_dc else 0,
    }


def _fallback_prices(
    qd: dict[str, Any], home_id: int, worlds_by_id: dict[int, str]
) -> dict[str, Any]:
    """Recent-sale fallbacks for when an item has no live listing.

    sell_price  — most recent actual sale on the home world (Odin).
    buy_price   — smallest recent purchase across world/dc scope (cheapest
                  recently-sold price), with the world it sold on.
    """
    rp = qd.get("recentPurchase") or {}
    rp_world = rp.get("world") or {}
    rp_dc = rp.get("dc") or {}
    sell_price = rp_world.get("price")

    cands: list[tuple[int, str | None, int]] = []
    if rp_dc.get("price"):
        wid = rp_dc.get("worldId")
        cands.append((
            int(rp_dc["price"]),
            worlds_by_id.get(wid) if wid else None,
            int(rp_dc.get("timestamp") or 0),
        ))
    if rp_world.get("price"):
        cands.append((
            int(rp_world["price"]),
            worlds_by_id.get(home_id),
            int(rp_world.get("timestamp") or 0),
        ))
    buy = min(cands, key=lambda c: c[0]) if cands else None
    return {
        "sell_price": int(sell_price) if sell_price else None,
        "buy_price": buy[0] if buy else None,
        "buy_world": buy[1] if buy else None,
        "buy_ts": buy[2] if buy else 0,
    }


def _spread_pct(sell_price: int | None, recent_purchase_price: int | None) -> float | None:
    if not sell_price or not recent_purchase_price:
        return None
    return round((sell_price - recent_purchase_price) / recent_purchase_price * 100, 2)


def mark_stale(rows: list[dict]) -> None:
    """Flag rows whose market data is older than STALE_DATA_HOURS.

    data_stale is True when the oldest upload feeding the row exceeds the
    cutoff. Rows with no upload timestamps are left unflagged.
    """
    cutoff_ms = settings.STALE_DATA_HOURS * 3600 * 1000
    now_ms = time.time() * 1000
    for r in rows:
        ages = [now_ms - ts for ts in (r.get("buy_upload_ts"), r.get("sell_upload_ts")) if ts]
        r["data_stale"] = bool(ages) and max(ages) > cutoff_ms


def _row_from_aggregated(
    r: dict[str, Any],
    home_id: int,
    worlds_by_id: dict[int, str],
    items_by_id: dict[int, str],
    tax: float,
    fresh_ms: int,
    now_ms: float,
) -> list[dict]:
    out: list[dict] = []
    iid = r.get("itemId")
    if iid is None:
        return out
    uploads = {ut["worldId"]: ut["timestamp"] for ut in r.get("worldUploadTimes", [])}
    home_ts = uploads.get(home_id, 0)
    for q in ("nq", "hq"):
        qd = r.get(q) or {}
        ml = qd.get("minListing") or {}
        world_ml = ml.get("world") or {}
        dc_ml = ml.get("dc") or {}
        sell_price = world_ml.get("price")
        buy_price = dc_ml.get("price")
        buy_wid = dc_ml.get("worldId")
        if not sell_price or not buy_price or not buy_wid:
            continue
        if buy_wid == home_id:
            continue
        if buy_price >= sell_price:
            continue
        velocity = ((qd.get("dailySaleVelocity") or {}).get("world") or {}).get("quantity") or 0
        buy_ts = uploads.get(buy_wid, 0)
        if not home_ts or not buy_ts:
            continue
        if now_ms - home_ts > fresh_ms or now_ms - buy_ts > fresh_ms:
            continue
        profit = int(round(sell_price * (1 - tax) - buy_price))
        if profit < settings.MIN_PROFIT_GIL:
            continue
        roi_pct = profit / buy_price * 100
        if roi_pct < settings.MIN_ROI_PCT or roi_pct > settings.MAX_ROI_PCT:
            continue
        if velocity < settings.MIN_SALES_PER_DAY:
            continue
        profit_per_day = profit * velocity
        signals = _extract_signals(qd)
        out.append({
            "itemId": int(iid),
            "name": items_by_id.get(int(iid), str(iid)),
            "icon_url": _icon_url(int(iid)),
            "quality": q,
            "source": "cross-world",
            "buy_world": worlds_by_id.get(buy_wid, str(buy_wid)),
            "buy_price": int(buy_price),
            "sell_world": settings.HOME_WORLD,
            "sell_price": int(sell_price),
            "profit": profit,
            "roi_pct": round(roi_pct, 2),
            "velocity": round(velocity, 3),
            "profit_per_day": round(profit_per_day, 2),
            "buy_upload_ts": int(buy_ts),
            "sell_upload_ts": int(home_ts),
            **signals,
            "spread_pct": _spread_pct(int(sell_price), signals["recent_purchase_price"]),
        })
    return out


def _dedupe_vendor() -> dict[int, tuple[int, str, int]]:
    """itemId -> (cheapest gilPrice, shopName, shopId)."""
    vendor = cache.read("vendor_items") or []
    out: dict[int, tuple[int, str, int]] = {}
    for v in vendor:
        iid = v.get("itemId")
        price = v.get("gilPrice") or 0
        if iid is None or price <= 0:
            continue
        key = int(iid)
        entry = (int(price), v.get("shopName") or "", int(v.get("shopId") or 0))
        cur = out.get(key)
        if cur is None or entry[0] < cur[0]:
            out[key] = entry
    return out


async def scan_vendor(*, force: bool = False) -> list[dict]:
    if not force:
        cached = _cached("vendor")
        if cached is not None:
            log.info("scan cache hit vendor n=%d", len(cached))
            return cached
    async with _scan_lock("vendor"):
        if not force:
            cached = _cached("vendor")
            if cached is not None:
                return cached
        return await _do_scan_vendor()


async def _do_scan_vendor() -> list[dict]:
    started_at = int(time.time())
    marketable_set = set(int(i) for i in (cache.read("marketable") or []))
    vendor_prices = _dedupe_vendor()
    worlds_by_id, worlds_by_name = _load_worlds()
    items_by_id = _load_items()
    home_id = worlds_by_name.get(settings.HOME_WORLD)
    if home_id is None:
        raise RuntimeError(f"HOME_WORLD {settings.HOME_WORLD!r} not in worlds cache")
    tax = _tax_pct()
    fresh_ms = settings.LISTING_FRESHNESS_HOURS * 3600 * 1000
    now_ms = time.time() * 1000

    ids = sorted(i for i in vendor_prices if i in marketable_set)
    log.info("vendor scan starting ids=%d tax=%.3f", len(ids), tax)

    started = time.monotonic()
    item_to_result = await _fetch_aggregated_for_items(ids, reset_pool=False)

    out: list[dict] = []
    for iid, r in item_to_result.items():
        buy_info = vendor_prices.get(int(iid))
        if not buy_info:
            continue
        buy_price, shop_name, shop_id = buy_info
        uploads = {ut["worldId"]: ut["timestamp"] for ut in r.get("worldUploadTimes", [])}
        home_ts = uploads.get(home_id, 0)
        qd = r.get("nq") or {}
        ml = qd.get("minListing") or {}
        world_ml = ml.get("world") or {}
        sell_price = world_ml.get("price")
        if not sell_price:
            continue
        if sell_price <= buy_price:
            continue
        velocity = ((qd.get("dailySaleVelocity") or {}).get("world") or {}).get("quantity") or 0
        if not home_ts:
            continue
        if now_ms - home_ts > fresh_ms:
            continue
        profit = int(round(sell_price * (1 - tax) - buy_price))
        if profit < settings.MIN_PROFIT_GIL:
            continue
        roi_pct = profit / buy_price * 100
        if roi_pct < settings.MIN_ROI_PCT or roi_pct > settings.MAX_ROI_PCT:
            continue
        if velocity < settings.MIN_SALES_PER_DAY:
            continue
        profit_per_day = profit * velocity
        signals = _extract_signals(qd)
        out.append({
            "itemId": int(iid),
            "name": items_by_id.get(int(iid), str(iid)),
            "icon_url": _icon_url(int(iid)),
            "quality": "nq",
            "source": "vendor",
            "buy_world": shop_name or f"Vendor #{shop_id}",
            "buy_price": int(buy_price),
            "sell_world": settings.HOME_WORLD,
            "sell_price": int(sell_price),
            "profit": profit,
            "roi_pct": round(roi_pct, 2),
            "velocity": round(velocity, 3),
            "profit_per_day": round(profit_per_day, 2),
            "buy_upload_ts": 0,
            "sell_upload_ts": int(home_ts),
            **signals,
            "spread_pct": _spread_pct(int(sell_price), signals["recent_purchase_price"]),
        })

    elapsed = time.monotonic() - started
    log.info("vendor scan done found=%d elapsed=%.1fs", len(out), elapsed)

    mark_stale(out)
    try:
        enriched = await enrich_rows(out, top_n=500)
        log.info("vendor enriched %d/%d rows", enriched, len(out))
    except Exception as e:
        log.warning("vendor enrichment failed: %s", e)
    _set_cached("vendor", out)
    try:
        await record_opportunities(out, source="vendor")
    except Exception as e:
        log.warning("history write failed: %s", e)
    try:
        await record_scan_run(
            source="vendor",
            started_at=started_at,
            finished_at=int(time.time()),
            items_scanned=len(ids),
            items_profitable=len(out),
        )
    except Exception as e:
        log.warning("scan_runs write failed: %s", e)
    return out


async def scan_cross_world(*, force: bool = False) -> list[dict]:
    if not force:
        cached = _cached("cross-world")
        if cached is not None:
            log.info("scan cache hit cross-world n=%d", len(cached))
            return cached
    async with _scan_lock("cross-world"):
        if not force:
            cached = _cached("cross-world")
            if cached is not None:
                return cached
        return await _do_scan_cross_world()


async def _do_scan_cross_world() -> list[dict]:
    started_at = int(time.time())
    marketable: list[int] = cache.read("marketable") or []
    worlds_by_id, worlds_by_name = _load_worlds()
    items_by_id = _load_items()
    home_id = worlds_by_name.get(settings.HOME_WORLD)
    if home_id is None:
        raise RuntimeError(f"HOME_WORLD {settings.HOME_WORLD!r} not in worlds cache")
    tax = _tax_pct()
    fresh_ms = settings.LISTING_FRESHNESS_HOURS * 3600 * 1000
    now_ms = time.time() * 1000

    log.info("cross-world scan starting ids=%d tax=%.3f home_id=%d",
             len(marketable), tax, home_id)

    started = time.monotonic()
    item_to_result = await _fetch_aggregated_for_items(marketable, reset_pool=True)

    out: list[dict] = []
    for r in item_to_result.values():
        out.extend(_row_from_aggregated(
            r, home_id, worlds_by_id, items_by_id, tax, fresh_ms, now_ms,
        ))

    elapsed = time.monotonic() - started
    log.info("cross-world scan done found=%d elapsed=%.1fs", len(out), elapsed)

    mark_stale(out)
    try:
        enriched = await enrich_rows(out, top_n=500)
        log.info("cross-world enriched %d/%d rows", enriched, len(out))
    except Exception as e:
        log.warning("cross-world enrichment failed: %s", e)

    _set_cached("cross-world", out)
    try:
        await record_opportunities(out, source="cross-world")
    except Exception as e:
        log.warning("history write failed: %s", e)
    try:
        await record_scan_run(
            source="cross-world",
            started_at=started_at,
            finished_at=int(time.time()),
            items_scanned=len(marketable),
            items_profitable=len(out),
        )
    except Exception as e:
        log.warning("scan_runs write failed: %s", e)
    return out


async def get_cross_world_cached() -> list[dict]:
    """Read-only: live cache if present, else DB snapshot. Never triggers a scan."""
    cached = _cached("cross-world")
    if cached is not None:
        return cached
    return await cached_rows_from_db("cross-world")


async def get_vendor_cached() -> list[dict]:
    cached = _cached("vendor")
    if cached is not None:
        return cached
    return await cached_rows_from_db("vendor")


async def cached_rows_from_db(source: str) -> list[dict]:
    """Latest snapshot per (item_id, quality) from history table — used as instant fallback."""
    sql = """
    WITH latest AS (
      SELECT item_id, quality, MAX(observed_at) AS max_t
      FROM history WHERE source = ?
      GROUP BY item_id, quality
    )
    SELECT h.item_id, h.quality, h.buy_world, h.buy_price, h.sell_world, h.sell_price,
           h.profit, h.roi_pct, h.velocity, h.observed_at,
           h.median_listing, h.avg_sale_price, h.recent_purchase_price,
           h.recent_purchase_ts, h.spread_pct
    FROM history h
    JOIN latest l ON h.item_id=l.item_id AND h.quality=l.quality AND h.observed_at=l.max_t
    WHERE h.source = ?
    """
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, (source, source))
        rows = await cur.fetchall()
    items_by_id = _load_items()
    out: list[dict] = []
    for r in rows:
        iid = int(r["item_id"])
        velocity = r["velocity"] or 0
        profit = r["profit"] or 0
        out.append({
            "itemId": iid,
            "name": items_by_id.get(iid, str(iid)),
            "icon_url": _icon_url(iid),
            "quality": r["quality"],
            "source": source,
            "buy_world": r["buy_world"],
            "buy_price": r["buy_price"],
            "sell_world": r["sell_world"],
            "sell_price": r["sell_price"],
            "profit": profit,
            "roi_pct": r["roi_pct"],
            "velocity": velocity,
            "profit_per_day": round(profit * velocity, 2),
            "buy_upload_ts": 0,
            "sell_upload_ts": int(r["observed_at"]) * 1000,
            "from_cache": True,
            "median_listing": r["median_listing"],
            "avg_sale_price": r["avg_sale_price"],
            "recent_purchase_price": r["recent_purchase_price"],
            "recent_purchase_ts": r["recent_purchase_ts"],
            "spread_pct": r["spread_pct"],
        })
    return out


async def rescan_single_item(source: str, item_id: int) -> dict | None:
    """Refresh one item via /aggregated; merge into in-memory scan cache."""
    u = UniversalisClient()
    data = await u.get_aggregated(settings.HOME_WORLD, [item_id])
    worlds_by_id, worlds_by_name = _load_worlds()
    items_by_id = _load_items()
    home_id = worlds_by_name.get(settings.HOME_WORLD)
    if home_id is None:
        return None
    tax = _tax_pct()
    fresh_ms = settings.LISTING_FRESHNESS_HOURS * 3600 * 1000
    now_ms = time.time() * 1000

    new_rows: list[dict] = []
    for r in data.get("results", []):
        if int(r.get("itemId") or 0) != item_id:
            continue
        if source == "cross-world":
            new_rows.extend(_row_from_aggregated(
                r, home_id, worlds_by_id, items_by_id, tax, fresh_ms, now_ms,
            ))
        elif source == "vendor":
            vendor_prices = _dedupe_vendor()
            marketable_set = set(int(i) for i in (cache.read("marketable") or []))
            if item_id not in marketable_set:
                continue
            buy_info = vendor_prices.get(item_id)
            if not buy_info:
                continue
            buy_price, shop_name, shop_id = buy_info
            uploads = {ut["worldId"]: ut["timestamp"] for ut in r.get("worldUploadTimes", [])}
            home_ts = uploads.get(home_id, 0)
            qd = r.get("nq") or {}
            ml = qd.get("minListing") or {}
            world_ml = ml.get("world") or {}
            sell_price = world_ml.get("price")
            if not sell_price or sell_price <= buy_price or not home_ts:
                continue
            if now_ms - home_ts > fresh_ms:
                continue
            velocity = ((qd.get("dailySaleVelocity") or {}).get("world") or {}).get("quantity") or 0
            profit = int(round(sell_price * (1 - tax) - buy_price))
            roi_pct = profit / buy_price * 100 if buy_price > 0 else 0
            signals = _extract_signals(qd)
            new_rows.append({
                "itemId": item_id,
                "name": items_by_id.get(item_id, str(item_id)),
                "icon_url": _icon_url(item_id),
                "quality": "nq",
                "source": "vendor",
                "buy_world": shop_name or f"Vendor #{shop_id}",
                "buy_price": int(buy_price),
                "sell_world": settings.HOME_WORLD,
                "sell_price": int(sell_price),
                "profit": profit,
                "roi_pct": round(roi_pct, 2),
                "velocity": round(velocity, 3),
                "profit_per_day": round(profit * velocity, 2),
                "buy_upload_ts": 0,
                "sell_upload_ts": int(home_ts),
                **signals,
                "spread_pct": _spread_pct(int(sell_price), signals["recent_purchase_price"]),
            })

    if new_rows:
        try:
            await enrich_rows(new_rows, top_n=None)
        except Exception as e:
            log.warning("rescan enrichment failed: %s", e)
    cached = _scan_cache.get(source)
    if cached is not None:
        ts, rows = cached
        rows = [r for r in rows if r["itemId"] != item_id]
        rows.extend(new_rows)
        _scan_cache[source] = (ts, rows)
    try:
        await record_opportunities(new_rows, source=source)
    except Exception as e:
        log.warning("rescan history write failed: %s", e)
    return new_rows[0] if new_rows else None
