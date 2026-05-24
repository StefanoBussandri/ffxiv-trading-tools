# FFXIV Gil Trading Tool — Build Plan

Personal-use FFXIV marketboard arbitrage tool. Backend in FastAPI, static frontend, SQLite for history/favorites, Universalis as the price feed, XIVAPI for vendor (NPC shop) prices.

## Stack

- **Backend:** FastAPI (Python 3.12), served by `uvicorn`
- **DB:** SQLite via stdlib `sqlite3` or `aiosqlite`
- **HTTP client:** `httpx` async, shared client, capped connections
- **Frontend:** static HTML/CSS/vanilla JS — no React/Vue/build step. Served by FastAPI via `StaticFiles`.
- **Config:** `.env` loaded via `pydantic-settings`
- **Package management:** `uv` — add deps with `uv add`, never pip

## Existing project state

Skeleton at the repo root already contains:
- `pyproject.toml` + `.venv` (uv-managed)
- `docs/rest-api.md` — Universalis REST API reference (authoritative; read this for endpoint shapes)
- `docs/ws-api.md` — Universalis WebSocket API reference (out of scope for v1)
- `resources/items.json` — item ID → name mapping from ffxiv-teamcraft
- `scripts/html_to_md.py` — utility, ignore

## `.env` keys

```
HOME_WORLD=Odin                # name or ID
DATA_CENTER=Light              # used for cross-world scope
UNIVERSALIS_BASE=https://universalis.app/api/v2
XIVAPI_BASE=https://xivapi.com
USER_AGENT=ffxiv-trader/0.1 (contact: <user-email>)
FAVORITES_POLL_SECONDS=60
LISTING_FRESHNESS_HOURS=24     # drop listings older than this
MIN_PROFIT_GIL=1000            # filter floor
MIN_ROI_PCT=10
MIN_SALES_PER_DAY=0.5          # velocity floor
TAX_CITY=Limsa Lominsa         # retainer city used for tax math
HISTORY_RETENTION_DAYS=30
RETAINER_COUNT=2               # how many retainers the player has
RETAINER_MARKET_SLOTS=20       # marketboard slots per retainer (game-defined)
```

`RETAINER_COUNT * RETAINER_MARKET_SLOTS` = total listings the player can post. Use this as the **default `limit`** for `/api/opportunities/*` so the surfaced rows match what the player can actually list. Override per-request via `?limit=`. Surface this number on the UI (e.g. "showing top 40 — your listing ceiling").

Ship a `.env.example` covering every key.

## Universalis API constraints — hard requirements

Per `docs/rest-api.md`:

- **25 req/s sustained, 50 req/s burst** on the API
- **Max 8 simultaneous connections per IP** — set `httpx.Limits(max_connections=8)`
- **Up to 100 item IDs comma-separated per call** to `/aggregated/{worldDcRegion}/{itemIds}` — chunk requests by 100
- **Prefer `/api/v2/aggregated/...`** over the currently-shown endpoint for bulk scans (cached, lighter). Only hit currently-shown for items already short-listed as candidates.
- Set a real `User-Agent` header on every request (from `.env`)
- Implement a token-bucket or `asyncio.Semaphore`-based rate limiter wrapping the httpx client — target ~20 req/s sustained to leave headroom. **Every** outbound API call must go through this wrapper.

Violating these can get the IP banned. Treat the limiter as non-negotiable.

## Data caching

On first run, fetch and persist as JSON files under `resources/cache/`:

- `data_centers.json` ← `GET /api/v2/data-centers`
- `worlds.json` ← `GET /api/v2/worlds`
- `marketable.json` ← `GET /api/v2/marketable` (item ID allowlist)
- `vendor_items.json` ← XIVAPI: paginate `/GilShopItem` joined with `/Item` to get `{itemId, name, gilPrice, shopName}`. Static game data; cache aggressively.
- `tax_rates.json` ← `GET /api/v2/tax-rates?world={HOME_WORLD}` (refresh on demand — rates rotate weekly)

On subsequent startup, skip the fetch if the file exists. Expose `POST /api/refresh` (optional `?resource=worlds|tax|vendors|all`) to force a re-fetch.

