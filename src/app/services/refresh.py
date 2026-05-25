import asyncio
import logging
import time

from app.clients.ffxivcollect import FFXIVCollectClient
from app.clients.teamcraft import TeamcraftClient
from app.clients.universalis import UniversalisClient, active_batch
from app.clients.xivapi import XIVAPIClient
from app.core.config import settings

log = logging.getLogger("refresh")

VALID_RESOURCES = {
    "worlds", "tax", "vendors", "data_centers", "marketable",
    "icons", "maps", "collectibles", "items", "scans", "all",
}

# rescan state for UI countdown
_last_rescan_ts: float = 0.0
_rescan_in_progress: bool = False
# Set by trigger_manual_rescan() so the auto-rescan loop can short-circuit its
# current sleep and reschedule from the new _last_rescan_ts.
_rescan_wake: asyncio.Event | None = None


def _wake_event() -> asyncio.Event:
    global _rescan_wake
    if _rescan_wake is None:
        _rescan_wake = asyncio.Event()
    return _rescan_wake

# Background bootstrap progress — surfaced via GET /api/startup/status so the
# setup screen and topbar pill can show heavy data loading after the fast
# start. steps: step -> "pending" | "done" | "failed".
_bootstrap: dict = {
    "ready": False,
    "steps": {
        "items": "pending", "vendors": "pending", "maps": "pending",
        "mounts": "pending", "minions": "pending", "icons": "pending",
    },
    "error": None,
}


def bootstrap_status() -> dict:
    return {
        "ready": _bootstrap["ready"],
        "steps": dict(_bootstrap["steps"]),
        "error": _bootstrap["error"],
    }


def rescan_status() -> dict:
    now = time.time()
    interval = settings.AUTO_RESCAN_SECONDS
    next_at = (_last_rescan_ts + interval) if (interval > 0 and _last_rescan_ts > 0) else 0
    return {
        "interval_seconds": interval,
        "last_rescan_ts": int(_last_rescan_ts * 1000) if _last_rescan_ts else 0,
        "next_rescan_ts": int(next_at * 1000) if next_at else 0,
        "seconds_until_next": max(0, int(next_at - now)) if next_at else None,
        "in_progress": _rescan_in_progress,
        "scan_progress": active_batch() if _rescan_in_progress else None,
        "enabled": interval > 0,
    }


async def _initial_scans_background() -> None:
    global _last_rescan_ts, _rescan_in_progress
    from app.services.opportunities import scan_cross_world, scan_vendor
    try:
        _rescan_in_progress = True
        log.info("starting initial cross-world scan (background)")
        await scan_cross_world()
        log.info("starting initial vendor scan (background)")
        await scan_vendor()
        _last_rescan_ts = time.time()
        _rescan_in_progress = False
        log.info("initial scans complete")
    except Exception as e:
        _rescan_in_progress = False
        log.warning("initial scan failed: %s", e)


