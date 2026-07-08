# =============================================================================
# signals.py — Step 3: Compute all technical indicators per instrument
# Reads  : data/cache/prices_etf.json  OR  prices_stock.json
# Writes : data/cache/signals_etf.json OR  signals_stock.json
#
# Usage:
#   python scripts/signals.py --mode etf    (default)
#   python scripts/signals.py --mode stock
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import pandas as pd
import numpy as np
import json
import logging

from config import get_mode_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Try pandas-ta; fall back to manual implementations if not installed
try:
    import pandas_ta as ta          # type: ignore
    _HAS_TA = True
    logger.info("pandas-ta available ✓")
except ImportError:
    _HAS_TA = False
    logger.warning("pandas-ta not found — using manual indicator calculations")


def parse_args():
    parser = argparse.ArgumentParser(description="Compute technical signals")
    parser.add_argument(
        "--mode", choices=["etf", "stock"], default="etf",
        help="etf = ETF/MF swing corpus | stock = delivery corpus"
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Manual indicator implementations (fallback)
# ---------------------------------------------------------------------------

def _rsi_manual(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr_manual(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ---------------------------------------------------------------------------
# Core signal computation
# ---------------------------------------------------------------------------

def compute_signals(ticker: str, price_data: dict) -> dict | None:
    """
    Compute all technical indicators for one instrument.
    Returns None if data is insufficient or computation fails.
    """
    try:
        df = pd.DataFrame({
            "open":   price_data["open"],
            "high":   price_data["high"],
            "low":    price_data["low"],
            "close":  price_data["close"],
            "volume": price_data["volume"],
        })
        df.index = pd.to_datetime(price_data["dates"])

        # Need at least 55 rows for EMA50 + warm-up buffer
        if len(df) < 55:
            logger.warning(f"  ✗ {ticker}: only {len(df)} rows — need ≥ 55")
            return None

        close  = df["close"]
        high   = df["high"]
        low    = df["low"]
        volume = df["volume"]

        # ── RSI(14) ─────────────────────────────────────────────────────────
        if _HAS_TA:
            rsi_s = ta.rsi(close, length=14)
        else:
            rsi_s = _rsi_manual(close, 14)
        rsi = float(rsi_s.iloc[-1]) if rsi_s is not None and len(rsi_s) > 0 else 50.0
        if np.isnan(rsi):
            rsi = 50.0

        # ── EMAs ─────────────────────────────────────────────────────────────
        ema9  = float(close.ewm(span=9,  adjust=False).mean().iloc[-1])
        ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])

        # EMA crossover — yesterday vs today (detect fresh cross)
        ema9_prev  = float(close.ewm(span=9,  adjust=False).mean().iloc[-2])
        ema21_prev = float(close.ewm(span=21, adjust=False).mean().iloc[-2])
        fresh_bullish_cross = (ema9_prev <= ema21_prev) and (ema9 > ema21)
        fresh_bearish_cross = (ema9_prev >= ema21_prev) and (ema9 < ema21)

        # ── ATR(14) ──────────────────────────────────────────────────────────
        if _HAS_TA:
            atr_s = ta.atr(high, low, close, length=14)
        else:
            atr_s = _atr_manual(high, low, close, 14)
        atr14 = float(atr_s.iloc[-1]) if atr_s is not None and len(atr_s) > 0 else 0.0
        if np.isnan(atr14):
            atr14 = float((high - low).mean())

        # ── Bollinger Bands (20, 2SD) ─────────────────────────────────────────
        bb_period = 20
        bb_mid    = float(close.rolling(bb_period).mean().iloc[-1])
        bb_std    = float(close.rolling(bb_period).std().iloc[-1])
        bb_upper  = bb_mid + 2 * bb_std
        bb_lower  = bb_mid - 2 * bb_std
        bb_width  = (bb_upper - bb_lower) / bb_mid  # Normalize bandwidth

        # ── Volume Z-score ───────────────────────────────────────────────────
        vol_mean   = float(volume.rolling(20).mean().iloc[-1])
        vol_std    = float(volume.rolling(20).std().iloc[-1])
        vol_today  = float(volume.iloc[-1])
        vol_zscore = (vol_today - vol_mean) / vol_std if vol_std > 0 else 0.0

        # ── Price metadata ───────────────────────────────────────────────────
        current_price = float(close.iloc[-1])
        prev_price    = float(close.iloc[-2])
        price_chg_pct = ((current_price - prev_price) / prev_price) * 100

        # 52-week range (use whatever history we have)
        high_52w = float(close.max())
        low_52w  = float(close.min())
        pct_from_high = ((current_price - high_52w) / high_52w) * 100

        # ── EMA21 Proximity (for stock delivery pullback detection) ───────────
        # Positive = above EMA21, Negative = below EMA21 (as % of EMA21)
        ema21_proximity_pct = (current_price - ema21) / ema21  # e.g. -0.02 = 2% below
        # True when price is within 4% of EMA21 AND still above EMA50
        price_near_ema21 = (
            current_price > ema50 and
            abs(ema21_proximity_pct) <= 0.04
        )

        return {
            # Price
            "current_price":      round(current_price, 4),
            "prev_price":         round(prev_price, 4),
            "price_change_pct":   round(price_chg_pct, 3),
            "high_52w":           round(high_52w, 4),
            "low_52w":            round(low_52w, 4),
            "pct_from_52w_high":  round(pct_from_high, 2),

            # Momentum
            "rsi":                round(rsi, 2),

            # Trend
            "ema9":               round(ema9, 4),
            "ema21":              round(ema21, 4),
            "ema50":              round(ema50, 4),
            "fresh_bullish_cross": fresh_bullish_cross,
            "fresh_bearish_cross": fresh_bearish_cross,

            # Volatility
            "atr14":              round(atr14, 4),

            # Bollinger
            "bb_upper":           round(bb_upper, 4),
            "bb_mid":             round(bb_mid, 4),
            "bb_lower":           round(bb_lower, 4),
            "bb_width":           round(bb_width, 4),

            # Volume
            "volume_today":       int(vol_today),
            "volume_avg20":       int(vol_mean),
            "volume_zscore":      round(vol_zscore, 3),

            # Derived boolean flags (used by score.py)
            "above_ema50":            current_price > ema50,
            "ema9_above_ema21":       ema9 > ema21,
            "ema21_above_ema50":      ema21 > ema50,
            "price_below_bb_lower":   current_price < bb_lower,
            "price_above_bb_upper":   current_price > bb_upper,

            # Delivery-specific: proximity to EMA21 (pullback zone detection)
            "ema21_proximity_pct":    round(ema21_proximity_pct, 4),
            "price_near_ema21":       price_near_ema21,
        }

    except Exception as e:
        logger.error(f"  ✗ {ticker}: signal error — {e}")
        return None


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    cfg  = get_mode_config(args.mode)

    if not os.path.exists(cfg["prices_cache"]):
        logger.critical(
            f"Price cache not found: {cfg['prices_cache']} — "
            f"run fetch_data.py --mode {args.mode} first"
        )
        sys.exit(1)

    with open(cfg["prices_cache"], "r") as f:
        prices = json.load(f)

    signals = {}
    failed  = []

    for ticker, price_data in prices.items():
        logger.info(f"Computing signals for {ticker} ...")
        sig = compute_signals(ticker, price_data)

        if sig:
            signals[ticker] = sig
            logger.info(
                f"  ✓ {ticker:<22} "
                f"RSI={sig['rsi']:5.1f} | "
                f"Price=₹{sig['current_price']:,.2f} | "
                f"VolZ={sig['volume_zscore']:+.2f} | "
                f"NearEMA21={'✓' if sig['price_near_ema21'] else '✗'}"
            )
        else:
            failed.append(ticker)

    with open(cfg["signals_cache"], "w") as f:
        json.dump(signals, f, indent=2)

    print(f"\n{'='*55}")
    print(f"  MODE              : {cfg['label']}")
    print(f"  SIGNALS COMPUTED  : {len(signals)} instruments")
    print(f"  FAILED            : {len(failed)}")
    if failed:
        print(f"  Skipped           : {', '.join(failed)}")
    print(f"{'='*55}\n")

    if len(signals) == 0:
        logger.critical("No signals computed! Aborting.")
        sys.exit(1)


if __name__ == "__main__":
    main()