## SQLite schema

```sql
CREATE TABLE IF NOT EXISTS favorites (
  item_id INTEGER NOT NULL,
  quality TEXT NOT NULL CHECK (quality IN ('hq','nq')),
  added_at INTEGER NOT NULL,
  PRIMARY KEY (item_id, quality)
);

CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY,
  observed_at INTEGER NOT NULL,    -- unix ts
  item_id INTEGER NOT NULL,
  quality TEXT NOT NULL,
  buy_world TEXT,
  buy_price INTEGER,
  sell_world TEXT,
  sell_price INTEGER,
  profit INTEGER,
  roi_pct REAL,
  velocity REAL,
  source TEXT                       -- 'cross-world' | 'vendor'
);
CREATE INDEX IF NOT EXISTS idx_history_item ON history(item_id, observed_at);
```

Trim rows older than `HISTORY_RETENTION_DAYS` on startup.

## Profit math

For each item × quality:

- `buy_price` — cheapest source (rival-world min listing, or vendor gil price)
- `sell_price` — home-world current best listing (configurable: "match best" vs "undercut by 1")
- `tax_pct` — retainer city tax from `tax_rates.json` (city configured via `TAX_CITY`)
- `profit = sell_price * (1 - tax_pct) - buy_price`
- `roi_pct = profit / buy_price * 100`
- `profit_per_day = profit * daily_sale_velocity`

Drop any listing whose `lastUploadTime` is older than `LISTING_FRESHNESS_HOURS`. Apply filters: `MIN_PROFIT_GIL`, `MIN_ROI_PCT`, `MIN_SALES_PER_DAY`.

HQ and NQ are tracked as **separate** opportunities.

## Project layout

Uses Python **src layout** (package lives under `src/`, not at the repo root). Grouping inside the package is **by layer** (api / clients / services / core / models).

```
ffxiv-trader/
  src/
    app/
      __init__.py
      main.py                  # FastAPI app, static mount, lifespan startup
      api/                     # FastAPI routers — one file per resource
        __init__.py
        opportunities.py       # GET /api/opportunities/cross-world, /vendor
        favorites.py           # GET/POST/DELETE /api/favorites, snapshot
        history.py             # GET /api/history/top
        tax.py                 # GET /api/tax-rates
        refresh.py             # POST /api/refresh
      clients/                 # outbound HTTP clients
        __init__.py
        universalis.py         # /aggregated, /tax-rates, /worlds, /marketable
        xivapi.py              # GilShopItem one-shot fetcher
      core/                    # shared infrastructure
        __init__.py
        config.py              # pydantic-settings (loads .env from repo root)
        db.py                  # sqlite connection + schema init
        rate_limit.py          # token bucket
        http_client.py         # shared httpx.AsyncClient (limits=8)
        cache.py               # resources/cache/ JSON read/write
      models/                  # pydantic schemas + DB row types
        __init__.py
        opportunity.py
        favorite.py
        history.py
        tax.py
      services/                # business logic, no FastAPI imports here
        __init__.py
        opportunities.py       # scan_cross_world, scan_vendor
        favorites.py           # CRUD
        history.py             # write + aggregate
        refresh.py             # cache refresh orchestration
  static/                      # served by FastAPI StaticFiles at /
    index.html
    vendor.html
    favorites.html
    history.html
    app.css
    app.js
  resources/
    items.json
    cache/                     # generated, gitignored
  docs/
    plan.md
    rest-api.md
    ws-api.md
  data.db                      # generated, gitignored
  .env                         # gitignored
  .env.example                 # committed, documents every key
  pyproject.toml
```

### src layout requirements

src layout means the package is **not** importable from the repo root unless installed. Two pieces of setup:

1. `pyproject.toml` must declare the package path so the build backend (hatchling, the uv default) finds `src/app`:

   ```toml
   [tool.hatch.build.targets.wheel]
   packages = ["src/app"]
   ```

2. Install the project in editable mode so imports resolve:

   ```
   uv sync          # uv 0.4+ installs the current project automatically
   ```

   Then `uv run uvicorn app.main:app --reload` works — `uv run` uses the project's venv where `app` is installed.

### Import discipline

