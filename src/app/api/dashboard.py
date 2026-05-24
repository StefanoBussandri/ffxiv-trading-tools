import time

from fastapi import APIRouter, Query

from app.clients.universalis import UniversalisClient
from app.core.config import settings
from app.services.favourites import list_favourites
from app.services.maps import scan_maps
from app.services.opportunities import scan_cross_world, scan_vendor

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _top(rows: list[dict], n: int) -> list[dict]:
    return sorted(rows, key=lambda r: r.get("profit_per_day") or 0, reverse=True)[:n]


@router.get("")
async def get_dashboard(top: int = Query(10, ge=1, le=50)) -> dict:
    cross = await scan_cross_world()
    vendor = await scan_vendor()
    maps = await scan_maps()
    favs = await list_favourites()

    rates = await UniversalisClient().get_tax_rates(settings.HOME_WORLD)
    return {
        "ts": int(time.time() * 1000),
        "home_world": settings.HOME_WORLD,
        "data_center": settings.DATA_CENTER,
        "tax_city": settings.TAX_CITY,
        "tax_rates": rates,
        "listings_ceiling": settings.listings_ceiling,
        "stats": {
            "cross_world_total": len(cross),
            "vendor_total": len(vendor),
            "favourites_total": len(favs),
            "maps_total": len(maps),
        },
        "top_cross_world": _top(cross, top),
        "top_vendor": _top(vendor, top),
        "maps": maps,
        "favourites_count": len(favs),
    }
