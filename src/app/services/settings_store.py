"""DB-backed game settings (app_settings) and UI preferences (ui_prefs).

Game settings are persisted to data.db and hot-applied to the in-memory
`settings` object so changes take effect without a restart. UI prefs replace
browser localStorage — column layouts, sort state, filters, display prefs.
"""
import logging

import aiosqlite

from app.core.config import GAME_SETTING_KEYS, coerce_setting, settings

log = logging.getLogger("settings_store")


async def set_game_settings(updates: dict) -> list[str]:
    """Persist game settings to app_settings and hot-apply to `settings`."""
    pending: list[tuple[str, str]] = [
        (k, str(v))
        for k, v in updates.items()
        if k in GAME_SETTING_KEYS and v is not None and v != ""
    ]
    if not pending:
        return []
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        await db.executemany(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            pending,
        )
        await db.commit()
    applied: list[str] = []
    for k, raw in pending:
        if not hasattr(settings, k):
            continue
        try:
            object.__setattr__(settings, k, coerce_setting(getattr(settings, k), raw))
            applied.append(k)
        except Exception as e:
            log.warning("hot-apply failed for %s=%s: %s", k, raw, e)
    log.info("game settings updated: %s", applied)
    return applied


async def is_configured() -> bool:
    """First-run check — app_settings gains rows only once setup has run."""
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        cur = await db.execute("SELECT COUNT(*) FROM app_settings")
        row = await cur.fetchone()
        return bool(row and row[0] > 0)


async def get_ui_prefs() -> dict[str, str]:
    """All UI prefs as {key: raw-JSON-string} — mirrors the old localStorage."""
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        cur = await db.execute("SELECT key, value FROM ui_prefs")
        return {k: v for k, v in await cur.fetchall()}


async def set_ui_pref(key: str, value: str) -> None:
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute(
            "INSERT INTO ui_prefs (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()
