# Easy Startup Plan

Goal: make ffxiv-trader trivial to set up and run for a non-coder friend. One
double-click to launch; a guided first-run setup screen; everything else
automatic.

## Locked decisions

- **First-run UX:** fast start + live progress. Server reachable in ~5s (only
  worlds / data centers / tax fetched blocking). Setup screen shows immediately;
  heavy data (vendors, maps, mounts, minions, icons, items.json) loads in the
  background behind a progress indicator.
- **Install:** Stefano installs Python + deps on the friend's PC. Run scripts
  only need to launch reliably day-to-day; README is mainly Stefano's reference
  plus a short "how to start it" section for the friend.

---

## Part 1 — Startup cache bootstrap (fast + background)

**Problem:** `populate_initial_cache()` currently `await`s every fetch before
the server becomes reachable. The vendor NPC sheet walk alone is ~1-3 min, so a
cold first run leaves the browser dead for minutes.

**Change `services/refresh.py`:**

- Split `populate_initial_cache()` into two phases:
  - **Blocking (awaited in lifespan):** `get_data_centers`, `get_worlds`,
    `get_marketable`, `get_tax_rates`. Four quick calls (~2-5s). These are what
    the setup screen dropdowns and core scans need.
  - **Background (`asyncio.create_task`):** a new `_background_bootstrap()`
    coroutine runs, in order: `items.json` download, `populate_vendor_items`,
    `populate_maps`, `populate_mounts`, `populate_minions`, `populate_item_icons`,
    then `_initial_scans_background()` and `_auto_rescan_loop()`.
- Add a module-level status tracker:
  ```python
  _bootstrap = {
      "ready": False,            # all background steps done
      "steps": {                 # step -> "pending" | "done" | "failed"
          "items": "pending", "vendors": "pending", "maps": "pending",
          "mounts": "pending", "minions": "pending", "icons": "pending",
      },
      "error": None,
  }
  ```
  `_background_bootstrap()` updates each step as it completes; sets
  `ready = True` at the end.
- Expose `bootstrap_status()` returning that dict.
- Wrap the blocking phase so a network failure surfaces a clear message
  (logged + reflected in `_bootstrap["error"]`) instead of a hard crash.

**New API — `api/refresh.py`:**

- `GET /api/startup/status` → `{ ready, steps, error }`.

**Result:** lifespan startup finishes in ~5s; browser auto-opens (already wired
in `main.py`); setup screen + market pages are reachable while heavy data
finishes loading behind a progress indicator.

---

## Part 2 — items.json → cache folder + auto-download

`resources/items.json` (9.5 MB) is byte-identical to the teamcraft source.
Move it into the cache folder so fresh installs fetch it automatically.

- **New `clients/teamcraft.py`** — `TeamcraftClient.populate_items(force=False)`:
  if `resources/cache/items.json` is missing (or `force`), GET
  `TEAMCRAFT_ITEMS_URL` and write the bytes straight to
  `resources/cache/items.json`. Sends `User-Agent`.
- **`core/config.py`** — add `TEAMCRAFT_ITEMS_URL` field
  (`https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/master/libs/data/src/lib/json/items.json`),
  add it to the `.env` / `.env.example` API-endpoints block.
- **`services/opportunities.py`** — `_load_items()` reads
  `settings.cache_dir / "items.json"` instead of `resources/items.json`.
- **`services/refresh.py`** — `populate_items` runs first in
  `_background_bootstrap()` (step `"items"`); add `"items"` to
  `VALID_RESOURCES` and the `refresh_resource()` handler.
- **Repo hygiene** — delete the tracked `resources/items.json`. `resources/cache/`
  is already in `.gitignore`, so the cached copy is correctly untracked. For
  Stefano's working copy, physically move the existing file so he does not
  re-download it.

---

## Part 3 — First-run detection

The setup screen must show only when the app has never been configured.

