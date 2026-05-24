# Modular Dashboard Plan

Goal: turn the dashboard into a **modular, movable, resizable** widget grid.
A normally-hidden cog (next to the "Dashboard" title) opens an editor overlay
where widgets can be added, removed, moved and resized on a snap-to-grid
canvas. Layout persists per-user.

---

## Locked decisions (from Q&A)

- **KPI tiles** — each of the 6 KPI numbers is its **own widget** (not a
  grouped strip).
- **Save model** — the editor mutates a **draft**. **Save** commits + persists;
  **Cancel** discards. Accidental moves/removes are recoverable.
- **Widget set** — everything currently on the dashboard, plus mounts,
  minions, history, and the new widgets below (all in scope for v1).

---

## Part 1 — Grid model & layout persistence

**Grid.** 12 columns (matches the existing `.row` / `.span-*` CSS system).
Column width is fluid (`1fr`). Row unit is a fixed **40 px** with the existing
**14 px** gap. The grid grows vertically as needed — no fixed viewport height.

> 40 px / 12 cols is the starting point — fine enough to line things up, coarse
> enough that snapping feels deliberate. One tunable constant
> (`CELL_ROW_PX`, `GRID_COLS`).

**Widget rect.** Every placed widget has integer cell coordinates:
`{ type, x, y, w, h }` — `x` 0–11, `w` 1–12, `y`/`h` ≥ 0 rows. One instance
per widget type (the left-panel toggle is on/off, not "add another").

**Layout object.**
```json
{ "version": 1,
  "widgets": [ { "type": "kpi_reliable", "x": 0, "y": 0, "w": 2, "h": 2 }, ... ] }
```
Disabled widgets are simply absent from the list.

**Persistence.** Stored in the existing server-backed UI-pref store under key
`ffxiv-trader.dashboard.v1` via `FT.prefGet` / `FT.prefSet` (→ `ui_prefs`
table). No backend schema change. A missing/empty pref → the built-in
**default layout** (Part 8).

**New module — `static/js/dashboard-grid.js`** — pure grid math, no DOM:
- `cellRect(widget)` → pixel rect from `{x,y,w,h}`.
- `snap(px)` → nearest cell coordinate.
- `overlaps(a, b)` → boolean.
- `resolveCollisions(layout, movedType)` — see Part 5.
- `findFreeSlot(layout, w, h)` — top-down, left-right scan for the first rect
  that fits without overlap (used for new-widget placement).
- `gridHeight(layout)` → total rows occupied (for the canvas height).

---

## Part 2 — Widget registry & live dashboard render

**New module — `static/js/dashboard-widgets.js`** — a registry. Each entry:
```js
{
  type:      'top_cross_world',
  title:     'Top cross-world',
  defaultW:  6, defaultH: 8,
  minW:      4, minH: 4,
  dataKey:   'cross',          // which fetched dataset it needs (or null)
  render(el, data) { ... },    // live content
}
```

**`dashboard.js` rewrite** — becomes the live grid renderer:
1. Load layout pref (or default).
2. Determine the union of `dataKey`s for enabled widgets; fetch only those
   sources once, dedup (see Part 7).
3. For each widget: create a `.dash-widget` card, position it with CSS Grid
   (`grid-column: x+1 / span w; grid-row: y+1 / span h`), call `render`.
4. Re-render on `ft-data-refreshed` (auto-rescan finished) and
   `ft-settings-changed` — consistent with every other page.

**Widget card.** `.dash-widget` = the existing `.card` look: title row + body.
The body scrolls if content exceeds the widget's box. Table widgets render as
many rows as fit the current height (height-driven — no row-count setting).

The live dashboard and the editor render the **same grid from the same
layout** — the editor just substitutes wireframe tiles for real content.

---

## Part 3 — Widget catalog

Existing (already on the dashboard):

| Widget | Data source | Default w×h | Min |
|---|---|---|---|
| KPI · Reliable trades | reliable watchlist count | 2×2 | 2×2 |
| KPI · Cross-world opps | dashboard stats | 2×2 | 2×2 |
| KPI · Vendor flips | dashboard stats | 2×2 | 2×2 |
| KPI · Favorites | favorites snapshot | 2×2 | 2×2 |
| KPI · Maps tracked | dashboard stats | 2×2 | 2×2 |
| KPI · Listing ceiling | settings | 2×2 | 2×2 |
| Reliable watchlist | `/api/reliable/watchlist` | 6×8 | 4×4 |
| Top cross-world | `/api/dashboard` | 6×8 | 4×4 |
| Top vendor flips | `/api/dashboard` | 6×8 | 4×4 |
| Favorites | `/api/favorites/snapshot` | 6×8 | 4×4 |
| Maps | `/api/dashboard` | 6×8 | 4×4 |

New table widgets:

| Widget | Data source | Default w×h | Min |
|---|---|---|---|
| Mounts | `/api/collectibles/mounts` | 6×8 | 4×4 |
| Minions | `/api/collectibles/minions` | 6×8 | 4×4 |
| History | `/api/history/top` | 6×8 | 4×4 |

