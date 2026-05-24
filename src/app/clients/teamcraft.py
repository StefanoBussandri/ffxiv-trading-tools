import logging

import httpx

from app.core import cache
from app.core.config import settings

log = logging.getLogger("teamcraft")


class TeamcraftClient:
    """Downloads the item ID -> name map from the ffxiv-teamcraft repo.

    items.json (~9.5 MB) maps every item ID to its localized names. It is a
    static datamining dump that only changes on game patches, so it is cached
    verbatim to ``cache/items.json`` and reused until a forced refresh.
    ``_load_items()`` in services/opportunities.py reads that file.
    """

    async def populate_items(self, *, force: bool = False) -> None:
        path = cache.cache_path("items")
        if not force and path.exists():
            log.info("cache hit items")
            return
        log.info("downloading items.json from %s", settings.TEAMCRAFT_ITEMS_URL)
        async with httpx.AsyncClient(
            headers={"User-Agent": settings.USER_AGENT},
            timeout=60.0,
            follow_redirects=True,
        ) as client:
            r = await client.get(settings.TEAMCRAFT_ITEMS_URL)
            r.raise_for_status()
            data = r.content
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        log.info("items.json cached bytes=%d", len(data))
