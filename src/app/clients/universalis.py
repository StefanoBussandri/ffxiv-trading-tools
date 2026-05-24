import logging
from typing import Any, Iterable

from app.core import cache
from app.core.config import settings
from app.core.http_client import universalis_client

log = logging.getLogger("universalis")

# In-flight batch progress: kind -> (fetched_so_far, total_items_in_batch)
_batch_progress: dict[str, list[int]] = {}


def begin_batch(kind: str, total: int) -> None:
    _batch_progress[kind] = [0, total]


def end_batch(kind: str) -> None:
    _batch_progress.pop(kind, None)


def batch_progress(kind: str) -> dict | None:
    """Live progress of an in-flight item batch: {done, total}, or None."""
    state = _batch_progress.get(kind)
    if state is None:
        return None
    return {"done": state[0], "total": state[1]}


# Human-readable phase label per batch kind, for the topbar progress pill.
_BATCH_LABELS = {
    "aggregated": "Scanning prices",
    "currently_shown": "Enriching listings",
    "history": "Fetching sale history",
}


def active_batch() -> dict | None:
    """The largest in-flight item batch: {done, total, label}, or None.

    `done` counts responses *received* — the bottleneck the user waits on —
    not requests dispatched. Picks the batch with the most items so the pill
    tracks the dominant phase (price scan, then enrichment, etc.).
    """
    best: dict | None = None
    for kind, state in _batch_progress.items():
        total = state[1]
        if total <= 0:
            continue
        if best is None or total > best["total"]:
            best = {
                "done": state[0],
                "total": total,
                "label": _BATCH_LABELS.get(kind, "Working"),
            }
    return best


def _emit_request_log(kind: str, n: int) -> None:
    state = _batch_progress.get(kind)
    if state is not None:
        state[0] += n
        log.info("request:%s n=%d %d/%d", kind, n, state[0], state[1])
    else:
        log.info("request:%s n=%d", kind, n)


class UniversalisClient:
    def __init__(self) -> None:
        self.base = settings.UNIVERSALIS_BASE.rstrip("/")

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        client = universalis_client()
        url = f"{self.base}{path}"
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    async def get_data_centers(self, *, refresh: bool = False) -> Any:
        if not refresh:
            c = cache.read("data_centers")
            if c is not None:
                return c
        _emit_request_log("data_centers", 1)
        data = await self._get_json("/data-centers")
        cache.write("data_centers", data)
        return data

    async def get_worlds(self, *, refresh: bool = False) -> Any:
        if not refresh:
            c = cache.read("worlds")
            if c is not None:
                return c
        _emit_request_log("worlds", 1)
        data = await self._get_json("/worlds")
        cache.write("worlds", data)
        return data

    async def get_marketable(self, *, refresh: bool = False) -> list[int]:
        if not refresh:
            c = cache.read("marketable")
            if c is not None:
                return c
        _emit_request_log("marketable", 1)
        data = await self._get_json("/marketable")
        cache.write("marketable", data)
        return data

    async def get_tax_rates(self, world: str, *, refresh: bool = False) -> dict[str, int]:
        TAX_MAX_AGE_MS = 7 * 86400 * 1000
        if not refresh:
            c = cache.read("tax_rates")
            mtime = cache.mtime_ms("tax_rates")
            if c is not None and mtime is not None:
                import time
                age_ms = int(time.time() * 1000) - mtime
                if age_ms <= TAX_MAX_AGE_MS:
                    return c
        _emit_request_log("tax_rates", 1)
        data = await self._get_json("/tax-rates", params={"world": world})
        cache.write("tax_rates", data)
        return data

    async def get_aggregated(self, scope: str, item_ids: Iterable[int]) -> Any:
        ids = list(item_ids)
        if not ids:
            raise ValueError("no item ids")
        if len(ids) > 100:
            raise ValueError(f"max 100 IDs per call, got {len(ids)}")
        ids_str = ",".join(str(i) for i in ids)
        result = await self._get_json(f"/aggregated/{scope}/{ids_str}")
        # Count on response received, not request dispatched — concurrent
        # requests are all dispatched up front; the wait is the responses.
        _emit_request_log("aggregated", len(ids))
        return result

    async def get_currently_shown(
        self,
        scope: str,
        item_ids: Iterable[int],
        *,
        listings: int = 10,
        entries: int = 0,
        fields: str | None = (
            "items.itemID,items.unitsForSale,items.unitsSold,"
            "items.listings.pricePerUnit,items.listings.quantity,"
            "items.listings.lastReviewTime,items.listings.worldName,"
            "items.listings.hq"
        ),
    ) -> Any:
        ids = list(item_ids)
        if not ids:
            raise ValueError("no item ids")
        if len(ids) > 100:
            raise ValueError(f"max 100 IDs per call, got {len(ids)}")
        ids_str = ",".join(str(i) for i in ids)
        params: dict[str, Any] = {"listings": listings, "entries": entries}
        if fields:
            params["fields"] = fields
        result = await self._get_json(f"/{scope}/{ids_str}", params=params)
        _emit_request_log("currently_shown", len(ids))
        return result

    async def get_history(
        self,
        scope: str,
        item_ids: Iterable[int],
        *,
        entries_within: int | None = None,
        entries_to_return: int | None = None,
    ) -> Any:
        ids = list(item_ids)
        if not ids:
            raise ValueError("no item ids")
        if len(ids) > 100:
            raise ValueError(f"max 100 IDs per call, got {len(ids)}")
        ids_str = ",".join(str(i) for i in ids)
        params: dict[str, Any] = {}
        if entries_within:
            params["entriesWithin"] = entries_within
        if entries_to_return:
            params["entriesToReturn"] = entries_to_return
        result = await self._get_json(f"/history/{scope}/{ids_str}", params=params)
        _emit_request_log("history", len(ids))
        return result
