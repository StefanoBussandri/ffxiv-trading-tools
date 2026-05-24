# Trade Signals Upgrade Plan

Add richer market signals derived from already-fetched Universalis data, then
extend to listing-depth fields, and feed them into the reliability score.

## Scope

### Kept

**FFXIV-specific:**
1. Undercut tracking — listings depth + undercut gap (needs `/currentlyShown`).
2. Commodity flip filter — surface high-velocity, low-margin items (crystals, mats).
3. Stale listing flag — top listing's `lastReviewTime` > 7d (needs `/currentlyShown`).

**Reliability-score boosters:**
1. VWAP-weighted mean profit — weight sales by quantity, not flat mean.
2. Order-flow imbalance — `unitsSold / unitsForSale` as liquidity multiplier.
3. Mean-reversion z-score — buy price below historical mean = score boost.

**Derived columns (score-feeding only):**
- `spread_pct` — (min listing − recent purchase) / recent purchase
- `z_score` — current buy vs history mean/std
- `demand_pressure` — unitsSold / unitsForSale
- `undercut_gap` — (2nd cheapest − min) / min
- `top_depth` — qty in cheapest listing

### Dropped

- Patch-day flips, pre-patch hoarding, glamour/seasonal (needs calendar)
- Region/cross-DC (DC only)
- Crafting profit (needs recipe data)
- Dead-listing rotation (too involved)
- Stop-loss + diversification (needs portfolio tracking)

## Universalis fields used vs unused

Currently used from `/aggregated`:
- `minListing.world.price` → sell_price
- `minListing.dc.price` + `worldId` → buy_price + buy_world
- `dailySaleVelocity.world.quantity` → velocity (post-fix)
- `worldUploadTimes` → freshness

Currently unused but free (already in response):
- `medianListing.world.price` / `medianListing.dc.price`
- `averageSalePrice.world.price` / `averageSalePrice.dc.price`
- `recentPurchase.world.price` / `recentPurchase.world.timestamp`

Requires `/currentlyShown` endpoint (extra calls):
- `listings[].pricePerUnit`, `quantity`, `lastReviewTime`, `retainerName`, `worldName`
- `unitsForSale`, `unitsSold`
- `stackSizeHistogram`

## Implementation phases

### Phase 1 — exploit existing /aggregated fields (no new API calls)

Extract median, average sale price, recent purchase from already-fetched
aggregated payload. Compute spread_pct. Persist to DB. Expose in frontend.

**Tasks:**

1. Extend `_row_from_aggregated` in `src/app/services/opportunities.py`:
   - Pull `medianListing.world.price` → `median_listing`
   - Pull `averageSalePrice.world.price` → `avg_sale_price`
   - Pull `recentPurchase.world.price` → `recent_purchase_price`
   - Pull `recentPurchase.world.timestamp` → `recent_purchase_ts`
   - Compute `spread_pct = (sell_price - recent_purchase_price) / recent_purchase_price` when both present
2. Repeat for vendor scan, maps, favorites snapshot.
3. Add columns to `history` table:
   - `median_listing INTEGER`
   - `avg_sale_price REAL`
   - `recent_purchase_price INTEGER`
   - `recent_purchase_ts INTEGER`
   - `spread_pct REAL`
4. Update `record_opportunities` + `cached_rows_from_db` to round-trip new fields.
5. Update API response shape (no new endpoints).
6. Frontend: new sortable columns (`spread_pct`, `recent_purchase_ts`) on
   relevant tables. Keep optional/collapsible.

### Phase 2 — reliability score upgrade

Use Phase 1 fields + per-entry quantity for VWAP. No new API calls.

**Tasks in `src/app/services/reliable.py`:**

1. VWAP mean profit:
   ```
   weights = [e.get("quantity", 1) for e in q_entries]
   vwap_profit = sum(p * w for p, w in zip(profits, weights)) / sum(weights)
   ```
   Replace `mean_profit` use in score and confidence tier check with VWAP.
2. Mean-reversion z-score:
   ```
   price_mean = sum(sale_prices) / len(sale_prices)
   price_std = sqrt(variance(sale_prices))
   z = (buy_price - price_mean) / price_std if price_std else 0
   mr_factor = clamp(1.0 - z * 0.2, 0.5, 1.5)
   ```
3. Updated formula:
   ```
   score = wilson_lb * vwap_profit * liquidity * sortino_factor * mr_factor
   ```
4. Surface `vwap_profit`, `z_score`, `mr_factor` in response for transparency.

### Phase 3 — /currentlyShown endpoint integration

Adds listing-depth fields. Expensive — gate to enrichment of already-filtered
candidates, not all marketable items.

**Tasks:**

1. `UniversalisClient.get_currently_shown(scope, item_ids, *, listings=10, entries=0)`
   in `src/app/clients/universalis.py`. Use `fields` query param to slim payload:
   `items.listings.pricePerUnit,items.listings.quantity,items.listings.lastReviewTime,items.unitsForSale,items.unitsSold`.
2. New enrichment step after opportunity scan: call `/currentlyShown` for top
   N candidates only (cap at 500, chunks of 100). Cache per item with 60s TTL.
3. Derive:
   - `top_depth` = listings[0].quantity
   - `undercut_gap` = (listings[1].price - listings[0].price) / listings[0].price
   - `stale_listing` = (now - listings[0].lastReviewTime) > 7d
   - `demand_pressure` = unitsSold / max(unitsForSale, 1)
4. Feed `demand_pressure` into reliable score:
   ```
   liquidity *= clamp(demand_pressure, 0.5, 2.0)
   ```
5. Commodity filter mode: API param to show only items where
   `velocity > 20 and margin_pct < 0.15`.

### Phase 4 — frontend

1. New columns + filters across `static/js/*.js`:
   - `spread_pct`, `z_score`, `top_depth`, `undercut_gap` (numeric, sortable)
   - Stale badge on rows
2. Filter chips: "Commodity mode", "Stale listings only", "Bargain (z<−1)".
3. Reliable page: show `vwap_profit` next to `mean_profit` for diagnostic.

## Suggested execution order

Phase 1 → Phase 2 → Phase 4 (partial, expose Phase 1+2 fields) → Phase 3
→ Phase 4 (finish).

Rationale: Phases 1+2 are free (no extra API cost) and immediately improve
reliable-score quality. Phase 3 unlocks bigger signals but requires API budget
discipline.

## Out of scope / future

- Portfolio tracker: enables stop-loss, position sizing, diversification metrics,
  bagholding alarms, real P&L.
- Crafting profit: needs recipe data ingest from XIVAPI or game data dump.
- Patch-day demand modeling: needs patch calendar + label training data.
