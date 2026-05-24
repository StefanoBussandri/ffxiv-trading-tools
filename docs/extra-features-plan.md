# Extra Features Plan

Five additions: a copy-name button, a stale-data warning, favourite price
alerts, an item detail panel, and a profit-calculator dashboard widget.

---

## Part 1 — Copy item-name button

**Goal:** a small copy icon to the left of every item name, inline with the
text and the same size, that copies the plain item name to the clipboard (for
pasting into the in-game market board search).

**Frontend only.**

- **`common.js`** — new `copyButton(name)` helper returning
  `<button class="copy-name" data-name="<escaped name>" title="Copy item name">…</button>`
  with an inline SVG sized `1em`.
- `renderItemCell()` prepends `copyButton(row.name)` before the name link;
  `wikiLink()` does the same — so history and every COLUMN_DEFS table get it.
- One delegated listener (in `common.js`): on `.copy-name` click →
  `navigator.clipboard.writeText(btn.dataset.name)`, then swap the icon to a
  tick for ~1 s as feedback. Stop propagation so it never opens the item
  detail panel (Part 4).
- **`app.css`** — `.copy-name`: `inline-flex`, `width/height: 1em`,
  `color: var(--dim)`, hover `var(--fg)`, no border/background.

**Files:** `static/js/common.js`, `static/css/app.css`.

---

## Part 2 — Stale data warning

**Goal:** a red exclamation badge next to the profit value when the market
data behind that row is older than a configurable cutoff (hours).

**Setting.**
- `core/config.py` — add `STALE_DATA_HOURS: int = 12`; add to
  `GAME_SETTING_KEYS`.
- `static/js/settings.js` — add to `TOOL_FIELDS`:
  `{ id: 'STALE_DATA_HOURS', label: 'Stale data cutoff (h)', type: 'number' }`.

**Backend — flag rows.**
- New helper in `services/opportunities.py`:
  `_data_stale(buy_upload_ts, sell_upload_ts, now_ms) -> bool` — true when any
  non-zero upload timestamp is older than `STALE_DATA_HOURS`. Zero timestamps
  (e.g. a vendor buy side) are ignored.
- Every row builder stamps `row["data_stale"]`: `_row_from_aggregated`
  (cross-world), `_do_scan_vendor`, the favourites snapshot, maps and
  collectibles row builders.

**Frontend — badge.**
- `common.js` `COLUMN_DEFS.profit.render` — when `r.data_stale`, append
  `<span class="stale-badge" title="Market data is older than your stale
  cutoff — prices may be wrong">!</span>`.
- **`app.css`** — `.stale-badge`: small red circle, white `!`, `var(--negative)`.

**Files:** `core/config.py`, `services/opportunities.py`, `services/maps.py`,
`services/collectibles.py`, `api/favourites.py`, `static/js/common.js`,
`static/js/settings.js`, `static/css/app.css`.

---

## Part 3 — Price alerts on favourites

**Goal:** per-favourite buy/sell price thresholds. When a threshold is met,
play a ping and show a toast.

### Data model

`favourites` table gains four nullable columns:

| Column | Meaning |
|---|---|
| `buy_target` INTEGER | buy-price threshold (NULL = no buy alert) |
| `buy_dir` TEXT | `below` or `above` |
| `sell_target` INTEGER | sell-price threshold (NULL = no sell alert) |
| `sell_dir` TEXT | `below` or `above` |

`db.py` — `_migrate_favourite_alerts(db)`: read `PRAGMA table_info(favourites)`,
`ALTER TABLE favourites ADD COLUMN …` for any missing column. Run in `init_db`.

### Backend

- `services/favourites.py` — `list_favourites()` selects the four new columns;
  new `set_favourite_alert(item_id, quality, buy_target, buy_dir, sell_target,
  sell_dir)`.
- `api/favourites.py` — `PUT /api/favourites/{item_id}/{quality}/alert` writes
  the alert config. `/api/favourites/snapshot` rows include the four fields.

### Favourites page — alert columns

- Two new `COLUMN_DEFS` entries, `fav_buy_alert` and `fav_sell_alert`. Both
  are added to `DEFAULT_LAYOUT_FAVOURITES` as **visible-by-default** columns,
  so they appear on the favourites page out of the box. Each cell renders a
  `<select class="fav-alert-dir">` (below / above) and a
  `<input type="number" class="fav-alert-val">`, seeded from the row.
- `favourites.js` — delegated `change` listener on the table body: on edit,
  debounced `PUT …/alert`. Empty input clears that side's alert.

### Toasts (rewrite `toast.js`)

The current toast is single, ephemeral, unclosable. Rewrite:

- A `#toast-host` column container.
- **Max 5** toasts; adding a 6th removes the oldest.
- Each toast has a **× close button**; still auto-dismisses after a timeout.
- `toast(msg, kind)` — `kind` ∈ `error | info | alert`. Existing
  `window.toast('msg')` callers keep working.

### Alert evaluation — new `static/js/alerts.js`

Loaded on every page. On page load and on each `ft-data-refreshed`
(auto-rescan finished):