**Problem:** `core/config.py._sync_db_settings()` currently *seeds*
`app_settings` from defaults on first run, so the table is never empty.

**Change:** stop seeding. `_sync_db_settings()` becomes overlay-only — it reads
whatever rows exist and applies them; if none exist, the pydantic field
defaults remain the runtime fallback (the app still runs pre-setup).

**Definition of "configured":** `app_settings` table has at least one row.

- Fresh install → empty → not configured → setup screen.
- Stefano's existing db → already has 16 rows → configured → no setup screen.
  No migration flag needed.

**New API — `api/settings_api.py`:**

- `GET /api/setup/status` → `{ configured: bool }` (count of `app_settings` rows > 0).
- `POST /api/setup` — body `{ data_center, home_world, tax_city, retainer_count, budget }`:
  - Writes `DATA_CENTER`, `HOME_WORLD`, `TAX_CITY`, `RETAINER_COUNT` to
    `app_settings` via `settings_store.set_game_settings` (also hot-applies).
  - Writes `budget` into the `ffxiv-trader.settings.v1` UI-pref (where
    `FT.loadSettings()` reads it).
  - Returns `{ ok: true }`.

---

## Part 4 — First-run setup screen

**`static/setup.html`** — standalone page, *no* topbar / taxbar / shared
components. Loads `app.css` plus its own `setup.js` and minimal inline CSS.

**Layout:** dark app background; a single centered card "floating" over it with
an animated gradient border.

**Card contents (a form):**

| Field | Control | Source |
|---|---|---|
| Data Center | `<select>` | `/api/settings/options` → `data_centers` |
| Home World | `<select>` | `options.worlds`, filtered to the chosen DC |
| Tax City | `<select>` | `options.tax_cities` |
| Retainer count | `<input type=number>` (default 2) | — |
| Budget (gil/unit) | `<input type=number>` | — |

- DC → Home World filtering: reuse the logic already in `settings.js`
  (`applyWorldFilter`).
- Retainer *market slots* is not asked — stays at the default 20.
- A short intro line ("Welcome — pick your server so prices are calculated for
  you") and a note that everything is changeable later via the gear icon.
- Submit → `POST /api/setup` → on success `location.replace('/')`.
- Basic validation: all selects chosen, numbers positive, Home World belongs to
  the selected DC.

**Animated gradient border** — CSS, e.g.:
```css
@property --angle { syntax: '<angle>'; initial-value: 0deg; inherits: false; }
.setup-card::before {
  content: ''; position: absolute; inset: -2px; border-radius: 16px; z-index: -1;
  background: conic-gradient(from var(--angle),
              var(--accent), transparent 25%, var(--accent) 50%,
              transparent 75%, var(--accent));
  animation: setup-spin 6s linear infinite;
}
@keyframes setup-spin { to { --angle: 360deg; } }
```
(Fallback for browsers without `@property`: a static or slow-pulsing gradient.)

**Progress indicator:** while background data loads, the setup card shows a
small line driven by `GET /api/startup/status` — e.g. "Loading game data…
vendors ✓ mounts ✓ icons …". Submit stays enabled (setup only needs the fast
caches); the indicator just reassures the friend nothing is broken.

**Routing guard:** combine the boot check into the single sync request
`common.js` already makes:

- New `GET /api/boot` → `{ configured: bool, prefs: { ... } }` (setup status +
  all UI prefs in one call).
- `common.js` hydration: if `!configured` → `location.replace('/setup.html')`
  and stop; otherwise populate `_prefs` as today.
- `setup.html` does **not** load `common.js`, so it never redirect-loops.
- Optional: keep `/api/ui-prefs` GET for symmetry, or retire it in favour of
  `/api/boot`.

**Topbar status pill (optional, recommended):** show a small "Preparing game
data…" pill in the topbar (reuse the existing `rescan-timer` pill styling)
until `/api/startup/status` reports `ready`, so the main pages also signal that
background loading is still in progress.

