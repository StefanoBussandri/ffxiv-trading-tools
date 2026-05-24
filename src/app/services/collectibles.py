"""Price the tradeable mount / minion catalogue against Universalis.

The catalogue (which mounts/minions exist, their summoning item_id, and whether
that item is tradeable) comes from FFXIVCollect — see clients/ffxivcollect.py.
This module filters that catalogue to tradeable entries and prices them with the
same /aggregated buy-low / sell-home model as the maps page.
"""
import asyncio
import logging
import time
from typing import Any

from app.clients.universalis import UniversalisClient, begin_batch, end_batch
from app.core import cache
from app.core.config import settings
from app.services.enrichment import enrich_rows
from app.services.opportunities import (
    _extract_signals,
    _fallback_prices,
    _icon_url,
    _load_worlds,
    _spread_pct,
    _tax_pct,
    mark_stale,
)

log = logging.getLogger("collectibles")

CHUNK = 100
KINDS = ("mounts", "minions")

# Per-kind scan cache: kind -> (timestamp, rows). Short TTL avoids re-pricing
# on every page load while still feeling live.
_scan_cache: dict[str, tuple[float, list[dict]]] = {}
_SCAN_TTL = 60.0
_scan_locks: dict[str, asyncio.Lock] = {}


def _format_sources(sources: list[dict]) -> tuple[str, str]:
    """Return (short, detail). short = unique source types; detail = full texts."""
    if not sources:
        return ("—", "")
    types: list[str] = []
    details: list[str] = []
    for s in sources:
        t = (s.get("type") or "").strip()
        txt = (s.get("text") or "").strip()
        if t and t not in types:
            types.append(t)
        if txt:
            details.append(f"{t}: {txt}" if t else txt)
        elif t:
            details.append(t)
    return (" / ".join(types) or "—", " · ".join(details))


def _tradeable_entries(kind: str) -> list[dict]:
    catalogue = cache.read(kind) or []
    return [c for c in catalogue if c.get("tradeable") and c.get("item_id")]


def _build_row(
    iid: int,
    entry: dict,
    r: dict[str, Any] | None,
    home_id: int,
    worlds_by_id: dict[int, str],
    tax: float,
) -> dict[str, Any]:
    """Build one display row. Emits a row even when the item has no market
    data, so the page always shows the full tradeable catalogue."""
    src_short, src_detail = _format_sources(entry.get("sources") or [])
    row: dict[str, Any] = {
        "itemId": iid,
        "name": entry.get("name") or str(iid),
        "icon_url": _icon_url(iid),
        "quality": "nq",
        "source": src_short,
        "source_detail": src_detail,
        "buy_world": None,
        "buy_price": None,
        "buy_price_estimated": False,
        "sell_world": settings.HOME_WORLD,
        "sell_price": None,
        "sell_price_estimated": False,
        "profit": None,
        "roi_pct": None,
        "velocity": 0,
        "profit_per_day": None,
        "buy_upload_ts": 0,
        "sell_upload_ts": 0,
        "median_listing": None,
        "avg_sale_price": None,
        "recent_purchase_price": None,
        "recent_purchase_ts": None,
        "recent_purchase_dc_price": None,
        "recent_purchase_dc_ts": None,
        "velocity_dc": 0,
        "spread_pct": None,
    }
    if not r:
        return row

    qd = r.get("nq") or {}
    ml = qd.get("minListing") or {}
    world_ml = ml.get("world") or {}
    dc_ml = ml.get("dc") or {}
    uploads = {ut["worldId"]: ut["timestamp"] for ut in r.get("worldUploadTimes", [])}
    home_ts = uploads.get(home_id, 0)
    velocity = ((qd.get("dailySaleVelocity") or {}).get("world") or {}).get("quantity") or 0
    signals = _extract_signals(qd)
    row.update(signals)
    row["sell_upload_ts"] = int(home_ts)
    row["velocity"] = round(velocity, 3) if velocity else 0

    # Live prices: sell = cheapest home-world listing, buy = cheapest rival world.
    sell = int(world_ml["price"]) if world_ml.get("price") else None
    sell_est = False
    buy: int | None = None
    buy_world: str | None = None
    buy_ts = 0
    buy_est = False
    dc_min_price = dc_ml.get("price")
    dc_min_wid = dc_ml.get("worldId")
    if dc_min_wid and dc_min_wid != home_id and dc_min_price:
        buy = int(dc_min_price)
        buy_world = worlds_by_id.get(dc_min_wid)
        buy_ts = int(uploads.get(dc_min_wid, 0))

    # Fallbacks when there is no live listing: use recent actual sales instead.
    fb = _fallback_prices(qd, home_id, worlds_by_id)
    if sell is None and fb["sell_price"]:
        sell, sell_est = fb["sell_price"], True
    if buy is None and fb["buy_price"]:
        buy, buy_world, buy_ts, buy_est = (
            fb["buy_price"], fb["buy_world"], fb["buy_ts"], True
        )

    row["sell_price"] = sell
    row["sell_price_estimated"] = sell_est
    row["buy_price"] = buy
    row["buy_world"] = buy_world
    row["buy_upload_ts"] = buy_ts
    row["buy_price_estimated"] = buy_est
    row["spread_pct"] = _spread_pct(sell, signals["recent_purchase_price"])

    if sell and buy and buy < sell:
        profit = int(round(sell * (1 - tax) - buy))
        row["profit"] = profit
        if buy > 0:
            row["roi_pct"] = round(profit / buy * 100, 2)
        if velocity:
            row["profit_per_day"] = round(profit * velocity, 2)
    return row


