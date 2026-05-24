import logging
import time

import aiosqlite

from app.core.config import settings

log = logging.getLogger("history")


async def record_opportunities(rows: list[dict], source: str) -> int:
    if not rows:
        return 0
    now = int(time.time())
    payload = [
        (
            now,
            r["itemId"],
            r["quality"],
            r["buy_world"],
            r["buy_price"],
            r["sell_world"],
            r["sell_price"],
            r["profit"],
            r["roi_pct"],
            r["velocity"],
            source,
            r.get("median_listing"),
            r.get("avg_sale_price"),
            r.get("recent_purchase_price"),
            r.get("recent_purchase_ts"),
            r.get("spread_pct"),
        )
        for r in rows
    ]
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        await db.executemany(
            """
            INSERT INTO history
              (observed_at, item_id, quality, buy_world, buy_price,
               sell_world, sell_price, profit, roi_pct, velocity, source,
               median_listing, avg_sale_price, recent_purchase_price,
               recent_purchase_ts, spread_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        await db.commit()
    log.info("history recorded n=%d source=%s", len(payload), source)
    return len(payload)


async def record_scan_run(
    source: str,
    started_at: int,
    finished_at: int,
    items_scanned: int,
    items_profitable: int,
) -> None:
    """Store only the latest run per source (UPSERT on source)."""
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute(
            """
            INSERT INTO scan_runs
              (source, started_at, finished_at, items_scanned, items_profitable, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
              started_at=excluded.started_at,
              finished_at=excluded.finished_at,
              items_scanned=excluded.items_scanned,
              items_profitable=excluded.items_profitable,
              duration_ms=excluded.duration_ms
            """,
            (source, started_at, finished_at, items_scanned, items_profitable,
             (finished_at - started_at) * 1000),
        )
        await db.commit()


async def get_last_scan_finished() -> int | None:
    """Unix-seconds timestamp of the most recent scan across sources, if any."""
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        cur = await db.execute("SELECT MAX(finished_at) FROM scan_runs")
        row = await cur.fetchone()
    return int(row[0]) if row and row[0] else None


async def trim_old(retention_days: int) -> int:
    cutoff = int(time.time()) - retention_days * 86400
    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        cur = await db.execute("DELETE FROM history WHERE observed_at < ?", (cutoff,))
        await db.commit()
        return cur.rowcount or 0


METRIC_COLUMN = {
    "profit": "avg_profit",
    "profit_per_day": "avg_profit_per_day",
    "roi_pct": "avg_roi_pct",
    "velocity": "avg_velocity",
    "appearances": "appearances",
}


async def top_history(
    *,
    days: int,
    metric: str,
    source: str = "all",
    limit: int = 100,
) -> list[dict]:
    cutoff = int(time.time()) - days * 86400
    metric_col = METRIC_COLUMN.get(metric, "avg_profit_per_day")

    sql = """
    SELECT
      item_id,
      quality,
      source,
      COUNT(*) AS appearances,
      AVG(profit) AS avg_profit,
      AVG(roi_pct) AS avg_roi_pct,
      AVG(velocity) AS avg_velocity,
      AVG(profit * velocity) AS avg_profit_per_day,
      MAX(observed_at) AS last_seen
    FROM history
    WHERE observed_at >= ?
    """
    params: list = [cutoff]
    if source != "all":
        sql += " AND source = ?"
        params.append(source)
    sql += f" GROUP BY item_id, quality, source ORDER BY {metric_col} DESC LIMIT ?"
    params.append(limit)

    async with aiosqlite.connect(settings.db_path, timeout=10.0) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