---

## Part 5 — requirements.txt

Add `requirements.txt` at repo root so `pip` works without `uv`. Pinned to the
current lock versions:

```
fastapi==0.136.1
uvicorn[standard]==0.47.0
httpx==0.28.1
pydantic-settings==2.14.1
lxml==6.1.0
markdownify==1.2.2
aiosqlite==0.22.1
beautifulsoup4==4.14.3
```

These are the 8 direct dependencies; pip resolves the transitive set. Keep
`pyproject.toml` as the source of truth for `uv`; `requirements.txt` is the
pip-only mirror.

---

## Part 6 — Windows run scripts

Two double-clickable `.bat` files at repo root.

**`run.bat`** (plain Python — the friend's daily launcher):
```bat
@echo off
cd /d "%~dp0"
if not exist ".venv\" (
  echo First run - setting up...
  python -m venv .venv || (echo Python 3.12+ required - install from python.org & pause & exit /b 1)
  .venv\Scripts\python -m pip install -r requirements.txt
)
.venv\Scripts\python -m uvicorn --app-dir src app.main:app
pause
```

**`run-uv.bat`** (uv — Stefano's launcher):
```bat
@echo off
cd /d "%~dp0"
uv sync
uv run uvicorn --app-dir src app.main:app
pause
```

Notes:
- `cd /d "%~dp0"` → works no matter where double-clicked.
- `pause` → window stays open so errors are readable.
- No `--reload` (dev-only; not for the friend).
- `--app-dir src` → `app` package importable without an editable install.
- Server runs on the uvicorn default `http://localhost:8000/`; `main.py`
  auto-opens the browser.
- Optional: a one-line `make-shortcut.bat` (or a README step) that drops a
  desktop shortcut to `run.bat`.

---

## Part 7 — README rewrite

Current README is stale: it documents game settings in `.env` (now in the DB),
omits the mounts/minions pages, and lists an outdated cache set.

New README structure:
1. **What it is** — one paragraph.
2. **Quick start (friend)** — "double-click `run.bat`, wait for the browser,
   fill in the setup screen." That's it.
3. **Requirements** — Windows, Python 3.12+ (link), internet on first run.
4. **First run** — what the setup screen asks; that game data loads in the
   background for a few minutes the first time; settings are editable later via
   the gear icon.
5. **Pages** — dashboard, cross-world, vendor, reliable, maps, mounts, minions,
   favorites, history.
6. **Developer notes** — `uv` workflow, `.env` is infra-only now, architecture
   diagram, rate-limit policy, refresh resources. Keep the accurate parts of the
   current README; drop the stale `.env` settings table.

---

## Part 8 — Additional recommendations

- **First-run network failure:** if the blocking fetches fail (no internet),
  show a clear message via `/api/startup/status.error` and let the setup screen
  display "Couldn't reach game data services — check your connection" with a
  retry, instead of hanging.
- **`USER_AGENT`:** `.env` currently carries Stefano's email. Harmless to keep,
  but consider a generic default so the friend's install isn't tagged with a
  personal address. Low priority.
- **`.env` bootstrap:** `main.py._bootstrap_env()` already copies
  `.env.example` → `.env` on first run, so the friend never touches `.env`.
  Keep it.
- **Graceful degradation:** before `items.json` finishes downloading, item
  names fall back to numeric IDs on the market pages. Acceptable for the first
  couple of minutes; the topbar status pill explains it.
- **Port in use:** if `8000` is taken the server fails to start. Out of scope
  for now; note it in README troubleshooting.
- **Settings reachability:** the in-app Settings panel still edits everything
  post-setup — the setup screen is purely the one-time first-run path.

---

## Part 9 — Table search

A per-page search box so a new user can find an item fast. Each page searches
**only its own dataset** — maps page → maps, vendor → vendor items, mounts →
mounts, etc.

### Behaviour

- **Client-side, in-memory.** Every table page already loads its full row set
  client-side; search is just another filter over `state.rows`. No backend
  call → instant. Input is debounced (~80 ms) so typing never thrashes render.
- **Unquoted = partial, token-AND.** Query lower-cased, split on whitespace;
  every token must appear as a substring of the row's searchable text — item
  **name + source + item ID**. `red key` matches any name with both "red" and
  "key", in any order. Source makes "raid", "cosmic", etc. work; ID covers
  generic-named mount items.
- **Quoted = direct match, name only.** `"text"` (double-quoted) matches the
  literal phrase contiguously, case-insensitive, against the item **name
  only** — `"red key"` matches "Faded Red Key" but not "Red Whistle Key".
- Search is **transient** — not persisted, cleared on reload. Filters and
  column layout persist; a momentary search should not.

### UI

- A search `<input>` in each page's `.filters controls` bar, beside the
  Columns & filters button.
- Clear (×) affordance; `Esc` clears + blurs; `/` focuses it.
- Status line reflects the narrowed count, e.g. `12 of 344`.
- Empty result → table body shows `No items match "<query>"`.
- Matched text is highlighted (bold) in the item-name cell — for token-AND,
  each matched token is highlighted.

### Implementation

- **`common.js`** — `matchesSearch(row, query)` helper implementing the
  token-AND / quoted rules; reused by every page.
- **New `static/js/search.js`** — shared component (mirrors `cols-filters.js`):
  binds `#search`, debounces, holds the current term, dispatches
  `ft-search-changed`, exposes `window.FTSearch.term()`.
- **Each page** (`app.js`, `maps.js`, `collectibles.js`, `reliable.js`,
  `favorites.js`, `history.js`) — listen for `ft-search-changed`, apply
  `matchesSearch` in the filter step (before sort). On the paginated
  cross-world / vendor page, a search also resets to page 1.
- Pages with search: cross-world, vendor, maps, mounts, minions, reliable,
  favorites, history. Dashboard widgets are not full tables — no search there.

### Performance

A substring scan of a few thousand in-memory strings per keystroke is
sub-millisecond; the debounce is just polish. No index needed at this scale.
Highlighting only re-renders the visible (post-filter) rows, so its cost
scales with results shown, not the full dataset.

---

## Implementation order

1. **items.json** — `clients/teamcraft.py`, `config.py` URL, `_load_items` path,
   physically move the file, untrack it.
2. **Startup bootstrap** — split `populate_initial_cache`, `_background_bootstrap`,
   status tracker, `GET /api/startup/status`.
3. **First-run detection** — `config.py` stop seeding, `GET /api/setup/status`,
   `POST /api/setup`, `GET /api/boot`.
4. **Setup screen** — `setup.html`, `setup.js`, animated-border CSS, `common.js`
   boot guard, optional topbar status pill.
5. **requirements.txt** + **run scripts**.
6. **Table search** — `matchesSearch` in `common.js`, shared `search.js`, wire
   each table page.
7. **README rewrite**.
8. **Test** (below).

## Testing checklist

Simulate a fresh install:
- Move `data.db` and `resources/cache/` aside (back them up).
- Start via `run.bat` → server reachable within ~5s.
- Browser opens → redirected to `/setup.html`.
- Dropdowns populated (worlds / DCs / tax cities).
- DC change re-filters the Home World list.
- Search box on each table page filters only that page's items; partial
  (token-AND) and quoted-exact both work; status count updates; clearing
  restores the full list.
- Submit → redirect to `/`; `app_settings` now has the 4 keys; budget in
  `ui_prefs`.
- Background load completes; topbar pill clears; vendor / mounts / minions /
  maps pages populate; item names resolve once `items.json` lands.
- Restart → no setup screen (configured); fast boot (all cache hits).
- Restore Stefano's real `data.db` / cache afterwards.
