# =============================================================================
# score.py — Step 4: Compute composite scores & rank all instruments
#
# Reads  : signals_etf.json / signals_stock.json + macro.json + news.json
# Writes : scores_etf.json  / scores_stock.json
#
# Two scoring strategies:
#   etf   → Mean-reversion: buy oversold ETFs (RSI < 38, vol spike)
#   stock → Momentum pullback: buy quality stocks dipping to EMA21
#
# Usage:
#   python scripts/score.py --mode etf    (default)
#   python scripts/score.py --mode stock
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import json
import logging

from config import (
    get_mode_config,
    MACRO_CACHE, NEWS_CACHE,
    WATCHLIST, STOCK_DELIVERY_WATCHLIST,
    VIX_THRESHOLDS,
    STOCK_SECTOR_MAP, SECTOR_UNDERPERFORM_THRESHOLD,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Score and rank instruments")
    parser.add_argument(
        "--mode", choices=["etf", "stock"], default="etf",
        help="etf = ETF/MF swing corpus | stock = delivery corpus"
    )
    return parser.parse_args()


# ===========================================================================
# ── MODE A: ETF SWING SIGNAL CONVERTERS  (all return [-1.0, +1.0]) ────────
# ===========================================================================

def _rsi_etf_signal(rsi: float) -> float:
    """Lower RSI = more oversold = higher score (mean-reversion logic)."""
    if rsi < 20:   return  1.00   # Extremely oversold
    if rsi < 30:   return  0.85
    if rsi < 35:   return  0.65
    if rsi < 38:   return  0.40
    if rsi < 45:   return  0.15
    if rsi < 55:   return  0.00   # Neutral
    if rsi < 62:   return -0.20
    if rsi < 70:   return -0.55
    return                -1.00   # Extremely overbought


def _ema_etf_signal(sig: dict) -> float:
    """EMA alignment & fresh crossovers (ETF swing)."""
    e9_above_21  = sig["ema9_above_ema21"]
    e21_above_50 = sig["ema21_above_ema50"]
    fresh_bull   = sig["fresh_bullish_cross"]
    fresh_bear   = sig["fresh_bearish_cross"]

    if fresh_bull:                        return  0.90   # Brand-new cross — highest conviction
    if fresh_bear:                        return -0.90
    if e9_above_21 and e21_above_50:      return  0.70   # Full bullish alignment
    if e9_above_21:                       return  0.25   # Short-term only
    if e21_above_50:                      return -0.25   # Medium ok but short-term broke
    return                                       -0.70   # Full bearish alignment


def _bollinger_etf_signal(sig: dict) -> float:
    """Price position relative to Bollinger Bands (mean-reversion for ETFs)."""
    price    = sig["current_price"]
    bb_lower = sig["bb_lower"]
    bb_mid   = sig["bb_mid"]
    bb_upper = sig["bb_upper"]

    if price < bb_lower:                              return  1.00   # Below lower band → oversold
    if price < bb_lower + 0.25 * (bb_mid - bb_lower): return  0.50
    if price < bb_mid:                                return  0.15
    if price < bb_mid + 0.5 * (bb_upper - bb_mid):   return -0.10
    if price < bb_upper:                              return -0.40
    return                                                   -1.00   # Above upper → overbought


def _volume_etf_signal(zscore: float) -> float:
    """Volume confirmation — high Z-score validates ETF breakout/breakdown."""
    if zscore >  3.0:  return  1.00
    if zscore >  2.0:  return  0.75
    if zscore >  1.5:  return  0.50
    if zscore >  0.5:  return  0.10
    if zscore > -0.5:  return  0.00   # Normal — neutral
    return                     -0.20  # Drying up volume — weakens thesis


# ===========================================================================
# ── MODE B: STOCK DELIVERY SIGNAL CONVERTERS ──────────────────────────────
# ===========================================================================

def _rsi_stock_signal(rsi: float) -> float:
    """
    Momentum pullback — sweet spot is RSI 42–55 (healthy dip, not breakdown).
    Penalise oversold (< 38) — that's a falling knife for individual stocks.
    """
    if rsi < 30:   return -0.80   # Falling knife — avoid
    if rsi < 38:   return -0.30   # Possibly broken — weak
    if rsi < 42:   return  0.10   # Approaching pullback zone
    if rsi < 50:   return  1.00   # Perfect pullback zone (sweet spot)
    if rsi < 55:   return  0.70   # Still good
    if rsi < 62:   return  0.10   # Getting stretched — wait
    if rsi < 70:   return -0.40   # Overbought — wait for pullback
    return                -1.00   # Very overbought — avoid chasing


def _ema_stock_signal(sig: dict) -> float:
    """
    Full EMA alignment required for delivery.
    EMA9 > EMA21 > EMA50 = full uptrend. Price pulling back below EMA9
    but EMA21 still above EMA50 = classic entry zone.
    """
    e9_above_21  = sig["ema9_above_ema21"]
    e21_above_50 = sig["ema21_above_ema50"]
    fresh_bull   = sig["fresh_bullish_cross"]
    fresh_bear   = sig["fresh_bearish_cross"]

    if fresh_bear:                            return -1.00   # Trend breaking — exit signal
    if e9_above_21 and e21_above_50:          return  1.00   # Full uptrend — best
    if e21_above_50 and not e9_above_21:      return  0.70   # Pulling back within uptrend (entry zone!)
    if fresh_bull:                            return  0.40   # Fresh cross — watch EMA50 confirmation
    if e9_above_21 and not e21_above_50:      return -0.20   # Possible recovery but medium-term weak
    return                                            -0.80   # Full bearish — avoid


def _pullback_stock_signal(sig: dict) -> float:
    """
    Is price in the EMA21 pullback zone?
    Best entry: price is within ±4% of EMA21, still above EMA50.
    Penalise: extended above EMA21 (don't chase) or broken below EMA50.
    """
    price = sig["current_price"]
    ema21 = sig["ema21"]
    ema50 = sig["ema50"]

    if price < ema50:
        return -1.00   # EMA50 broken — trend compromised

    # Distance from EMA21 (positive = above EMA21, negative = below)
    dist = sig.get("ema21_proximity_pct", (price - ema21) / ema21)

    if -0.02 <= dist <= 0.01:   return  1.00   # Right at EMA21 — perfect pullback
    if -0.04 <= dist < -0.02:   return  0.70   # Slightly below EMA21 — still fine
    if  0.01 < dist <= 0.03:    return  0.60   # Just above EMA21 — beginning to pull back
    if  0.03 < dist <= 0.07:    return  0.10   # Well above EMA21 — wait for dip
    if  dist > 0.07:            return -0.40   # Extended — don't chase
    return                              -0.60   # Too far below EMA21


def _volume_stock_signal(zscore: float) -> float:
    """
    Calm volume = healthy pullback (smart money not panicking).
    High volume on a dip = aggressive selling = danger for delivery.
    """
    if zscore >  3.0:  return -0.80   # Very high volume on dip = distribution / panic
    if zscore >  2.0:  return -0.40   # Elevated — caution
    if zscore >  1.5:  return -0.10   # Slightly elevated — minor concern
    if zscore >  0.5:  return  0.80   # Normal-calm — ideal pullback volume
    if zscore > -0.5:  return  0.60   # Below average — volume drying up = stabilising
    return                     0.20   # Very low volume — thin / stale stock


# ===========================================================================
# ── Category lookup ────────────────────────────────────────────────────────
# ===========================================================================

def _get_category(ticker: str, mode: str) -> str:
    watchlist = WATCHLIST if mode == "etf" else STOCK_DELIVERY_WATCHLIST
    for cat, tickers in watchlist.items():
        if ticker in tickers:
            return cat
    return "unknown"


# ===========================================================================
# ── Composite scorer ────────────────────────────────────────────────────────
# ===========================================================================

def compute_composite(
    ticker: str,
    signals: dict,
    macro_data: dict,
    news_data: dict | None,
    mode: str = "etf",
    cfg: dict | None = None,
) -> dict:
    """
    Returns a full scoring dict including:
      - composite_score   : [-100, +100]
      - meets_entry       : bool (all entry conditions satisfied)
      - entry_conditions  : dict of individual condition results
      - component_scores  : individual signal values
    """
    sig      = signals[ticker]
    weights  = cfg["weights"] if cfg else {}
    entry_rules = cfg["entry_rules"] if cfg else {}
    category = _get_category(ticker, mode)

    # Macro signal (shared)
    macro_sig  = 0.0
    vix_factor = 1.0
    if macro_data and "_signal" in macro_data:
        macro_sig  = macro_data["_signal"]["score"]
        vix_factor = macro_data["_signal"]["vix_factor"]

    # News sentiment (shared)
    news_sig = 0.0
    if news_data and "ticker_sentiment" in news_data:
        news_sig = news_data["ticker_sentiment"].get(ticker, {}).get("score", 0.0)

    # ── Compute individual components ────────────────────────────────────────
    if mode == "stock":
        rsi_sig  = _rsi_stock_signal(sig["rsi"])
        ema_sig  = _ema_stock_signal(sig)
        pull_sig = _pullback_stock_signal(sig)
        vol_sig  = _volume_stock_signal(sig["volume_zscore"])

        raw = (
            weights.get("rsi",       0.20) * rsi_sig  +
            weights.get("ema_cross", 0.30) * ema_sig  +
            weights.get("pullback",  0.25) * pull_sig +
            weights.get("volume",    0.15) * vol_sig  +
            weights.get("news",      0.05) * news_sig +
            weights.get("macro",     0.05) * macro_sig
        )
        composite = raw * 100.0

        # ── Stock-specific adjustments ───────────────────────────────────────
        # Bonus for EMA9 freshly crossing up into EMA21 (high-conviction entry)
        if sig.get("fresh_bullish_cross") and sig.get("ema21_above_ema50"):
            composite += 10.0   # Fresh cross + trend intact = strong signal

        # Penalty: broken EMA50 support
        if not sig.get("above_ema50"):
            composite -= 20.0   # Hard penalty — trend broken

        # ── Entry conditions for stock delivery ──────────────────────────────
        rsi_val = sig["rsi"]

        # Nifty 20-EMA hard gate
        nifty_trend_ok = True
        if entry_rules.get("require_nifty_trend", False):
            nifty_trend_ok = macro_data.get("_signal", {}).get("nifty_above_ema20", True)

        # Sector relative strength gate
        sector_ok = True
        if entry_rules.get("require_sector_strength", False):
            sector_key = STOCK_SECTOR_MAP.get(ticker)
            if sector_key and sector_key != "nifty":
                sector_data = macro_data.get("_sector_data", {})
                sdata = sector_data.get(sector_key)
                if sdata and "relative_to_nifty" in sdata:
                    sector_ok = sdata["relative_to_nifty"] >= SECTOR_UNDERPERFORM_THRESHOLD

        entry_conditions = {
            "rsi_pullback_zone": (
                entry_rules.get("rsi_pullback_min", 42) <= rsi_val <=
                entry_rules.get("rsi_pullback_max", 55)
            ),
            "ema21_above_ema50":  sig["ema21_above_ema50"],
            "price_near_ema21":   sig.get("price_near_ema21", False),
            "volume_calm":        sig["volume_zscore"] <= entry_rules.get("volume_zscore_max", 2.0),
            "score_sufficient":   composite >= entry_rules.get("min_composite_score", 50),
            "nifty_trend_ok":     nifty_trend_ok,
            "sector_strength_ok": sector_ok,
        }

        component_scores = {
            "rsi_signal":      round(rsi_sig,  3),
            "ema_signal":      round(ema_sig,  3),
            "pullback_signal": round(pull_sig, 3),
            "volume_signal":   round(vol_sig,  3),
            "news_signal":     round(news_sig, 3),
            "macro_signal":    round(macro_sig, 3),
        }

    else:  # ETF mode
        rsi_sig = _rsi_etf_signal(sig["rsi"])
        ema_sig = _ema_etf_signal(sig)
        bb_sig  = _bollinger_etf_signal(sig)
        vol_sig = _volume_etf_signal(sig["volume_zscore"])

        raw = (
            weights.get("rsi",       0.25) * rsi_sig  +
            weights.get("ema_cross", 0.25) * ema_sig  +
            weights.get("bollinger", 0.15) * bb_sig   +
            weights.get("volume",    0.15) * vol_sig  +
            weights.get("news",      0.10) * news_sig +
            weights.get("macro",     0.10) * macro_sig
        )
        composite = raw * 100.0

        # ── ETF-specific adjustments ─────────────────────────────────────────
        if category == "etf_international":
            usd_data = macro_data.get("usd_inr") if macro_data else None
            if usd_data and usd_data.get("pct_change", 0) > 0.20:
                composite += 5.0
            if macro_sig < -0.3:
                composite -= 10.0

        if ticker == "OILIETF.NS" and macro_data:
            crude = macro_data.get("crude_oil")
            if crude:
                composite += crude["pct_change"] * 2.0

        if sig.get("fresh_bullish_cross"):
            composite += 8.0

        # ── Entry conditions for ETF swing ───────────────────────────────────
        entry_conditions = {
            "rsi_oversold":     sig["rsi"] < entry_rules.get("rsi_oversold_threshold", 38),
            "above_ema50":      sig["above_ema50"],
            "volume_confirmed": sig["volume_zscore"] >= entry_rules.get("volume_zscore_threshold", 1.5),
            "score_sufficient": composite >= entry_rules.get("min_composite_score", 40),
        }

        component_scores = {
            "rsi_signal":    round(rsi_sig,  3),
            "ema_signal":    round(ema_sig,  3),
            "bb_signal":     round(bb_sig,   3),
            "volume_signal": round(vol_sig,  3),
            "news_signal":   round(news_sig, 3),
            "macro_signal":  round(macro_sig, 3),
        }

    # Clamp
    composite = max(-100.0, min(100.0, composite))

    meets_entry = all(entry_conditions.values())

    return {
        "ticker":           ticker,
        "category":         category,
        "composite_score":  round(composite, 2),
        "meets_entry":      meets_entry,
        "vix_factor":       vix_factor,
        "entry_conditions": entry_conditions,
        "component_scores": component_scores,
    }


# ===========================================================================
# ── MAIN ────────────────────────────────────────────────────────────────────
# ===========================================================================

def main():
    args = parse_args()
    cfg  = get_mode_config(args.mode)

    for path in [cfg["signals_cache"], MACRO_CACHE]:
        if not os.path.exists(path):
            logger.critical(f"Required file missing: {path}")
            sys.exit(1)

    with open(cfg["signals_cache"], "r") as f:
        signals = json.load(f)

    with open(MACRO_CACHE, "r") as f:
        macro_data = json.load(f)

    news_data = None
    if os.path.exists(NEWS_CACHE):
        with open(NEWS_CACHE, "r") as f:
            news_data = json.load(f)

    scores = {}
    for ticker in signals:
        logger.info(f"Scoring {ticker} [{args.mode}] ...")
        sc = compute_composite(
            ticker, signals, macro_data, news_data,
            mode=args.mode, cfg=cfg
        )
        scores[ticker] = sc

    with open(cfg["scores_cache"], "w") as f:
        json.dump(scores, f, indent=2)

    # Ranked summary
    ranked  = sorted(scores.values(), key=lambda x: x["composite_score"], reverse=True)
    sig_map = signals

    print(f"\n{'='*70}")
    print(f"  MODE: {cfg['label']}")
    print(f"  {'TICKER':<22} {'SCORE':>7}  {'RSI':>5}  {'VOL-Z':>6}  {'ENTRY?':<10}")
    print(f"  {'-'*66}")
    for item in ranked:
        tk  = item["ticker"]
        rsi = sig_map.get(tk, {}).get("rsi", 0)
        vz  = sig_map.get(tk, {}).get("volume_zscore", 0)
        ent = "🎯 YES" if item["meets_entry"] else "—"
        print(f"  {tk:<22} {item['composite_score']:>7.1f}  {rsi:>5.1f}  {vz:>6.2f}  {ent}")
    print(f"{'='*70}")

    candidates = [x["ticker"] for x in ranked if x["meets_entry"]]
    if candidates:
        print(f"\n  🎯 ENTRY CANDIDATES → {', '.join(candidates)}\n")
    else:
        print(f"\n  No entry candidates.\n")


if __name__ == "__main__":
    main()