1. Fetch `/api/favourites/snapshot`.
2. For each row with alert rules, test live `buy_price` / `sell_price`
   against the target + direction.
3. Keep a `Set` of currently-triggered alert keys
   (`itemId:quality:buy|sell`). A key newly present → fire (toast + ping).
   A key that drops out → removed from the set, so it can fire again later.

**Ping sound.** A short WebAudio oscillator beep (`playPing()` in
`alerts.js`) — no audio asset. The oscillator routes through a `GainNode`
whose gain is set from the volume preference; the beep is skipped entirely
when the sound preference is off.

**Sound toggle + volume.** Add to `SETTINGS_DEFAULTS` in `common.js`:
- `alerts_sound: true` — on/off.
- `alerts_volume: 0.5` — `0.0`–`1.0`.

The settings panel gets a sound on/off checkbox and a volume slider (`range`
input, shown disabled/greyed when sound is off). `alerts.js` reads
`FT.loadSettings()` before each ping: skip if `!alerts_sound`, else set the
`GainNode` gain to `alerts_volume`.

**Files:** `core/db.py`, `services/favourites.py`, `api/favourites.py`,
`models/favourite.py`, `static/js/toast.js`, `static/js/alerts.js` (new),
`static/js/common.js`, `static/js/favourites.js`, `static/js/settings.js`,
`static/css/app.css`, every `*.html` (load `alerts.js`).

---

## Part 4 — Item detail panel

**Goal:** click a table row → a panel opens with a price-history graph on
top, an all-worlds listings table bottom-left, and a home-world listings
table bottom-right — each sorted cheapest first.

### Backend

- New `api/item.py` — `GET /api/item/{item_id}?quality=hq|nq`:
  - `UniversalisClient.get_currently_shown(DATA_CENTER, [item_id])` → active
    listings across the data centre.
  - `UniversalisClient.get_history(DATA_CENTER, [item_id])` → sale history.
  - Filter both to the requested quality; sort listings by price ascending.
  - Return `{ item_id, name, quality, home_world, history: [{ts, price,
    quantity, world}], listings: [{world, price, quantity, hq, age_s}] }`.

### Frontend — `static/js/item-detail.js` (new)

- A modal (backdrop + panel, same pattern as the dashboard editor overlay).
- **Top:** price-history line graph — hand-rolled SVG, time on X, price on Y,
  a few axis labels. Reuses the sparkline maths from `reliable.js`, scaled up.
- **Bottom-left:** "All listings" — world, price, qty; cheapest first.
- **Bottom-right:** "Your home world" — price, qty; cheapest first (the
  listings filtered to `home_world`).
- `Esc` / backdrop click / × closes.

### Wiring

- Row renders on the market pages and dashboard table widgets add
  `data-iid` + `data-q` to each `<tr>`.
- `item-detail.js` adds one delegated click listener: a click inside a
  `table.data tbody tr` that is **not** on an `<a>`, `<button>` or `<input>`
  opens the panel for that row's item.

**Files:** `api/item.py` (new), `src/app/main.py` (register router),
`static/js/item-detail.js` (new), `static/css/app.css`, market `*.html`
(load `item-detail.js`), row renderers in `app.js` / `maps.js` /
`collectibles.js` / `reliable.js` / `favourites.js` / `history.js` /
`dashboard-widgets.js` (add `data-iid` / `data-q`).

---

## Part 5 — Profit calculator widget

**Goal:** a dashboard widget to quickly check a flip — enter buy price,
quantity and sell price; see the net profit after tax.

- New `profit_calc` entry in the `dashboard-widgets.js` registry —
  `sources: []`, default ~3×3.
- `render` builds three number inputs (Buy / unit, Quantity, Sell / unit) and
  a result block (net profit, profit per unit, ROI %).
- Tax: the widget calls `FT.getTaxInfo()` once and
  `FT.effectiveTaxRate(tax, FT.loadSettings())`; recomputes on every `input`.
  `net = sell × (1 − tax) × qty − buy × qty`.
- No backend, no data source.

**Files:** `static/js/dashboard-widgets.js`, `static/css/app.css`.

---

## Implementation order

1. **Profit calculator widget** — isolated, no backend.
2. **Copy item-name button** — isolated, `common.js` + CSS.
3. **Stale data warning** — setting + server flag + badge.
4. **Toast rewrite + price alerts** — DB migration, API, favourites columns,
   `alerts.js`, ping, sound toggle.
5. **Item detail panel** — endpoint, modal, graph, row wiring.

## Testing checklist

- Copy button sits left of the name, matches text size; click copies the
  plain item name; never opens the detail panel.
- Stale badge appears when a row's upload data exceeds the cutoff; changing
  `STALE_DATA_HOURS` in settings changes which rows show it.
- The buy/sell alert columns show on the favourites page by default.
- Set a favourite buy/sell alert; when the next snapshot meets it a toast +
  ping fire once; the toast closes via ×; 6th toast evicts the oldest;
  the sound toggle silences the ping; the volume slider changes its loudness.
- Item detail panel opens on row click, graph + both listings tables render,
  cheapest first; `Esc` closes.
- Profit calculator widget computes net profit after tax and updates live.