New computed / utility widgets:

| Widget | What it shows | Source | Default w×h | Min |
|---|---|---|---|---|
| Bargains | Items listed below recent sale (`spread_pct < 0`), best first | derived from cross+vendor rows | 4×6 | 3×4 |
| Stale listings | Items whose top listing is stale (`stale_listing`) — easy undercut | derived | 4×6 | 3×4 |
| ROI leaders | Top-N opportunities by ROI % | derived | 3×6 | 3×4 |
| Velocity leaders | Top-N opportunities by sales/day | derived | 3×6 | 3×4 |
| Profit potential | One big number — summed `profit_per_day` of all current opps | derived | 3×2 | 2×2 |
| Scan status | Next-rescan countdown, last scan time, items scanned / profitable | `/api/refresh/status` | 3×3 | 3×2 |
| Clock | Live local time (HH:MM:SS); small sub-line "Next scan in MM:SS" | `/api/refresh/status` | 2×2 | 2×2 |
| Notes | Free-text scratchpad, debounced-saved server-side | `ui_prefs` | 3×4 | 2×2 |
| Search | Search box; results expand the widget (Part 6) | derived (client filter) | 4×1 | 3×1 |

Table widgets use a **compact column preset** (icon, item, profit, ROI%,
sales/d) so they read well at narrow widths; the full pages stay the place for
the complete column set. Each table widget keeps a "view all →" link in its
title row.

Computed widgets (Bargains, Stale, ROI/Velocity leaders, Profit potential,
Search) need **no new endpoint** — they filter/sort the cross-world + vendor
rows the dashboard already fetches.

---

## Part 4 — Editor overlay

**Cog button.** In the `.page-head`, immediately after the `Dashboard` `<h1>`:
a small cog `<button id="dash-cog">`. `opacity: 0` by default; the rule
`.page-head:hover #dash-cog { opacity: 1 }` reveals it on hover. Always
keyboard-focusable for accessibility.

**Overlay.** Click cog → a full-window modal (`.dash-editor-backdrop`) over the
dashboard. Layout:
- **Left sidebar** — the widget list. Every widget type, each row showing the
  name + an on/off toggle switch. On = placed on the grid; Off = removed.
- **Main canvas** — the snap grid showing every enabled widget as a blank
  **wireframe tile** (just its title, centered). Faint grid lines are visible
  so cells are obvious.
- **Header** — title "Edit dashboard", a **Reset to default** link, and
  **Cancel** / **Save** buttons.

**New module — `static/js/dashboard-editor.js`** — builds and drives the
overlay. It works on a **draft copy** of the layout. Save → write the draft to
the pref + re-render the live dashboard. Cancel (and backdrop click / `Esc`) →
discard the draft, overlay closes, live dashboard untouched.

**Left-panel toggle.**
- Off → On: place the widget at `findFreeSlot(...)` with its default size
  ("as near the top as it fits"), then `resolveCollisions`.
- On → Off: remove from the draft layout. Its wireframe tile disappears; other
  widgets are left where they are (no auto-compaction).

---

## Part 5 — Editor interactions

All of the following mutate the **draft** layout and re-render the canvas.

**Move.** Press-drag a widget's body. While dragging it follows the cursor
(pixel-precise); a snapped **ghost** shows the target cell rect. On release the
widget commits to the snapped rect and `resolveCollisions` runs.

**Resize.** A handle on the bottom-right corner (plus right / bottom edges).
Dragging it changes `w`/`h`, snapped to whole cells, clamped to the widget's
`minW`/`minH` and to the 12-column bound. `resolveCollisions` runs on release.

**Click-to-remove.** A click on a widget body **with no drag** removes it
(equivalent to toggling it off in the left panel — the two stay in sync). Drag
vs click is disambiguated by a movement threshold (~4 px): below threshold =
click = remove; above = move. Removal is recoverable — re-toggle in the left
panel, or Cancel the whole session.

**Collision / push-out.** `resolveCollisions(layout, movedType)`:
```
for each widget O (≠ moved) that overlaps the moved widget:
    O.y = moved.y + moved.h          # shove O straight down to clear
    recurse: resolveCollisions(layout, O)   # O may now hit widgets below
```
Only ever moves widgets **down**, so `y` strictly increases and the recursion
terminates. The grid grows to fit. No global compaction — widgets stay where
the user puts them; gaps are allowed. (A future "Compact" button could pull
everything up.)

**Snap-to-grid.** Every committed position/size is integer cells. The drag
ghost previews the snapped result so the user sees where it will land.

**Save / Cancel.** Save persists the draft and re-renders the live view.
Cancel restores the pre-edit layout.

---

## Part 6 — Dynamic-height widgets (Search)

The **Search widget** changes its own height at runtime:
- Collapsed it is just a search input (`h` = 1 row — its persisted size).
- On a query it filters the cross-world + vendor rows (`FT.matchesSearch`) and
  renders the matches; the widget grows to fit the result rows and **pushes the
  widgets below it down**. Clearing the query collapses it back.

