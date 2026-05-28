import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


def _app_root() -> Path:
    """Writable root: dev tree in source mode, %LOCALAPPDATA%/FFXIVTrader
    when frozen.

    PyInstaller sets sys.frozen. We deliberately do NOT use the exe folder
    in frozen mode: a friend who drops the build under "Program Files" (or
    anywhere else UAC-protected) would crash on first DB write. LocalAppData
    is per-user, always writable, survives reinstalls, and is the standard
    Windows spot for app state. The dir is created on import so callers can
    assume it exists.
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            root = Path(base) / "FFXIVTrader"
        else:
            # Fallback for non-Windows frozen builds / weird envs.
            root = Path(sys.executable).resolve().parent
        root.mkdir(parents=True, exist_ok=True)
        return root
    return Path(__file__).resolve().parents[3]


def _bundle_root() -> Path:
    """Read-only bundle root for shipped assets (static/, .env.example).

    PyInstaller unpacks bundled data into sys._MEIPASS at runtime; in dev
    the same files live in the source tree.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


REPO_ROOT = _app_root()
BUNDLE_ROOT = _bundle_root()
LOG_DIR = REPO_ROOT / "logs"
LOG_PATH = LOG_DIR / "app.log"

# Mutable game/player settings — stored in data.db (app_settings table) and
# edited via the in-app Settings panel. .env holds only infra (API URLs, rate
# limits). These names must exist as fields on Settings below.
GAME_SETTING_KEYS = (
    "HOME_WORLD", "DATA_CENTER", "TAX_CITY",
    "RETAINER_COUNT", "RETAINER_MARKET_SLOTS",
    "LISTING_FRESHNESS_HOURS", "MIN_PROFIT_GIL", "MIN_ROI_PCT", "MAX_ROI_PCT",
    "MIN_SALES_PER_DAY", "AUTO_RESCAN_SECONDS", "MIN_RELIABLE_PROFIT_GIL",
    "RELIABLE_WINDOW_DAYS", "TARGET_VELOCITY", "HISTORY_RETENTION_DAYS",
    "STALE_DATA_HOURS",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    HOME_WORLD: str = "Odin"
    DATA_CENTER: str = "Light"
    TAX_CITY: str = "Limsa Lominsa"

    RETAINER_COUNT: int = 2
    RETAINER_MARKET_SLOTS: int = 20

    @property
    def listings_ceiling(self) -> int:
        return self.RETAINER_COUNT * self.RETAINER_MARKET_SLOTS

    UNIVERSALIS_BASE: str = "https://universalis.app/api/v2"
    XIVAPI_BASE: str = "https://v2.xivapi.com/api"
    FFXIVCOLLECT_BASE: str = "https://ffxivcollect.com/api"
    TEAMCRAFT_ITEMS_URL: str = (
        "https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft"
        "/master/libs/data/src/lib/json/items.json"
    )
    USER_AGENT: str = "ffxiv-trader/0.1 (contact: unset)"

    UNIVERSALIS_RATE_PER_SEC: float = 20.0
    UNIVERSALIS_MAX_CONCURRENT: int = 8
    XIVAPI_RATE_PER_SEC: float = 10.0
    XIVAPI_MAX_CONCURRENT: int = 4

    LISTING_FRESHNESS_HOURS: int = 24
    STALE_DATA_HOURS: int = 12
    MIN_PROFIT_GIL: int = 1000
    MIN_ROI_PCT: float = 10.0
    MAX_ROI_PCT: float = 500.0
    MIN_SALES_PER_DAY: float = 0.5

    HISTORY_RETENTION_DAYS: int = 30

    AUTO_RESCAN_SECONDS: int = 300
    MIN_RELIABLE_PROFIT_GIL: int = 5000
    RELIABLE_WINDOW_DAYS: int = 7
    TARGET_VELOCITY: float = 5.0

    @property
    def repo_root(self) -> Path:
        return REPO_ROOT

    @property
    def db_path(self) -> Path:
        return REPO_ROOT / "data.db"

    @property
    def static_dir(self) -> Path:
        return BUNDLE_ROOT / "static"

    @property
    def cache_dir(self) -> Path:
        return REPO_ROOT / "cache"


def coerce_setting(template: Any, raw: str) -> Any:
    """Coerce a string value to match the type of an existing setting."""
    if isinstance(template, bool):
        return raw.lower() in ("1", "true", "yes")
    if isinstance(template, int) and not isinstance(template, bool):
        return int(float(raw))
    if isinstance(template, float):
        return float(raw)
    return raw


def _sync_db_settings(s: "Settings") -> None:
    """Overlay game settings stored in data.db onto the settings object.

    Read-only overlay — applies whatever rows exist in app_settings. It does
    *not* seed: on a fresh install the table stays empty and the pydantic
    field defaults remain the runtime fallback (the app still runs pre-setup).
    The presence of >=1 app_settings row is the "configured" signal that
    suppresses the first-run setup screen.
    """
    try:
        conn = sqlite3.connect(REPO_ROOT / "data.db")
    except Exception:
        return
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_settings "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        rows = dict(conn.execute("SELECT key, value FROM app_settings").fetchall())
        for k, v in rows.items():
            if k in GAME_SETTING_KEYS and hasattr(s, k):
                try:
                    object.__setattr__(s, k, coerce_setting(getattr(s, k), v))
                except Exception:
                    pass
    finally:
        conn.close()


settings = Settings()
_sync_db_settings(settings)