- **`api/`** imports `services/` and `models/`. Never the reverse.
- **`services/`** imports `clients/`, `core/`, `models/`. Never `api/`.
- **`clients/`** imports `core/` (for the rate-limited HTTP client) and `models/` only.
- **`core/`** depends on nothing else inside `app/`.
- **`models/`** depends on nothing else inside `app/` (pure data).

## API surface

- `GET /api/opportunities/cross-world?limit=<RETAINER_COUNT*RETAINER_MARKET_SLOTS>&sort=profit_per_day&quality=hq|nq|both`
- `GET /api/opportunities/vendor?limit=<RETAINER_COUNT*RETAINER_MARKET_SLOTS>&sort=...`
- `GET /api/favorites` / `POST /api/favorites` / `DELETE /api/favorites/{item_id}/{quality}`
- `GET /api/favorites/snapshot` — live prices for all favorites in one batched `/aggregated` call
- `GET /api/history/top?days=7&metric=profit_per_day`
- `GET /api/tax-rates`
- `POST /api/refresh?resource=worlds|tax|vendors|all`

## Frontend pages

Static, served at `/`. Each table: item name, quality badge, buy world/price, sell world/price, tax-adjusted profit, ROI %, sales/day, last updated. Click row → favorites toggle. Sort toggle between profit/unit, profit/day, ROI %.

- `index.html` — cross-world opportunities
- `vendor.html` — vendor flips
- `favorites.html` — favorites with polling via `setInterval` + `fetch`; pause when `document.visibilityState === 'hidden'`
- `history.html` — top items by metric over a date range
- Shared `app.css`, `app.js` (fetch helpers + sortable table)

## Phases

Build in this order. Each phase ends with something runnable and verifiable.

### Phase 1 — Foundation
**Goal:** server boots, config loads, DB schema exists, static frontend placeholder renders.

- `pyproject.toml` — add deps `fastapi`, `uvicorn[standard]`, `httpx`, `pydantic-settings`, `aiosqlite` (or stdlib `sqlite3`); add `[tool.hatch.build.targets.wheel] packages = ["src/app"]` for src layout
- `src/app/__init__.py` — empty
- `src/app/core/config.py` — `Settings` class reading `.env` from repo root
- `src/app/core/db.py` — sqlite connection + schema init on startup
- `src/app/main.py` — FastAPI app, lifespan startup (init DB, init httpx client), `StaticFiles` mount at `/`
- `static/index.html` — placeholder "It works" page
- `.env.example`, `.gitignore` (`.env`, `data.db`, `resources/cache/`)
- Run `uv sync` once after editing `pyproject.toml` to install the project in editable mode

**Acceptance:** `uv run uvicorn app.main:app --reload` boots, `http://localhost:8000/` serves the placeholder, `data.db` is created with both tables.

### Phase 2 — Rate-limited Universalis client + reference caching
**Goal:** every API call is rate-limited; worlds/DCs/marketable/tax cached to disk.

- `src/app/core/http_client.py` — constructs the shared `httpx.AsyncClient` with `limits=httpx.Limits(max_connections=8)` and the `User-Agent` header from config
- `src/app/core/rate_limit.py` — token-bucket limiter (~20 req/s); every outbound request acquires a token before the httpx call
- `src/app/core/cache.py` — read/write helpers for `resources/cache/*.json`
- `src/app/clients/universalis.py` — `UniversalisClient` with methods `get_data_centers()`, `get_worlds()`, `get_marketable()`, `get_tax_rates(world)`, `get_aggregated(scope, item_ids)`. Reads cache first when applicable.
- `src/app/api/tax.py`, `src/app/api/refresh.py` — endpoint routers
- Lifespan startup populates the four cache files if missing.
- `GET /api/tax-rates` and `POST /api/refresh` endpoints.

**Acceptance:** first boot writes `resources/cache/*.json`; second boot logs cache hits and makes zero requests for those resources. Log shows in-flight request count never exceeds 8 and per-second rate stays ≤ 25.

### Phase 3 — Vendor data
**Goal:** `vendor_items.json` populated from XIVAPI.

