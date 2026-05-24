# Reliable Trades — Automation Plan

A scoring + surfacing layer on top of the scanner. Goal: given history of every scan + live prices, produce a short list of trades with **statistically high probability** of profit.

Decisions are locked per your review (May 2026). See "Locked answers" section.

---

## Premise

The pipeline records every profitable opportunity to `history` at scan time. After running for days the table accumulates evidence for which items are *consistently* profitable vs ones that flickered profitable once.

A "reliable" trade is one supported by a **conditional claim**:
> *"In the last N days, this (item, quality) has been profitable in X% of scans, with median margin Y gil and median velocity Z/day, AND the current live listing is consistent with that pattern."*

Can't guarantee — listings change, undercuts happen, patches drop. We rank by **evidence + risk-adjusted score**.

---

## Industry techniques used

Researched and chosen for this problem:

### 1. Wilson Score Lower Bound — for `coverage` ranking
Standard technique for sorting items where you only have observed `successes / trials` from sparse data. Used by Reddit, Amazon for review ranking. Penalizes small-sample items naturally.

Given `s` successes (scans where item was profitable) and `n` total scans:

```
p_hat = s / n
z     = 1.96   # 95% confidence
denom = 1 + z²/n
center = (p_hat + z²/(2n)) / denom
margin = z * sqrt(p_hat*(1-p_hat)/n + z²/(4n²)) / denom
wilson_lb = center - margin
```

If only 1/1 scans were profitable, `p_hat=1.0` but Wilson lower bound is much lower (≈ 0.2) → rightly distrusted. If 80/100 scans → `wilson_lb ≈ 0.71`, trusted.

### 2. Sortino-style downside risk — for profit stability
Sharpe ratio penalizes ALL volatility (including upside surprises). For arbitrage, we only fear DOWNSIDE — profit dipping below our target. Sortino ratio:

```
downside_deviation = sqrt(mean(max(0, MAR - profit_i)²))   # MAR = min acceptable return
sortino = (mean(profit) - MAR) / downside_deviation
```

Where MAR = `MIN_RELIABLE_PROFIT_GIL` (e.g. 5000). Higher Sortino = more reliable margin.

### 3. James-Stein / Empirical Bayes shrinkage — for sparse profit estimates
When an item has few historical scans, shrink its observed mean toward the population mean (grand mean across all items in the same source). Reduces variance, prevents tiny-sample outliers from dominating.

```
shrunk_profit = (n * sample_mean + k * population_mean) / (n + k)
```

Where `k` ≈ effective sample size of the prior (tunable, e.g. 5).

### 4. Inventory turnover (velocity) — liquidity ceiling
Capped utility: above `TARGET_VELOCITY` (say 5/day) extra speed doesn't help — you can still only stock 20 slots per retainer. So:

```
liquidity = min(1, velocity / TARGET_VELOCITY)
```

### Sources

Plain English summaries baked into the formula above.