**Mechanism — effective layout.** The persisted layout never changes from a
runtime expansion. The live renderer computes an **effective layout**:
```
effective = persisted layout
for each widget reporting a runtime height override:
    set its effective h, then resolveCollisions downward
```
Re-derived whenever a widget reports a new height. A widget triggers this via
`FT.dashboard.requestHeight(type, rows)`.

This keeps expansion transient: reload, or clear the search, and the saved
layout reasserts. Any widget can use `requestHeight` later (e.g. a notes
widget that grows with content) — Search is just the first consumer.

In the **editor**, the Search widget is sized/placed like any other; only its
collapsed height is persisted.

---

## Part 7 — Backend

Minimal — the feature is almost entirely front-end.

- **No new endpoints required.** Widgets reuse existing ones:
  `/api/dashboard`, `/api/favorites/snapshot`, `/api/reliable/watchlist`,
  `/api/collectibles/{mounts,minions}`, `/api/history/top`,
  `/api/refresh/status`.
- **Fetch layer** in `dashboard.js`: map each enabled widget → its endpoint,
  fetch the deduped set once, hand each widget its slice. Mounts / minions /
  history are fetched **only when their widget is enabled**.
- **Notes** persist through the existing `ui_prefs` store — pref key
  `ffxiv-trader.dashboard.notes.v1`, debounced `FT.prefSet` on edit.
- Optional later: a single `/api/dashboard/bundle` that returns everything in
  one call, if the extra round-trips ever matter. Not needed for v1.

---

## Part 8 — Default layout & reset

A built-in `DEFAULT_DASHBOARD_LAYOUT` constant reproduces today's dashboard:
the 6 KPI widgets across the top row (2×2 each → 12 columns), then Reliable
watchlist, Top cross-world, Top vendor, Favorites, Maps stacked below at 6 or
12 wide. Mounts / minions / history / the new widgets default to **off**.

- Fresh install (no pref) → default layout.
- "Reset to default" in the editor → draft is replaced with the default
  (still needs Save to commit).

---

## Part 9 — Files

**New**
- `static/js/dashboard-grid.js` — grid math (snap, overlap, collision, free-slot).
- `static/js/dashboard-widgets.js` — widget registry + render functions.
- `static/js/dashboard-editor.js` — cog overlay + drag/resize/toggle.

**Changed**
- `static/dashboard.html` — cog button in `.page-head`; grid container; load
  the three new scripts.
- `static/js/dashboard.js` — rewritten as the live grid renderer.
- `static/css/app.css` — `.dash-widget`, grid canvas, cog reveal, editor
  overlay, wireframe tile, drag ghost, resize handle, toggle switch.
- `static/js/common.js` — expose a small `FT.dashboard` hook for
  `requestHeight` (Part 6), if not kept local to `dashboard.js`.

No Python changes (unless the optional bundle endpoint is added later).

---

## Implementation order

1. **Grid core** — `dashboard-grid.js`: data model, snap, overlap, collision,
   free-slot. Unit-testable in isolation (Node).
2. **Live render** — widget registry + `dashboard.js` rewrite; render the
   default layout from the grid; port the existing 11 widgets.
3. **New widgets** — mounts, minions, history, then the computed/utility ones.
4. **Editor overlay** — cog, overlay shell, left-panel toggles, wireframe
   canvas (no drag yet).
5. **Editor interactions** — move, resize, snap, collision, click-remove,
   draft + Save/Cancel + Reset.
6. **Search widget / dynamic height** — `requestHeight`, effective layout.
7. **Polish** — empty states, keyboard (`Esc` closes), reduced-motion.
8. **Test** (below).

## Testing checklist

- Cog hidden until the dashboard title is hovered; keyboard-reachable.
- Editor opens; left panel lists every widget with correct on/off state.
- Toggle a widget on → appears at the topmost free slot at default size.
- Toggle off / click its tile → removed; left panel reflects it.
- Drag a widget over others → they push down, never overlap; grid grows.
- Resize to cells; min sizes respected; snaps cleanly.
- Cancel discards every change; Save persists; reload keeps the saved layout.
- Reset to default restores the original arrangement.
- Live dashboard renders real content in the saved positions.
- Search widget: typing expands it and pushes widgets below; clearing
  collapses; the saved layout is unaffected after reload.
- Layout survives a server restart (persisted in `ui_prefs`).

---

## Assumptions (decided here — flag if any should change)

- **Cell size** — 12 columns, 40 px row unit, 14 px gap. One constant to tune.
- **Table widgets** show a compact 5-column preset and as many rows as fit
  their height; the full pages remain the place for full tables.
- **No global compaction** — moving a widget pushes others down only;
  resulting gaps are allowed and preserved.
- **One instance per widget type** — the left panel is on/off, not "add many".
- **Search expansion is transient** — runtime height changes never rewrite the
  persisted layout.
