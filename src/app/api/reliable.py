from fastapi import APIRouter, Query

from app.services.reliable import compute_reliable

router = APIRouter(prefix="/api/reliable", tags=["reliable"])

VALID_SOURCES = {"all", "cross-world", "vendor"}
VALID_CONFIDENCE = {"high", "medium", "all"}


def _resolve_sources(source: str) -> list[str]:
    if source == "all":
        return ["cross-world", "vendor"]
    return [source]


@router.get("")
async def get_reliable(
    days: int | None = Query(None, ge=1, le=90),
    source: str = Query("all"),
    quality: str = Query("both"),
    confidence: str = Query("high"),
    top: int = Query(50, ge=1, le=200),
    budget: int | None = Query(None),
    commodity: bool = Query(False),
    stale_only: bool = Query(False),
    bargain_only: bool = Query(False),
) -> dict:
    if source not in VALID_SOURCES:
        source = "all"
    if confidence not in VALID_CONFIDENCE:
        confidence = "high"
    return await compute_reliable(
        days=days,
        sources=_resolve_sources(source),
        quality=quality,
        confidence=confidence,
        top=top,
        budget=budget,
        include_series=True,
        commodity=commodity,
        stale_only=stale_only,
        bargain_only=bargain_only,
    )


@router.get("/watchlist")
async def get_watchlist(top: int = Query(5, ge=1, le=20)) -> dict:
    return await compute_reliable(
        sources=["cross-world", "vendor"],
        quality="both",
        confidence="high",
        top=top,
        include_series=False,
    )
