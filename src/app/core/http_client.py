import httpx

from app.core.config import settings
from app.core.rate_limit import RateLimitedClient, RateLimiter

_universalis: RateLimitedClient | None = None
_xivapi: RateLimitedClient | None = None
_clients: list[httpx.AsyncClient] = []


def _make_client(max_conn: int) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        limits=httpx.Limits(max_connections=max_conn, max_keepalive_connections=max_conn),
        headers={"User-Agent": settings.USER_AGENT},
        timeout=30.0,
    )


async def init_http_client() -> None:
    global _universalis, _xivapi
    uni_http = _make_client(settings.UNIVERSALIS_MAX_CONCURRENT)
    xiv_http = _make_client(settings.XIVAPI_MAX_CONCURRENT)
    _clients.extend([uni_http, xiv_http])
    _universalis = RateLimitedClient(
        uni_http,
        RateLimiter(
            rate=settings.UNIVERSALIS_RATE_PER_SEC,
            capacity=settings.UNIVERSALIS_RATE_PER_SEC,
            max_concurrent=settings.UNIVERSALIS_MAX_CONCURRENT,
            name="universalis",
        ),
    )
    _xivapi = RateLimitedClient(
        xiv_http,
        RateLimiter(
            rate=settings.XIVAPI_RATE_PER_SEC,
            capacity=settings.XIVAPI_RATE_PER_SEC,
            max_concurrent=settings.XIVAPI_MAX_CONCURRENT,
            name="xivapi",
        ),
    )


async def close_http_client() -> None:
    global _universalis, _xivapi
    for c in _clients:
        await c.aclose()
    _clients.clear()
    _universalis = None
    _xivapi = None


def universalis_client() -> RateLimitedClient:
    if _universalis is None:
        raise RuntimeError("universalis client not initialized")
    return _universalis


def xivapi_client() -> RateLimitedClient:
    if _xivapi is None:
        raise RuntimeError("xivapi client not initialized")
    return _xivapi
