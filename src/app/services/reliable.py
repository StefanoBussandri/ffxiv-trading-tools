import logging
import math
import time
from typing import Any

from app.core.config import settings
from app.services.opportunities import _cached, _icon_url, _load_items
from app.services.sale_history import fetch as fetch_history

log = logging.getLogger("reliable")

Z_95 = 1.96
SHRINKAGE_K = 5

CONFIDENCE_HIGH = {"wilson_lb": 0.70, "successes": 20, "cv_profit": 0.25}
CONFIDENCE_MED = {"wilson_lb": 0.55, "successes": 12, "cv_profit": 0.45}
CONFIDENCE_LOW = {"wilson_lb": 0.35, "successes": 8, "cv_profit": 0.70}


def wilson_lower_bound(s: int, n: int, z: float = Z_95) -> float:
    if n <= 0:
        return 0.0
    s_eff = min(s, n)
    p = s_eff / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    margin = z * math.sqrt(max(0.0, p * (1.0 - p) / n + z * z / (4.0 * n * n))) / denom
    return max(0.0, center - margin)


def _confidence_tier(wilson_lb: float, successes: int, cv: float) -> str | None:
    if (wilson_lb >= CONFIDENCE_HIGH["wilson_lb"]
            and successes >= CONFIDENCE_HIGH["successes"]
            and cv < CONFIDENCE_HIGH["cv_profit"]):
        return "high"
    if (wilson_lb >= CONFIDENCE_MED["wilson_lb"]
            and successes >= CONFIDENCE_MED["successes"]
            and cv < CONFIDENCE_MED["cv_profit"]):
        return "medium"
    if (wilson_lb >= CONFIDENCE_LOW["wilson_lb"]
            and successes >= CONFIDENCE_LOW["successes"]
            and cv < CONFIDENCE_LOW["cv_profit"]):
        return "low"
    return None