- `src/app/clients/xivapi.py` — paginate `/GilShopItem`, join with `/Item` for name + `priceMid` (vendor gil price), persist `{itemId, name, gilPrice, shopName}`. Runs once on first startup; idempotent. Uses the same shared rate-limited client.
- Goes through the same rate limiter (lower rate is fine; this is one-shot).

**Acceptance:** `resources/cache/vendor_items.json` exists with thousands of rows, includes recognizable items (e.g., basic dyes), gilPrice present.

### Phase 4 — Cross-world opportunities (core feature)
**Goal:** end-to-end home page works.

- `src/app/services/opportunities.py` — `scan_cross_world()`:
  1. Load marketable item IDs.
  2. Chunk by 100, call `/aggregated/{DATA_CENTER}/{ids}` for each chunk via `UniversalisClient`.
  3. For each item × quality, compute buy/sell/profit/ROI/profit-per-day. Apply freshness + filters.
  4. Persist every surviving opportunity to `history` via `services/history.py`.
- `src/app/models/opportunity.py` — pydantic schema for the response row.
- `src/app/api/opportunities.py` — `GET /api/opportunities/cross-world` returns sorted JSON.
- `static/index.html` + `app.js` — fetch, render sortable table, sort toggle.

**Acceptance:** page loads, shows real opportunities, tax-adjusted math is correct (verify one row by hand), sort toggle works, listings older than `LISTING_FRESHNESS_HOURS` don't appear.

### Phase 5 — Vendor flips
**Goal:** same shape as cross-world, but `buy_price` comes from `vendor_items.json`.

- `scan_vendor()` in `src/app/services/opportunities.py`. Only consider item IDs present in both vendor cache and marketable allowlist. Router method on `src/app/api/opportunities.py`.
- `GET /api/opportunities/vendor`.
- `static/vendor.html` + JS reuses the table renderer.

**Acceptance:** page shows vendor → marketboard flips, profit math accounts for tax, known cheap-to-flip items show up.

### Phase 6 — Favorites + polling
**Goal:** favorites CRUD + auto-refreshing prices.

- `src/app/services/favorites.py` — SQLite CRUD. `src/app/models/favorite.py` — schema. `src/app/api/favorites.py` — routes.
- `GET /api/favorites/snapshot` — single batched `/aggregated` call covering all favorited item IDs.
- `static/favorites.html` + JS — `setInterval(fetch, FAVORITES_POLL_SECONDS * 1000)`. Pause on tab hidden. Star/unstar from any table writes back through the API.

**Acceptance:** add favorites from index page, switch to favorites page, watch prices update on interval, hide tab → polling stops, show tab → resumes.

### Phase 7 — History view
**Goal:** surface items that are *consistently* profitable.

- `src/app/services/history.py` — aggregations: count of appearances, avg profit, avg ROI, avg velocity over an N-day window, grouped by `item_id, quality`. `src/app/models/history.py` — schema. `src/app/api/history.py` — routes.
- `GET /api/history/top?days=7&metric=profit_per_day`.
- `static/history.html` + JS — table with date-range selector and metric toggle.
- Startup task trims rows older than `HISTORY_RETENTION_DAYS`.

**Acceptance:** after running scans for a few hours, history page shows recurring winners with appearance counts.

### Phase 8 — Polish
- Tax rates panel on every page (highlight cheapest city).
- Loading spinners + error toasts.
- README with screenshots + setup steps.
- Verify rate-limit logs across a full scan; tune chunk concurrency if needed.

## Acceptance criteria (whole project)

- `uv run uvicorn app.main:app --reload` starts the server at `http://localhost:8000/`
- First run populates `resources/cache/` and `data.db`; second run skips re-fetch (visible in logs)
- Cross-world page shows real, tax-adjusted opportunities sorted by the selected metric
- Rate limiter enforces ≤ 25 req/s globally with ≤ 8 in flight (debug log of in-flight count)
- Favorites page auto-refreshes; pauses when tab hidden
- History page shows top items over a configurable window
- `.env.example` documents every config key

## Out of scope (do not build)

- Auth / multi-user
- WebSocket subscriptions (REST polling is sufficient for v1)
- Cross-region trading (intra-DC only — game restriction)
- Any game-client integration or auto-buying
