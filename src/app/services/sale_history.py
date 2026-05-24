import asyncio
import logging
import time
from typing import Any

from app.clients.universalis import UniversalisClient, begin_batch, end_batch
from app.core.config import settings

log = logging.getLogger("sale_history")

CHUNK = 100
_pool: dict[int, dict] = {}
_pool_ts: float = 0.0
_pool_scope: str | None = None
_pool_window: int | None = None
DEFAULT_TTL = 3600  # 1h


async def fetch(
    item_ids: list[int],
    *,
    scope: str | None = None,
    window_days: int | None = None,
    reset: bool = False,
    ttl: int = DEFAULT_TTL,
) -> dict[int, dict]:
    global _pool_ts, _pool_scope, _pool_window
    use_scope = scope or settings.HOME_WORLD
    use_window = window_days or settings.RELIABLE_WINDOW_DAYS
    # Invalidate if scope/window changed
    if _pool_scope != use_scope or _pool_window != use_window:
        _pool.clear()
        _pool_scope = use_scope
        _pool_window = use_window
    if reset or (time.time() - _pool_ts > ttl):
        _pool.clear()
    needed = [int(i) for i in item_ids if int(i) not in _pool]
    if needed:
        u = UniversalisClient()
        chunks = [needed[i:i + CHUNK] for i in range(0, len(needed), CHUNK)]
        log.info(
            "history fetching %d items (%d chunks); pool hits=%d scope=%s window=%dd",
            len(needed), len(chunks), len(item_ids) - len(needed), use_scope, use_window,
        )
        begin_batch("history", len(needed))
        try:
            results = await asyncio.gather(
                *(u.get_history(use_scope, c, entries_within=use_window * 86400, entries_to_return=2000)
                  for c in chunks),
                return_exceptions=True,
            )
        finally:
            end_batch("history")
        for res in results:
            if isinstance(res, Exception):
                log.warning("history chunk failed: %s", res)
                continue
            items = res.get("items") if isinstance(res, dict) else None
            if items:
                for iid, v in items.items():
                    _pool[int(iid)] = v
            elif isinstance(res, dict) and "entries" in res:
                # single-item response shape
                iid = res.get("itemID")
                if iid is not None:
                    _pool[int(iid)] = res
        _pool_ts = time.time()
    else:
        log.info("history pool full hit for %d items", len(item_ids))
    return {int(i): _pool[int(i)] for i in item_ids if int(i) in _pool}


def reset_pool() -> None:
    global _pool_ts
    _pool.clear()
    _pool_ts = 0.0