async def _auto_rescan_loop() -> None:
    global _last_rescan_ts, _rescan_in_progress
    from app.services.history import get_last_scan_finished
    from app.services.opportunities import scan_cross_world, scan_vendor
    interval = settings.AUTO_RESCAN_SECONDS
    if interval <= 0:
        log.info("auto-rescan disabled (AUTO_RESCAN_SECONDS=0)")
        return
    # Seed the countdown from the last persisted scan so it survives a restart.
    last_finished = await get_last_scan_finished()
    _last_rescan_ts = float(last_finished) if last_finished else time.time()
    log.info("auto-rescan loop started — interval=%ds", interval)
    wake = _wake_event()
    while True:
        try:
            # Sleep until the interval since the last scan elapses, OR until a
            # manual rescan wakes us — in which case the new _last_rescan_ts
            # already advanced and we re-enter the wait with a fresh budget.
            remaining = interval - (time.time() - _last_rescan_ts)
            if remaining > 0:
                try:
                    await asyncio.wait_for(wake.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    pass
                else:
                    wake.clear()
                    continue  # manual scan handled it; recompute the budget
            log.info("auto-rescan firing")
            _rescan_in_progress = True
            await scan_cross_world(force=True)
            await scan_vendor(force=True)
            _last_rescan_ts = time.time()
            _rescan_in_progress = False
            log.info("auto-rescan cycle complete")
        except asyncio.CancelledError:
            log.info("auto-rescan loop cancelled")
            raise
        except Exception as e:
            _rescan_in_progress = False
            log.warning("auto-rescan iteration failed: %s", e)


async def trigger_manual_rescan() -> None:
    """Run cross-world + vendor scans, then wake the auto-rescan loop so it
    rebases its countdown from now. Safe to spawn as a background task."""
    global _last_rescan_ts, _rescan_in_progress
    if _rescan_in_progress:
        log.info("manual rescan ignored — scan already in progress")
        return
    from app.services.opportunities import scan_cross_world, scan_vendor
    _rescan_in_progress = True
    try:
        log.info("manual rescan firing")
        await scan_cross_world(force=True)
        await scan_vendor(force=True)
        _last_rescan_ts = time.time()
        log.info("manual rescan complete")
    except Exception as e:
        log.warning("manual rescan failed: %s", e)
    finally:
        _rescan_in_progress = False
        _wake_event().set()


async def _background_bootstrap() -> None:
    """Sequentially load the heavy caches behind the live-reachable server.

    Each step is independent — a failure is logged and recorded as "failed"
    without aborting the rest. ``ready`` flips true once all data steps finish;
    the initial scans and the auto-rescan loop follow.
    """
    x = XIVAPIClient()
    fc = FFXIVCollectClient()
    steps = (
        ("items", TeamcraftClient().populate_items),
        ("vendors", x.populate_vendor_items),
        ("maps", x.populate_maps),
        ("mounts", fc.populate_mounts),
        ("minions", fc.populate_minions),
        ("icons", x.populate_item_icons),
    )
    for name, fn in steps:
        try:
            log.info("bootstrap step %s starting", name)
            await fn()
            _bootstrap["steps"][name] = "done"
            log.info("bootstrap step %s done", name)
        except Exception as e:
            _bootstrap["steps"][name] = "failed"
            log.warning("bootstrap step %s failed: %s", name, e)
    _bootstrap["ready"] = True
    log.info("background bootstrap complete — all data steps done")
    await _initial_scans_background()
    await _auto_rescan_loop()


async def populate_initial_cache() -> None:
    """Blocking phase: fetch only what the setup screen and core scans need
    (~2-5s), then spawn the heavy data load in the background so the server is
    reachable immediately."""
    try:
        u = UniversalisClient()
        await u.get_data_centers()
        await u.get_worlds()
        await u.get_marketable()
        await u.get_tax_rates(settings.HOME_WORLD)
    except Exception as e:
        _bootstrap["error"] = "Couldn't reach game data services — check your connection"
        log.error("initial cache blocking phase failed: %s", e)
        return
    asyncio.create_task(_background_bootstrap())


async def refresh_resource(resource: str) -> dict:
    if resource not in VALID_RESOURCES:
        return {"ok": False, "error": f"unknown resource {resource!r}"}
    u = UniversalisClient()
    refreshed: list[str] = []
    if resource in ("worlds", "data_centers", "all"):
        await u.get_data_centers(refresh=True)
        refreshed.append("data_centers")
        await u.get_worlds(refresh=True)
        refreshed.append("worlds")
    if resource in ("marketable", "all"):
        await u.get_marketable(refresh=True)
        refreshed.append("marketable")
    if resource in ("tax", "all"):
        await u.get_tax_rates(settings.HOME_WORLD, refresh=True)
        refreshed.append("tax_rates")
    if resource in ("vendors", "all"):
        x = XIVAPIClient()
        await x.populate_vendor_items(force=True)
        refreshed.append("vendor_items")
    if resource in ("icons", "all"):
        x = XIVAPIClient()
        await x.populate_item_icons(force=True)
        refreshed.append("item_icons")
    # Catalogues below change only on game patches — kept out of "all" (which
    # fires on every topbar rescan); refresh explicitly per resource.
    if resource == "maps":
        x = XIVAPIClient()
        await x.populate_maps(force=True)
        refreshed.append("maps")
    if resource == "collectibles":
        fc = FFXIVCollectClient()
        await fc.populate_mounts(force=True)
        await fc.populate_minions(force=True)
        refreshed.extend(["mounts", "minions"])
    if resource == "items":
        await TeamcraftClient().populate_items(force=True)
        refreshed.append("items")
    return {"ok": True, "refreshed": refreshed}