async def _do_scan(kind: str) -> list[dict]:
    entries = _tradeable_entries(kind)
    if not entries:
        log.warning("%s catalogue empty — run scripts/fetch_collectibles.py", kind)
        return []

    worlds_by_id, worlds_by_name = _load_worlds()
    home_id = worlds_by_name.get(settings.HOME_WORLD)
    if home_id is None:
        raise RuntimeError(f"HOME_WORLD {settings.HOME_WORLD!r} not in worlds cache")
    tax = _tax_pct()

    # Dedupe on item_id (a few mounts share one summoning item).
    by_iid_entry: dict[int, dict] = {}
    for c in entries:
        by_iid_entry.setdefault(int(c["item_id"]), c)
    item_ids = list(by_iid_entry)

    u = UniversalisClient()
    chunks = [item_ids[i:i + CHUNK] for i in range(0, len(item_ids), CHUNK)]
    started = time.monotonic()
    begin_batch("aggregated", len(item_ids))
    try:
        results = await asyncio.gather(
            *(u.get_aggregated(settings.HOME_WORLD, c) for c in chunks),
            return_exceptions=True,
        )
    finally:
        end_batch("aggregated")

    by_iid: dict[int, dict] = {}
    for res in results:
        if isinstance(res, Exception):
            log.warning("%s agg chunk failed: %s", kind, res)
            continue
        for r in res.get("results", []):
            iid = r.get("itemId")
            if iid is not None:
                by_iid[int(iid)] = r

    out = [
        _build_row(iid, entry, by_iid.get(iid), home_id, worlds_by_id, tax)
        for iid, entry in by_iid_entry.items()
    ]
    log.info(
        "%s scan done items=%d priced=%d elapsed=%.1fs",
        kind, len(item_ids), len(by_iid), time.monotonic() - started,
    )
    mark_stale(out)
    try:
        await enrich_rows(out, top_n=None)
    except Exception as e:
        log.warning("%s enrichment failed: %s", kind, e)
    return out


def _scan_lock(kind: str) -> asyncio.Lock:
    if kind not in _scan_locks:
        _scan_locks[kind] = asyncio.Lock()
    return _scan_locks[kind]


async def scan_collectible(kind: str, *, force: bool = False) -> list[dict]:
    if kind not in KINDS:
        raise ValueError(f"unknown collectible kind {kind!r}")
    if not force:
        entry = _scan_cache.get(kind)
        if entry and time.time() - entry[0] < _SCAN_TTL:
            return entry[1]
    async with _scan_lock(kind):
        if not force:
            entry = _scan_cache.get(kind)
            if entry and time.time() - entry[0] < _SCAN_TTL:
                return entry[1]
        rows = await _do_scan(kind)
        _scan_cache[kind] = (time.time(), rows)
        return rows


async def rescan_collectible_item(kind: str, item_id: int) -> dict | None:
    """Refresh one item via /aggregated; merge into the in-memory scan cache."""
    if kind not in KINDS:
        raise ValueError(f"unknown collectible kind {kind!r}")
    entry = next(
        (c for c in (cache.read(kind) or []) if c.get("item_id") == item_id),
        None,
    )
    if entry is None or not entry.get("tradeable"):
        return None

    u = UniversalisClient()
    data = await u.get_aggregated(settings.HOME_WORLD, [item_id])
    worlds_by_id, worlds_by_name = _load_worlds()
    home_id = worlds_by_name.get(settings.HOME_WORLD)
    if home_id is None:
        return None
    tax = _tax_pct()
    r = next(
        (x for x in data.get("results", []) if int(x.get("itemId") or 0) == item_id),
        None,
    )
    row = _build_row(item_id, entry, r, home_id, worlds_by_id, tax)
    try:
        await enrich_rows([row], top_n=None)
    except Exception as e:
        log.warning("%s rescan enrichment failed: %s", kind, e)

    cached = _scan_cache.get(kind)
    if cached is not None:
        ts, rows = cached
        rows = [x for x in rows if x["itemId"] != item_id]
        rows.append(row)
        _scan_cache[kind] = (ts, rows)
    return row
