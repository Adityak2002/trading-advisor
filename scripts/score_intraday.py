# =============================================================================
# score_intraday.py — Step 3 (Intraday): Composite scoring for ORB quality
#
# Reads  : data/cache/signals_intraday.json
# Writes : data/cache/scores_intraday.json
#
# Scoring:
#   orb_breakout (40%) + volume multiplier (25%) + VWAP (20%) + RSI (15%)
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import logging

from config import get_mode_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


# ── Signal converters ──────────────────────────────────────────────────────

def _orb_signal(sig: dict) -> float:
    """ORB status → signal strength [-1, 1]."""
    status = sig["orb_status"]
    orb_range = sig.get("orb_range_pct", 0.0)

    if status == "breakout_long":
        # Wider ORB range = stronger conviction (but cap at 3%)
        range_bonus = min(orb_range / 3.0, 1.0) * 0.2
        return min(1.0, 0.80 + range_bonus)

    if status == "inside":
        # Inside range — no breakout yet
        current = sig["current_price"]
        orb_high = sig["orb_high"]
        orb_low  = sig["orb_low"]
        orb_range_abs = orb_high - orb_low
        if orb_range_abs > 0:
            position_in_range = (current - orb_low) / orb_range_abs
            # Upper half of range = mild positive, lower half = mild negative
            return (position_in_range - 0.5) * 0.6
        return 0.0

    # breakout_short — we don't take short positions, heavily penalise
    return -1.0


def _volume_signal(vol_mult: float, min_required: float = 1.5) -> float:
    """Volume multiplier → signal strength [-1, 1]."""
    if vol_mult == 0:
        # No breakout yet, neutral
        return 0.0
    if vol_mult >= 3.0:
        return 1.00
    if vol_mult >= 2.0:
        return 0.80
    if vol_mult >= min_required:
        return 0.50
    if vol_mult >= 1.0:
        return 0.10
    return -0.30


def _vwap_signal(sig: dict) -> float:
    """Price above/below VWAP → signal strength [-1, 1]."""
    current = sig["current_price"]
    vwap    = sig["vwap"]
    if vwap == 0:
        return 0.0

    deviation = (current - vwap) / vwap  # How far above/below VWAP as fraction

    if deviation > 0.015:   return  1.00  # Well above VWAP — strong bullish
    if deviation > 0.005:   return  0.70
    if deviation > 0.0:     return  0.35  # Just above VWAP
    if deviation > -0.005:  return -0.20  # Just below VWAP
    if deviation > -0.015:  return -0.60
    return                          -1.00  # Well below VWAP — avoid


def _rsi_intraday_signal(rsi: float) -> float:
    """Intraday RSI — momentum confirmation, avoid overbought entries."""
    if rsi < 40:    return -0.50   # Weak momentum — avoid long
    if rsi < 50:    return  0.10   # Neutral to mild positive
    if rsi < 60:    return  0.60   # Good momentum
    if rsi < 70:    return  0.90   # Strong momentum — ideal
    if rsi < 75:    return  0.50   # Getting extended — entry risk rising
    return                 -0.30   # Overbought — don't chase


def compute_intraday_composite(ticker: str, sig: dict, cfg: dict) -> dict:
    """
    Compute composite score and entry conditions for one intraday candidate.
    """
    weights     = cfg["weights"]
    entry_rules = cfg["entry_rules"]

    orb_sig  = _orb_signal(sig)
    vol_sig  = _volume_signal(
        sig.get("volume_multiplier", 0),
        min_required=entry_rules.get("min_volume_multiplier", 1.5)
    )
    vwap_sig = _vwap_signal(sig)
    rsi_sig  = _rsi_intraday_signal(sig["rsi"])

    raw = (
        weights.get("orb_breakout", 0.40) * orb_sig +
        weights.get("volume",       0.25) * vol_sig +
        weights.get("vwap",         0.20) * vwap_sig +
        weights.get("rsi",          0.15) * rsi_sig
    )

    # Apply time factor — late entries get a composite penalty
    time_factor = sig.get("time_factor", 1.0)
    composite = raw * 100.0 * time_factor

    # Hard penalty: price below VWAP on a long breakout
    if sig["is_breakout_long"] and not sig["price_above_vwap"]:
        composite -= 15.0

    composite = max(-100.0, min(100.0, composite))

    # ── Entry conditions ──────────────────────────────────────────────────────
    entry_conditions = {
        "orb_breakout_confirmed": sig["is_breakout_long"],
        "volume_sufficient":      sig.get("volume_multiplier", 0) >= entry_rules.get("min_volume_multiplier", 1.5),
        "price_above_vwap":       sig["price_above_vwap"],
        "rsi_not_overbought":     sig["rsi"] <= entry_rules.get("rsi_max", 75),
        "score_sufficient":       composite >= entry_rules.get("min_composite_score", 55),
        "time_ok":                sig.get("time_factor", 1.0) > 0.3,
    }

    meets_entry = all(entry_conditions.values())

    return {
        "ticker":            ticker,
        "composite_score":   round(composite, 2),
        "meets_entry":       meets_entry,
        "orb_status":        sig["orb_status"],
        "entry_conditions":  entry_conditions,
        "component_scores":  {
            "orb_signal":    round(orb_sig,  3),
            "volume_signal": round(vol_sig,  3),
            "vwap_signal":   round(vwap_sig, 3),
            "rsi_signal":    round(rsi_sig,  3),
        },
    }


def main():
    cfg = get_mode_config("intraday")

    if not os.path.exists(cfg["signals_cache"]):
        logger.critical(f"Signals cache not found: {cfg['signals_cache']}. Run signals_intraday.py first.")
        sys.exit(1)

    with open(cfg["signals_cache"], "r") as f:
        signals = json.load(f)

    scores = {}
    for ticker, sig in signals.items():
        logger.info(f"Scoring {ticker} ...")
        sc = compute_intraday_composite(ticker, sig, cfg)
        scores[ticker] = sc

    with open(cfg["scores_cache"], "w") as f:
        json.dump(scores, f, indent=2)

    # Ranked summary
    ranked = sorted(scores.values(), key=lambda x: x["composite_score"], reverse=True)

    print(f"\n{'='*70}")
    print(f"  INTRADAY SCORES")
    print(f"  {'TICKER':<20} {'SCORE':>7}  {'ORB STATUS':<20}  {'ENTRY?'}")
    print(f"  {'-'*66}")
    for item in ranked:
        entry_str = "🎯 YES" if item["meets_entry"] else "—"
        print(f"  {item['ticker']:<20} {item['composite_score']:>7.1f}  {item['orb_status']:<20}  {entry_str}")
    print(f"{'='*70}")

    candidates = [x["ticker"] for x in ranked if x["meets_entry"]]
    if candidates:
        print(f"\n  🎯 INTRADAY ENTRY CANDIDATES → {', '.join(candidates)}\n")
    else:
        print(f"\n  No intraday entry candidates at this time.\n")


if __name__ == "__main__":
    main()
