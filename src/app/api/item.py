"""Per-item detail — live listings + sale history for the item detail panel."""
import time

from fastapi import APIRouter, Query

from app.clients.universalis import UniversalisClient
from app.core.config import settings
from app.services.opportunities import _load_items

router = APIRouter(prefix="/api/item", tags=["item"])


def _unwrap(payload: dict, item_id: int) -> dict:
    """Universalis returns a bare item object for a single ID, or an `items`
    map for multiple — normalise to the single item object."""
    if isinstance(payload, dict) and "items" in payload:
        items = payload.get("items") or {}
        return items.get(str(item_id)) or items.get(item_id) or {}
    return payload or {}


@router.get("/{item_id}")
async def get_item(item_id: int, quality: str = Query("nq")) -> dict:
    is_hq = quality == "hq"
    u = UniversalisClient()
    scope = settings.DATA_CENTER

    shown = _unwrap(
        await u.get_currently_shown(scope, [item_id], listings=100, fields=None),
        item_id,
    )
    hist = _unwrap(
        await u.get_history(scope, [item_id], entries_to_return=200),
        item_id,
    )

    listings = []
    for ln in (shown.get("listings") or []):
        if bool(ln.get("hq")) != is_hq:
            continue
        listings.append({
            "world": ln.get("worldName"),
            "price": int(ln.get("pricePerUnit") or 0),
            "quantity": int(ln.get("quantity") or 0),
            "hq": bool(ln.get("hq")),
        })
    listings.sort(key=lambda x: x["price"])

    history = []
    for e in (hist.get("entries") or []):
        if bool(e.get("hq")) != is_hq:
            continue
        history.append({
            "ts": int(e.get("timestamp") or 0),
            "price": int(e.get("pricePerUnit") or 0),
            "quantity": int(e.get("quantity") or 0),
            "world": e.get("worldName"),
        })
    history.sort(key=lambda x: x["ts"])

    items_by_id = _load_items()
    return {
        "item_id": item_id,
        "name": items_by_id.get(item_id, str(item_id)),
        "quality": "hq" if is_hq else "nq",
        "home_world": settings.HOME_WORLD,
        "listings": listings,
        "home_listings": [ln for ln in listings if ln["world"] == settings.HOME_WORLD],
        "history": history,
        "ts": int(time.time() * 1000),
    }
