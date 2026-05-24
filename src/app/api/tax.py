from fastapi import APIRouter

from app.clients.universalis import UniversalisClient
from app.core import cache
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["tax"])


@router.get("/tax-rates")
async def get_tax_rates() -> dict:
    rates = await UniversalisClient().get_tax_rates(settings.HOME_WORLD)
    min_pct = min(rates.values()) if rates else None
    cheapest_cities = [c for c, v in rates.items() if v == min_pct] if rates else []
    return {
        "rates": rates,
        "retainer_city": settings.TAX_CITY,
        "home_world": settings.HOME_WORLD,
        "cheapest_cities": cheapest_cities,
        "fetched_at": cache.mtime_ms("tax_rates"),
    }

