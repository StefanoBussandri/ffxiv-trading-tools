from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.core import cache
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["icons"])


@router.get("/icon/{item_id}")
async def get_icon(item_id: int) -> RedirectResponse:
    icons = cache.read("item_icons") or {}
    path = icons.get(str(item_id))
    if not path:
        raise HTTPException(status_code=404, detail="icon not found")
    base = settings.XIVAPI_BASE.rstrip("/")
    # Icon mappings change only on game patches — let the browser cache the
    # redirect so re-rendering the table (e.g. on sort) doesn't refetch icons.
    return RedirectResponse(
        f"{base}/asset?path={path}&format=png",
        status_code=302,
        headers={"Cache-Control": "public, max-age=604800"},
    )
