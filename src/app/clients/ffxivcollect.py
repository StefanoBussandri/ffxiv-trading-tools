import logging

import httpx

from app.core import cache
from app.core.config import settings

log = logging.getLogger("ffxivcollect")

# Endpoint per catalogue kind. Cache file name == kind (cache/{kind}.json).
KIND_ENDPOINT = {"mounts": "/mounts", "minions": "/minions"}


class FFXIVCollectClient:
    """Fetches the mount / minion catalogue from ffxivcollect.com.

    Each record already carries the summoning ``item_id`` and a precomputed
    ``tradeable`` flag — so the market pages just join on ``item_id`` instead
    of guessing from item names (mount items reuse generic names like
    "X Whistle"; minion items mirror the minion name).

    The catalogue only changes on game patches (every few months), so results
    are cached to ``cache/{kind}.json`` and reused until a forced refresh.
    Run ``scripts/fetch_collectibles.py`` after a major patch.
    """

    async def _fetch(self, kind: str) -> list[dict]:
        base = settings.FFXIVCOLLECT_BASE.rstrip("/")
        endpoint = KIND_ENDPOINT[kind]
        # ffxivcollect rejects the default urllib UA; any app UA is accepted.
        async with httpx.AsyncClient(
            headers={"User-Agent": settings.USER_AGENT},
            timeout=30.0,
        ) as client:
            r = await client.get(
                f"{base}{endpoint}",
                params={"language": "en", "limit": 5000},
            )
            r.raise_for_status()
            data = r.json()
        out: list[dict] = []
        for rec in data.get("results", []):
            iid = rec.get("item_id")
            out.append({
                "id": rec.get("id"),
                "name": rec.get("name") or "",
                "item_id": int(iid) if iid else None,
                # tradeable == the summoning item can be bought/sold on the market board
                "tradeable": bool(rec.get("tradeable")),
                "sources": [
                    {"type": s.get("type") or "", "text": s.get("text") or ""}
                    for s in (rec.get("sources") or [])
                ],
            })
        return out

    async def populate(self, kind: str, *, force: bool = False) -> list[dict]:
        if kind not in KIND_ENDPOINT:
            raise ValueError(f"unknown collectible kind {kind!r}")
        if not force and cache.exists(kind):
            log.info("cache hit %s", kind)
            return cache.read(kind) or []
        log.info("populating %s from FFXIVCollect", kind)
        rows = await self._fetch(kind)
        cache.write(kind, rows)
        tradeable = sum(1 for r in rows if r["tradeable"])
        log.info("%s cached n=%d tradeable=%d", kind, len(rows), tradeable)
        return rows

    async def populate_mounts(self, *, force: bool = False) -> list[dict]:
        return await self.populate("mounts", force=force)

    async def populate_minions(self, *, force: bool = False) -> list[dict]:
        return await self.populate("minions", force=force)
