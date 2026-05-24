import time

import aiosqlite

from app.core.config import settings


async def list_favourites() -> list[dict]:
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT item_id, quality, added_at, buy_target, buy_dir, "
            "sell_target, sell_dir FROM favourites ORDER BY added_at DESC"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def set_favourite_alert(
    item_id: int, quality: str,
    buy_target: int | None, buy_dir: str | None,
    sell_target: int | None, sell_dir: str | None,
) -> bool:
    """Store buy/sell price-alert thresholds on a favourite."""
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        cur = await db.execute(
            "UPDATE favourites SET buy_target=?, buy_dir=?, sell_target=?, sell_dir=? "
            "WHERE item_id=? AND quality=?",
            (buy_target, buy_dir, sell_target, sell_dir, item_id, quality),
        )
        await db.commit()
        return (cur.rowcount or 0) > 0


async def add_favourite(item_id: int, quality: str) -> None:
    if quality not in ("hq", "nq"):
        raise ValueError("quality must be 'hq' or 'nq'")
    now = int(time.time())
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute(
            "INSERT OR IGNORE INTO favourites (item_id, quality, added_at) VALUES (?, ?, ?)",
            (item_id, quality, now),
        )
        await db.commit()


async def remove_favourite(item_id: int, quality: str) -> bool:
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        cur = await db.execute(
            "DELETE FROM favourites WHERE item_id = ? AND quality = ?",
            (item_id, quality),
        )
        await db.commit()
        return (cur.rowcount or 0) > 0
