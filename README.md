# ffxiv-trader

Personal-use FFXIV gil arbitrage tool. It scans Universalis market data and
surfaces cross-world flips, vendor flips, reliable trades and collectible
opportunities for your home world — all in a local web app.

## Quick start

1. Double-click **`run.bat`**.
2. Wait for your browser to open (a few seconds).
3. Fill in the setup screen — pick your data center, home world and tax city.

That's it. The first launch installs everything and downloads game data; later
launches start in seconds.

## Requirements

- Windows
- [Python 3.12+](https://www.python.org/downloads/) — install once; tick *"Add
  Python to PATH"* in the installer.
- Internet connection (needed on first run and for live prices).

## First run

- `run.bat` creates a private environment and installs dependencies — this
  takes a minute the first time only.
- The browser opens on a **setup screen**. Choose your server; that is the only
  thing you need to enter.
- Game data (vendors, maps, mounts, minions, item names, icons) downloads in
  the background for a few minutes. The pages fill in as it finishes — a
  "Preparing game data…" pill in the top bar shows progress. You can use the
  app while it loads.
- Every setting is changeable later via the **gear icon** in the top right —
  the setup screen is a one-time thing.

If `run.bat` reports that Python is missing, install it from the link above and
run `run.bat` again.

## Pages

- **Dashboard** — at-a-glance widgets across all scans.
- **Cross-world** — buy on rival worlds of your DC, sell on your home world.
- **Vendor** — items NPC vendors sell below market price.
- **Reliable** — high-confidence trades ranked by a Wilson-lower-bound score.
- **Maps** — daily-obtainable treasure maps, live prices.
- **Mounts** / **Minions** — market-tradeable collectibles.
- **Favorites** — starred items, polled live.
- **History** — items that have recurred in past scans, aggregated.

Every table page has a search box (press `/` to focus). Unquoted text is a
partial, all-words match over name + source + item ID; `"quoted text"` is an
exact phrase match on the item name.

---

## Developer notes

`.env` is **infrastructure only** (API endpoints, rate limits, user-agent).
Game and player settings — home world, tax city, retainers, scan thresholds,
auto-rescan, etc. — live in `data.db` (`app_settings` table) and are edited via
the in-app Settings panel. On a fresh install they fall back to the defaults in
`src/app/core/config.py` until the setup screen writes them.

### Stack

- **Backend:** FastAPI (Python 3.12), `uvicorn`
- **DB:** SQLite via `aiosqlite` — settings, UI prefs, favorites, history
- **HTTP:** `httpx` async, shared per-upstream rate-limited clients
- **Frontend:** static HTML/CSS/vanilla JS, served by FastAPI `StaticFiles`
- **Config:** `.env` via `pydantic-settings`
- **Package mgmt:** `uv` (with a `requirements.txt` pip mirror for the plain
  `run.bat` path)

### Run

```powershell
# uv workflow (run-uv.bat does this)
uv sync
uv run uvicorn --app-dir src app.main:app
# Server at http://localhost:8000/ — main.py auto-opens the browser.

# add --reload for dev
uv run uvicorn --app-dir src app.main:app --reload
```

`run.bat` is the plain-Python path: it creates `.venv`, installs from
`requirements.txt`, and launches the same server. `requirements.txt` is a
pinned mirror of `pyproject.toml`; `pyproject.toml` stays the source of truth
for `uv`.

### Data sources

- **Universalis** (`https://universalis.app/api/v2`) — market listings, sale
  velocity, tax rates, world/DC metadata.
- **XIVAPI v2** (`https://v2.xivapi.com/api`) — vendor (NPC shop) prices and
  names, treasure-map catalog, item icons.
- **FFXIVCollect** (`https://ffxivcollect.com/api`) — mount/minion catalog.
- **ffxiv-teamcraft** (raw GitHub) — `items.json`, the item ID → name map.

All fetched data is cached under `cache/` (git-ignored). On startup
the four quick Universalis calls block (~2-5s) so the server is reachable fast;
everything heavier loads in a background bootstrap.

### Startup

`populate_initial_cache()` runs a blocking phase (data centers, worlds,
marketable, tax) then spawns `_background_bootstrap()` for the heavy caches
(items, vendors, maps, mounts, minions, icons) followed by the initial scans
and the auto-rescan loop. `GET /api/startup/status` reports progress.

### API endpoints

```
GET    /api/boot                       setup status + all UI prefs
GET    /api/setup/status               { configured }
POST   /api/setup                      first-run game settings
GET    /api/startup/status             background-load progress
GET    /api/tax-rates
GET    /api/opportunities/cross-world?limit=&sort=&quality=&budget=&force=
GET    /api/opportunities/vendor?limit=&sort=&quality=&budget=&force=
GET    /api/favorites
POST   /api/favorites                  body: {"item_id": int, "quality": "hq"|"nq"}
DELETE /api/favorites/{item_id}/{quality}
GET    /api/favorites/snapshot
GET    /api/history/top?days=&metric=&source=&limit=
GET    /api/settings/options           dropdown enums (worlds / DCs / tax cities)
POST   /api/refresh?resource=...
```

`refresh` resources: `worlds`, `data_centers`, `marketable`, `tax`, `vendors`,
`icons`, `maps`, `collectibles`, `items`, `scans`, `all`. Catalogs that only
change on game patches (`maps`, `collectibles`, `items`) are excluded from
`all` and must be refreshed explicitly.

### Rate-limit policy

Universalis fair-use:

- 25 req/s sustained, 8 connections per IP — we target 20 req/s, 8 concurrent.
- Up to 100 item IDs per `/aggregated` call — we chunk at 100.
- `User-Agent` header required — set in `.env`.
- Every outbound call routes through `core/rate_limit.RateLimiter`.

XIVAPI v2 has no documented limits; we use 10 req/s, 4 concurrent as courtesy.

### Architecture

```
src/app/
  api/         FastAPI routers (one per resource)
  clients/     outbound HTTP wrappers — universalis, xivapi, ffxivcollect, teamcraft
  core/        config, db, rate_limit, http_client, cache
  models/      pydantic schemas
  services/    business logic (no FastAPI imports)
```

Import direction: `api/` → `services/` → `clients/` → `core/`. Never reversed.

### Caveats

- **First scan slow** — cross-world ~40s, vendor ~17s (server-side latency per
  `/aggregated` call). Subsequent loads cache for 5 min.
- **Item names before items.json lands** — on a cold first run, market pages
  show numeric IDs until the background `items.json` download finishes.
- **Vendor location** — XIVAPI's GilShop sheet has no NPC location info. NPC
  names are captured via an ENpcBase → ENpcResident scan; map/zone is not.
- **Port in use** — if `8000` is taken the server fails to start. Close the
  other program using it, or change the port in the run scripts.

### Out of scope

- Auth / multi-user
- Cross-region trading (game restriction)
- Game-client integration / auto-buying
