"""UI preferences — server-side store replacing browser localStorage."""
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.services.settings_store import get_ui_prefs, set_ui_pref

router = APIRouter(prefix="/api/ui-prefs", tags=["prefs"])


@router.get("")
async def get_prefs() -> dict[str, str]:
    """All UI prefs as {key: raw-JSON-string}."""
    return await get_ui_prefs()


@router.put("")
async def put_pref(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    key = payload.get("key")
    value = payload.get("value")
    if not isinstance(key, str) or not isinstance(value, str):
        raise HTTPException(status_code=422, detail="key and value (strings) required")
    await set_ui_pref(key, value)
    return {"ok": True}
