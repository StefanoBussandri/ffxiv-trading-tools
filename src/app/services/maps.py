import logging
from typing import Any

from app.clients.universalis import UniversalisClient
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

log = logging.getLogger("maps")


def _map_ids() -> list[tuple[int, str]]:
    """Treasure-map (item_id, name) pairs from the cached catalogue.

    Catalogue is built by XIVAPIClient.populate_maps() — see clients/xivapi.py.
    New maps appear automatically once that cache is refreshed after a patch.
    """
    catalogue = cache.read("maps") or []
    if not catalogue:
        log.warning("maps catalogue empty — refresh with resource=maps")
    return [(int(m["item_id"]), m["name"]) for m in catalogue if m.get("item_id")]


async def scan_maps() -> list[dict]:
    """Single /aggregated call for all map IDs (≤100)."""
    u = UniversalisClient()
    worlds_by_id, worlds_by_name = _load_worlds()
    home_id = worlds_by_name.get(settings.HOME_WORLD)
    if home_id is None:
        raise RuntimeError("HOME_WORLD not in worlds cache")
    tax = _tax_pct()

    pairs = _map_ids()
    if not pairs:
        return []
    item_ids = [iid for iid, _ in pairs]

    data = await u.get_aggregated(settings.HOME_WORLD, item_ids)
    by_iid = {int(r["itemId"]): r for r in data.get("results", [])}

    out: list[dict] = []
    for iid, name in pairs:
        r = by_iid.get(iid)
        if not r:
            continue
        qd = r.get("nq") or {}
        ml = qd.get("minListing") or {}
        world_ml = ml.get("world") or {}
        dc_ml = ml.get("dc") or {}
        uploads = {ut["worldId"]: ut["timestamp"] for ut in r.get("worldUploadTimes", [])}
        home_ts = uploads.get(home_id, 0)
        velocity = ((qd.get("dailySaleVelocity") or {}).get("world") or {}).get("quantity") or 0
        signals = _extract_signals(qd)

        # Live prices: sell = cheapest home listing, buy = cheapest rival world.
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

        # Fallbacks when there is no live listing: use recent actual sales.
        fb = _fallback_prices(qd, home_id, worlds_by_id)
        if sell is None and fb["sell_price"]:
            sell, sell_est = fb["sell_price"], True
        if buy is None and fb["buy_price"]:
            buy, buy_world, buy_ts, buy_est = (
                fb["buy_price"], fb["buy_world"], fb["buy_ts"], True
            )

        row: dict[str, Any] = {
            "itemId": iid,
            "name": name,
            "icon_url": _icon_url(iid),
            "quality": "nq",
            "source": "map",
            "buy_world": buy_world,
            "buy_price": buy,
            "buy_price_estimated": buy_est,
            "sell_world": settings.HOME_WORLD,
            "sell_price": sell,
            "sell_price_estimated": sell_est,
            "profit": None,
            "roi_pct": None,
            "velocity": round(velocity, 3) if velocity else 0,
            "profit_per_day": None,
            "buy_upload_ts": buy_ts,
            "sell_upload_ts": int(home_ts),
            **signals,
            "spread_pct": _spread_pct(sell, signals["recent_purchase_price"]),
        }
        if sell and buy and buy < sell:
            profit = int(round(sell * (1 - tax) - buy))
            row["profit"] = profit
            if buy > 0:
                row["roi_pct"] = round(profit / buy * 100, 2)
            if velocity:
                row["profit_per_day"] = round(profit * velocity, 2)
        out.append(row)
    mark_stale(out)
    try:
        await enrich_rows(out, top_n=None)
    except Exception as e:
        log.warning("maps enrichment failed: %s", e)
    return out