- [Wilson Score (Wikipedia)](https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval) — sparse-sample confidence interval, default ranking technique for "% positive" data
- [Sortino ratio (CME Group PDF)](https://www.cmegroup.com/education/files/rr-sortino-a-sharper-ratio.pdf) — downside-only risk adjustment
- [Shrinkage (Wikipedia)](https://en.wikipedia.org/wiki/Shrinkage_(statistics)) — bias-variance trade for small samples
- [Statistical Limit of Arbitrage (BFI/UChicago)](https://bfi.uchicago.edu/wp-content/uploads/2024/10/BFI_WP_2024-135.pdf) — why uncertainty alone keeps arbitrage opportunities alive
- [Inventory turnover primer (NetSuite)](https://www.netsuite.com/portal/resource/articles/inventory-management/inventory-turnover-primer-with-examples.shtml) — liquidity ratio basics

---

## Locked answers (per review)

| # | Question | Decision |
|---|---|---|
| 1 | Sources | **Both** (cross-world + vendor) |
| 2 | Quality | **Separate** HQ and NQ |
| 3 | Output | **Both** — short watchlist (5–10) on dashboard + long-form page |
| 4 | Confidence target | **Strict**: coverage ≥ 80%, appearances ≥ 30, cv_profit < 0.2 |
| 5 | Anomaly handling | **Drop** (current price outside historical band → excluded) |
| 6 | Trade horizon vs window | Trade target = **1-day flips**. Confidence window = **7 days** rolling |
| 7 | Auto-rescan | **Yes, 5-minute interval** (configurable via `.env`) |
| 8 | Min profit | **Stricter**: `MIN_RELIABLE_PROFIT_GIL=5000` (separate from existing `MIN_PROFIT_GIL=1000`) |
| 9 | Budget | **Reuse** existing budget setting |
| 10 | Confidence badges | **Yes** — High / Medium / Low |
| 11 | Color coding | **Yes** — row background tinted by confidence tier |
| 12 | Sparklines | **Yes** — mini chart of profit over window per row |
| 13 | Trade journal | **Skip** |
| 14 | Auto-favorite top N reliable | **Yes — opt-in setting** |

---

## Final reliability score

For each `(item_id, quality, source)` over the rolling 7-day window:

```
# Sample stats
n             = total scans in window
s             = scans where item appeared (profit > MIN_RELIABLE_PROFIT_GIL)
mean_profit   = AVG(profit) over s
std_profit    = STDDEV(profit) over s
mean_velocity = AVG(velocity)
cv_profit     = std_profit / max(mean_profit, 1)

# Wilson lower bound on coverage (95% CI)
wilson_lb     = wilson_lower_bound(s, n, z=1.96)

# Shrunk mean profit (toward population grand mean)
k             = 5    # prior pseudo-count
shrunk_profit = (s * mean_profit + k * grand_mean_profit) / (s + k)

# Downside deviation
MAR           = MIN_RELIABLE_PROFIT_GIL  # 5000
dd            = sqrt(mean(max(0, MAR - profit_i)² for i in s))
sortino       = (mean_profit - MAR) / max(dd, 1)

# Liquidity & freshness
liquidity     = min(1, mean_velocity / TARGET_VELOCITY)
freshness     = recent_24h_appearances / expected_24h_scans  # 0..1+

# Live overlay (must have current data point)
current_match = 1 if current opp exists AND inside historical band(p10..p90) else 0
```

```
score = wilson_lb * shrunk_profit * liquidity * freshness * sortino_factor * current_match

where sortino_factor = max(1, sortino) / 2   # mild scaling, never zeros out
```

### Confidence tier (UI badge + color)
```
HIGH   if wilson_lb >= 0.80 AND appearances >= 30 AND cv_profit < 0.2
MED    if wilson_lb >= 0.60 AND appearances >= 15 AND cv_profit < 0.4
LOW    if wilson_lb >= 0.40 AND appearances >= 10 AND cv_profit < 0.6
(else excluded entirely)
```

Strict mode (locked) = show **HIGH only by default**, with toggle to expand to MED/LOW.

---

## Required infrastructure

### New table: `scan_runs`
Tracks every scan completion so the `n` (total scans in window) denominator is known.

```sql
CREATE TABLE IF NOT EXISTS scan_runs (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,            -- 'cross-world' | 'vendor'
  started_at INTEGER NOT NULL,
  finished_at INTEGER NOT NULL,
  items_scanned INTEGER,
  items_profitable INTEGER,
  duration_ms INTEGER
);
CREATE INDEX idx_scan_runs_source_time ON scan_runs(source, finished_at);
```

`coverage_denominator = COUNT(*) FROM scan_runs WHERE source=? AND finished_at >= cutoff`

### Auto-rescan loop
- Background `asyncio` task: `await asyncio.sleep(AUTO_RESCAN_SECONDS)` then `scan_cross_world(force=True)` + `scan_vendor(force=True)`
- Configurable interval via `.env`: `AUTO_RESCAN_SECONDS=300` (default 5 min)
- Set `0` to disable
- Logged + safe to restart server (no overlapping scans thanks to existing scan locks)
- Each scan completion writes to `scan_runs`

### Rate-limit math sanity check
- Cross-world scan: ~50s, 168 requests
- Vendor scan: ~15s, 50 requests
- Combined run = ~65s, 218 requests per 5 minutes = ~0.73 req/s avg
- Well under the 20 req/s budget. Plenty of headroom for live `/aggregated`, icon redirects, etc.

### Item icons cache invalidation
Icon cache currently fetched once on startup. Game patches add new items. Auto-rescan should NOT refetch icons (slow + rarely changes). Manual "Rebuild icons" already exists in settings.

---

## API design

### `GET /api/reliable`

Query params:
- `days=7`
- `source=all|cross-world|vendor`
- `quality=both|hq|nq`
- `confidence=high|all` (default `high`)
- `top=20`
- `budget=N` (per-unit cap, reuse setting)

Response row:
```json
{
  "itemId": 5057,
  "name": "Iron Ingot",
  "icon_url": "/api/icon/5057",
  "quality": "hq",
  "source": "cross-world",

  // standard opportunity fields (current state):
  "buy_world": "Zodiark", "buy_price": 150,
  "sell_world": "Odin",   "sell_price": 399,
  "profit": 229, "roi_pct": 152.67,
  "velocity": 0.8, "profit_per_day": 183.2,
  "buy_upload_ts": ..., "sell_upload_ts": ...,

  // reliability extras:
  "appearances": 28, "total_scans": 32,
  "wilson_lb": 0.78,
  "mean_profit": 215, "shrunk_profit": 211, "std_profit": 14, "cv_profit": 0.065,
  "mean_velocity": 0.78,
  "sortino": 4.2,
  "price_band": {"buy_p10": 142, "buy_p90": 168, "sell_p10": 385, "sell_p90": 420},
  "is_anomaly": false,
  "score": 23408.5,
  "confidence": "high",

  // sparkline data:
  "profit_series": [220, 215, 218, 210, 225, 219, ...]  // last N points
}
```

### `GET /api/reliable/watchlist`
Top 5 across all sources, for the dashboard.

---

## Frontend

### New page `/reliable.html`
- Same shared table layout
- New columns: **Confidence** (badge) · **Score** · **Coverage** (`s/n` + %) · **Mean Profit** · **CV** · **Sortino** · **Spark**
- Row background tinted: high=`rgba(6,214,160,.07)`, med=`rgba(255,209,102,.07)`, low=`rgba(239,71,111,.07)`
- Confidence filter dropdown (default High)
- Sparkline: SVG, ~80×20px, single line of `profit_series`
- All standard chrome: star, rescan button, wiki link, icon

### Dashboard section
- "Reliable watchlist (top 5)" small table at top
- Each row click → link to reliable page filtered to that item

### Settings additions
- New section "Reliable scoring":
  - `Reliable min profit` (gil) — overrides `MIN_RELIABLE_PROFIT_GIL` per-client
  - `Auto-favorite top N reliable` (count, default 0 = off)
- Existing "Rebuild caches" already there

### .env additions
```
AUTO_RESCAN_SECONDS=300       # 0 disables
MIN_RELIABLE_PROFIT_GIL=5000  # MAR for Sortino + filter
RELIABLE_WINDOW_DAYS=7
TARGET_VELOCITY=5             # sales/day saturation cap
```

---

## Phases

### R1 — Data foundation
- `scan_runs` table schema (in `core/db.py`)
- Record run start/end in `scan_cross_world` / `scan_vendor`
- Auto-rescan background task in lifespan (`AUTO_RESCAN_SECONDS`)
- New `.env` keys

**Acceptance**: server boots, `scan_runs` populating every 5 min, `_scan_cache` updating, no duplicate scans (locks honored)

### R2 — Scoring service
- `services/reliable.py` — Wilson LB, shrinkage, Sortino, score
- Pull from `history` + `scan_runs` + current `_scan_cache` (live overlay)
- Compute population stats once per request (cache for 60s)

**Acceptance**: function returns ranked list with all expected fields for a known item

### R3 — API
- `GET /api/reliable` with all params + response shape
- `GET /api/reliable/watchlist` for dashboard
- Surface `profit_series` for sparkline

**Acceptance**: endpoint returns rows with confidence tiers correctly assigned

### R4 — UI
- `static/reliable.html` + `js/reliable.js`
- Sparkline component (pure SVG)
- Color-coded rows + badges
- Add nav link + dashboard section

**Acceptance**: page renders ranked list, sparklines draw, badges visible, color tint applied

### R5 — Polish + safety nets
- "Collecting data — try again in 24h" empty state if `n < 12`
- Auto-favorite top N option
- Stretch: a "Why is this reliable?" tooltip explaining the score components per-row

---

## Caveats

- **Initial sparseness**: first 24h has too few scan_runs for any item to clear HIGH thresholds. UI must communicate this. After ~7 days, scoring stabilizes.
- **Survivorship in history**: only profitable rows recorded → coverage_pct can be inflated for items that bounce around the MIN_PROFIT threshold. Mitigation: also record near-miss items? (DB cost trade-off. Skipping for now; revisit if scores are wrong in practice.)
- **Tax math drift**: changing TAX_CITY in settings recomputes display-side only. Historical profit stored at scan-time tax. For the `mean_profit` aggregate this is fine since tax is fairly stable (3% or 5% only). Note in UI: "scores computed against last-scan tax."
- **Auto-rescan + Universalis ToS**: 218 req per 5 min = 0.73/s. Well under the 25 req/s limit. User-Agent unchanged, identifying as ffxiv-trader.
- **Game patches**: a major patch may invalidate historical patterns (e.g. new items spawn, old ones change uses). User can manually wipe history if scores feel wrong: `DELETE FROM history; DELETE FROM scan_runs;` then wait 7 days. Consider adding a "wipe stats" button in Settings → cache section.

---

## Out of scope (do not build)

- Game-client integration / auto-buying / auto-listing
- Predicting future game patches
- Per-character undercut detection
- Cross-DC trading (game restriction)
- WebSocket subscriptions
