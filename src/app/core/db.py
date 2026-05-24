import aiosqlite

from app.core.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS favourites (
  item_id INTEGER NOT NULL,
  quality TEXT NOT NULL CHECK (quality IN ('hq','nq')),
  added_at INTEGER NOT NULL,
  buy_target INTEGER,
  buy_dir TEXT,
  sell_target INTEGER,
  sell_dir TEXT,
  PRIMARY KEY (item_id, quality)
);

CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY,
  observed_at INTEGER NOT NULL,
  item_id INTEGER NOT NULL,
  quality TEXT NOT NULL,
  buy_world TEXT,
  buy_price INTEGER,
  sell_world TEXT,
  sell_price INTEGER,
  profit INTEGER,
  roi_pct REAL,
  velocity REAL,
  source TEXT,
  median_listing INTEGER,
  avg_sale_price REAL,
  recent_purchase_price INTEGER,
  recent_purchase_ts INTEGER,
  spread_pct REAL
);

CREATE INDEX IF NOT EXISTS idx_history_item ON history(item_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_history_source_time ON history(source, observed_at);

-- Only the most recent run per source is kept (UPSERT on source).
CREATE TABLE IF NOT EXISTS scan_runs (
  source TEXT PRIMARY KEY,
  started_at INTEGER NOT NULL,
  finished_at INTEGER NOT NULL,
  items_scanned INTEGER,
  items_profitable INTEGER,
  duration_ms INTEGER
);

-- Game/server settings (home world, thresholds, ...). Edited via the in-app
-- Settings panel; overrides the pydantic/.env defaults. See core/config.py.
CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- Client UI preferences (column layouts, sort state, filters, display prefs).
-- Replaces browser localStorage so prefs are server-side. value = JSON string.
CREATE TABLE IF NOT EXISTS ui_prefs (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


HISTORY_NEW_COLUMNS = [
    ("median_listing", "INTEGER"),
    ("avg_sale_price", "REAL"),
    ("recent_purchase_price", "INTEGER"),
    ("recent_purchase_ts", "INTEGER"),
    ("spread_pct", "REAL"),
]


async def _migrate_history(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(history)")
    existing = {row[1] for row in await cur.fetchall()}
    for name, decl in HISTORY_NEW_COLUMNS:
        if name not in existing:
            await db.execute(f"ALTER TABLE history ADD COLUMN {name} {decl}")


async def _migrate_scan_runs(db: aiosqlite.Connection) -> None:
    """Old scan_runs kept every run (id PRIMARY KEY). New schema keeps only the
    latest per source — drop the old table so executescript recreates it."""
    cur = await db.execute("PRAGMA table_info(scan_runs)")
    cols = {row[1] for row in await cur.fetchall()}
    if "id" in cols:
        await db.execute("DROP TABLE scan_runs")


async def _migrate_favourites_table(db: aiosqlite.Connection) -> None:
    """Old installs have a US-spelled 'favorites' table — rename it so existing
    rows carry over before executescript would create an empty 'favourites'."""
    cur = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name IN ('favorites', 'favourites')"
    )
    names = {row[0] for row in await cur.fetchall()}
    if "favorites" in names and "favourites" not in names:
        await db.execute("ALTER TABLE favorites RENAME TO favourites")


async def _migrate_favourite_alerts(db: aiosqlite.Connection) -> None:
    """Add the price-alert columns to an existing favourites table."""
    cur = await db.execute("PRAGMA table_info(favourites)")
    cols = {row[1] for row in await cur.fetchall()}
    for name, decl in (
        ("buy_target", "INTEGER"), ("buy_dir", "TEXT"),
        ("sell_target", "INTEGER"), ("sell_dir", "TEXT"),
    ):
        if name not in cols:
            await db.execute(f"ALTER TABLE favourites ADD COLUMN {name} {decl}")


async def init_db() -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await _migrate_scan_runs(db)
        await _migrate_favourites_table(db)
        await db.executescript(SCHEMA)
        await _migrate_history(db)
        await _migrate_favourite_alerts(db)
        await db.commit()


async def connect() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(settings.db_path)
    await conn.execute("PRAGMA busy_timeout=5000")
    return conn
