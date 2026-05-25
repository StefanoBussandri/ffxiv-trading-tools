import logging
import os
import shutil
import threading
import webbrowser
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def _bootstrap_env() -> None:
    """If .env is missing, seed it from the shipped .env.example.

    Writes to REPO_ROOT (exe folder when frozen, source tree otherwise).
    Reads from BUNDLE_ROOT, which is the PyInstaller _MEIPASS dir at runtime
    or the source tree in dev — keeps the shipped template read-only.
    """
    from app.core.config import BUNDLE_ROOT, REPO_ROOT
    env_path = REPO_ROOT / ".env"
    example_path = BUNDLE_ROOT / ".env.example"
    if not env_path.exists() and example_path.exists():
        shutil.copyfile(example_path, env_path)
        logging.getLogger("app").info(".env created from .env.example")


_bootstrap_env()

from app.api import collectibles, dashboard, favourites, history, icons, item, maps, opportunities, prefs, refresh, reliable, settings_api, tax  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import init_db  # noqa: E402
from app.core.http_client import close_http_client, init_http_client  # noqa: E402
from app.services.history import trim_old  # noqa: E402
from app.services.refresh import populate_initial_cache  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
# Quiet noisy httpx URL logs; our universalis client emits structured logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("db initialized at %s", settings.db_path)
    await init_http_client()
    log.info(
        "http clients initialized — universalis=%s/s,%dc xivapi=%s/s,%dc",
        settings.UNIVERSALIS_RATE_PER_SEC,
        settings.UNIVERSALIS_MAX_CONCURRENT,
        settings.XIVAPI_RATE_PER_SEC,
        settings.XIVAPI_MAX_CONCURRENT,
    )
    await populate_initial_cache()
    trimmed = await trim_old(settings.HISTORY_RETENTION_DAYS)
    if trimmed:
        log.info("history trimmed %d rows older than %dd", trimmed, settings.HISTORY_RETENTION_DAYS)
    url = "http://localhost:8000/"
    log.info("startup complete — open %s", url)
    if os.environ.get("FFXIV_TRADER_NO_BROWSER", "").lower() not in ("1", "true", "yes"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        yield
    finally:
        await close_http_client()
        log.info("http client closed")


app = FastAPI(title="ffxiv-trader", lifespan=lifespan)

app.include_router(tax.router)
app.include_router(refresh.router)
app.include_router(opportunities.router)
app.include_router(favourites.router)
app.include_router(history.router)
app.include_router(icons.router)
app.include_router(maps.router)
app.include_router(item.router)
app.include_router(collectibles.router)
app.include_router(dashboard.router)
app.include_router(reliable.router)
app.include_router(settings_api.router)
app.include_router(settings_api.setup_router)
app.include_router(prefs.router)

app.mount("/css", StaticFiles(directory=settings.static_dir / "css"), name="css")
app.mount("/js", StaticFiles(directory=settings.static_dir / "js"), name="js")
app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")