def _percentile(sorted_vals: list[float], pct: float) -> float | None:
    if not sorted_vals:
        return None
    idx = max(0, min(len(sorted_vals) - 1, int(round(pct / 100 * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def _score_row(opp: dict, hist: dict, tax: float, mar: int, window_days: int) -> dict | None:
    quality = opp["quality"]
    is_hq = quality == "hq"
    entries = hist.get("entries", []) or []
    q_entries = [e for e in entries if bool(e.get("hq")) == is_hq]
    n = len(q_entries)
    if n == 0:
        return None

    buy = opp.get("buy_price")
    if not buy or buy <= 0:
        return None

    profits = [int(e["pricePerUnit"] * (1 - tax) - buy) for e in q_entries]
    quantities = [max(int(e.get("quantity") or 1), 1) for e in q_entries]
    total_qty = sum(quantities)
    successes = sum(1 for p in profits if p >= mar)
    p_hat = successes / n if n else 0
    wilson_lb = wilson_lower_bound(successes, n)

    # VWAP profit: volume-weighted mean of profitable sales (stacks count more).
    success_pairs = [(p, q) for p, q in zip(profits, quantities) if p >= mar]
    if success_pairs:
        success_qty = sum(q for _, q in success_pairs)
        vwap_profit = sum(p * q for p, q in success_pairs) / success_qty
        unweighted_mean_profit = sum(p for p, _ in success_pairs) / len(success_pairs)
    else:
        vwap_profit = 0.0
        unweighted_mean_profit = 0.0

    # Volume-weighted moments over all sales for variance/cv.
    weighted_mean_all = sum(p * q for p, q in zip(profits, quantities)) / total_qty
    var_all = sum(((p - weighted_mean_all) ** 2) * q for p, q in zip(profits, quantities)) / total_qty
    std_profit = math.sqrt(max(0.0, var_all))
    cv = std_profit / max(abs(vwap_profit), 1.0) if vwap_profit else float("inf")

    downside_sq = sum(((mar - p) ** 2) * q for p, q in zip(profits, quantities) if p < mar) / total_qty
    downside_dev = math.sqrt(downside_sq)
    sortino = ((vwap_profit - mar) / downside_dev) if downside_dev > 0 else (
        1.0 if vwap_profit > mar else 0.0
    )

    tier = _confidence_tier(wilson_lb, successes, cv)
    if tier is None:
        return None

    # Velocity by quality (sales/day)
    if quality == "hq":
        velocity = hist.get("hqSaleVelocity") or 0
    else:
        velocity = hist.get("nqSaleVelocity") or 0
    liquidity = min(1.0, velocity / max(settings.TARGET_VELOCITY, 0.01))

    # Demand-pressure multiplier on liquidity (units sold / units for sale).
    # >1 = market burns through inventory; <1 = oversupplied.
    demand_pressure = opp.get("demand_pressure")
    if demand_pressure is not None:
        dp_factor = max(0.5, min(2.0, float(demand_pressure)))
        liquidity = min(1.5, liquidity * dp_factor)

    # Sortino factor squashes range
    sortino_factor = max(0.5, min(3.0, (sortino + 2.0) / 2.0))

    # Price band
    sale_prices = sorted(int(e["pricePerUnit"]) for e in q_entries)
    band = {
        "p10": _percentile(sale_prices, 10),
        "p50": _percentile(sale_prices, 50),
        "p90": _percentile(sale_prices, 90),
    }

    # Mean-reversion z-score on buy_price vs historical sale-price distribution.
    # Negative z = buying below mean = bargain = score boost.
    price_mean = sum(sale_prices) / len(sale_prices)
    price_var = sum((p - price_mean) ** 2 for p in sale_prices) / len(sale_prices)
    price_std = math.sqrt(max(0.0, price_var))
    z_score = ((buy - price_mean) / price_std) if price_std > 0 else 0.0
    mr_factor = max(0.5, min(1.5, 1.0 - z_score * 0.2))

    # Anomaly: current sell listing way outside band
    sell_price = opp.get("sell_price")
    is_anomaly = False
    if sell_price and band["p10"] is not None and band["p90"] is not None:
        if sell_price < band["p10"] * 0.5 or sell_price > band["p90"] * 2.0:
            is_anomaly = True

    score = wilson_lb * vwap_profit * liquidity * sortino_factor * mr_factor
    last_sale = max((int(e.get("timestamp") or 0) for e in q_entries), default=0)

    row = dict(opp)
    home_profit_per_day = (
        round(opp["profit"] * velocity, 2)
        if opp.get("profit") is not None and velocity
        else None
    )
    row.update({
        "velocity": round(velocity, 3),
        "profit_per_day": home_profit_per_day,
        "successes": successes,
        "sales_total": n,
        "units_total": total_qty,
        "wilson_lb": round(wilson_lb, 4),
        "p_hat": round(p_hat, 4),
        "vwap_profit": round(vwap_profit, 2),
        "mean_profit": round(vwap_profit, 2),  # back-compat alias
        "unweighted_mean_profit": round(unweighted_mean_profit, 2),
        "std_profit": round(std_profit, 2),
        "cv_profit": round(cv, 4) if math.isfinite(cv) else None,
        "mean_velocity": round(velocity, 3),
        "downside_dev": round(downside_dev, 2),
        "sortino": round(sortino, 3),
        "price_band": band,
        "price_mean": round(price_mean, 2),
        "price_std": round(price_std, 2),
        "z_score": round(z_score, 3),
        "mr_factor": round(mr_factor, 3),
        "is_anomaly": is_anomaly,
        "score": round(score, 2),
        "confidence": tier,
        "profit_series": profits,
        "last_sale_ts": last_sale * 1000,
        "appearances": successes,
        "total_scans": n,
    })
    return row


COMMODITY_MIN_VELOCITY = 20.0
COMMODITY_MAX_MARGIN_PCT = 15.0


async def compute_reliable(
    *,
    days: int | None = None,
    sources: list[str] | None = None,
    quality: str = "both",
    confidence: str = "high",
    top: int = 50,
    budget: int | None = None,
    include_series: bool = True,
    commodity: bool = False,
    stale_only: bool = False,
    bargain_only: bool = False,
) -> dict[str, Any]:
    days = days or settings.RELIABLE_WINDOW_DAYS
    sources = sources or ["cross-world", "vendor"]
    mar = settings.MIN_RELIABLE_PROFIT_GIL
    tax_rates = (
        __import__("app.core.cache", fromlist=["read"]).read("tax_rates") or {}
    )
    tax = float(tax_rates.get(settings.TAX_CITY) or 0) / 100.0

    candidates: list[dict] = []
    for src in sources:
        rows = _cached(src) or []
        candidates.extend(rows)

    if quality in ("hq", "nq"):
        candidates = [c for c in candidates if c["quality"] == quality]
    if budget:
        candidates = [c for c in candidates if c.get("buy_price") and c["buy_price"] <= budget]
    if commodity:
        candidates = [
            c for c in candidates
            if (c.get("velocity") or 0) >= COMMODITY_MIN_VELOCITY
            and (c.get("roi_pct") or 0) <= COMMODITY_MAX_MARGIN_PCT
        ]
    if stale_only:
        candidates = [c for c in candidates if c.get("stale_listing")]
    # Note: bargain_only on reliable filters on z_score post-scoring (below).

    if not candidates:
        return {
            "rows": [],
            "count": 0,
            "window_days": days,
            "ts": int(time.time() * 1000),
            "ready": False,
            "reason": "No live opportunities right now — waiting for scans to populate.",
        }

    item_ids = sorted({int(c["itemId"]) for c in candidates})
    histories = await fetch_history(item_ids, window_days=days)

    items_by_id = _load_items()
    out: list[dict] = []
    for opp in candidates:
        h = histories.get(int(opp["itemId"]))
        if not h:
            continue
        scored = _score_row(opp, h, tax, mar, days)
        if not scored:
            continue
        if scored["is_anomaly"]:
            continue
        if confidence == "high" and scored["confidence"] != "high":
            continue
        if confidence == "medium" and scored["confidence"] not in ("high", "medium"):
            continue
        if bargain_only and (scored.get("z_score") or 0) >= -1:
            continue
        scored["name"] = items_by_id.get(int(scored["itemId"]), str(scored["itemId"]))
        scored["icon_url"] = _icon_url(int(scored["itemId"]))
        if not include_series:
            scored.pop("profit_series", None)
        out.append(scored)

    out.sort(key=lambda r: r["score"], reverse=True)
    return {
        "rows": out[:top],
        "count": len(out),
        "window_days": days,
        "ts": int(time.time() * 1000),
        "ready": True,
        "min_reliable_profit_gil": mar,
        "tax_pct": round(tax * 100, 3),
        "candidates": len(candidates),
        "histories_fetched": len(histories),
    }
