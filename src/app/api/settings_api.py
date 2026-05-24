"""Game settings — read from the in-memory settings object, write to data.db."""
import json
import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.core import cache
from app.core.config import GAME_SETTING_KEYS, settings
from app.services.settings_store import (
    get_ui_prefs,
    is_configured,
    set_game_settings,
    set_ui_pref,
)

log = logging.getLogger("settings_api")

# UI-pref blob where common.js FT.loadSettings() reads `budget` (and friends).
SETTINGS_PREF_KEY = "ffxiv-trader.settings.v1"

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/game")
async def get_game_settings() -> dict[str, Any]:
    return {k: getattr(settings, k) for k in GAME_SETTING_KEYS if hasattr(settings, k)}


@router.get("/options")
async def get_options() -> dict[str, list[dict[str, Any]]]:
    """Enum options for dropdown settings (worlds, DCs, tax cities)."""
    worlds_raw = cache.read("worlds") or []
    dcs_raw = cache.read("data_centers") or []
    tax_raw = cache.read("tax_rates") or {}
    worlds = sorted(
        ({"id": int(w["id"]), "name": w["name"]} for w in worlds_raw if w.get("name")),
        key=lambda w: w["name"],
    )
    data_centers = sorted(
        (
            {
                "name": dc["name"],
                "region": dc.get("region"),
                "world_ids": dc.get("worlds") or [],
            }
            for dc in dcs_raw if dc.get("name")
        ),
        key=lambda d: d["name"],
    )
    if isinstance(tax_raw, dict):
        tax_cities = [{"name": c} for c in sorted(tax_raw.keys())]
    else:
        tax_cities = []
    return {
        "worlds": worlds,
        "data_centers": data_centers,
        "tax_cities": tax_cities,
    }


@router.post("/game")
async def post_game_settings(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    updated = await set_game_settings(payload)
    return {"ok": True, "updated": updated}


# --- First-run setup — routes outside the /api/settings prefix ---
setup_router = APIRouter(prefix="/api", tags=["setup"])


@setup_router.get("/setup/status")
async def get_setup_status() -> dict[str, Any]:
    """{ configured } — true once app_settings has at least one row."""
    return {"configured": await is_configured()}


@setup_router.get("/boot")
async def get_boot() -> dict[str, Any]:
    """Single first-load call — setup status plus every UI pref."""
    return {
        "configured": await is_configured(),
        "prefs": await get_ui_prefs(),
    }


@setup_router.post("/setup")
async def post_setup(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """First-run setup — persist core game settings, then the budget UI pref."""
    missing = [k for k in ("data_center", "home_world", "tax_city") if not payload.get(k)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing fields: {', '.join(missing)}")
    await set_game_settings({
        "DATA_CENTER": payload.get("data_center"),
        "HOME_WORLD": payload.get("home_world"),
        "TAX_CITY": payload.get("tax_city"),
        "RETAINER_COUNT": payload.get("retainer_count") or 2,
    })
    budget = payload.get("budget")
    if budget is not None:
        prefs = await get_ui_prefs()
        raw = prefs.get(SETTINGS_PREF_KEY)
        try:
            obj = json.loads(raw) if raw else {}
        except Exception:
            obj = {}
        if not isinstance(obj, dict):
            obj = {}
        obj["budget"] = budget
        await set_ui_pref(SETTINGS_PREF_KEY, json.dumps(obj))
    return {"ok": True}
