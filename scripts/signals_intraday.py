# =============================================================================
# signals_intraday.py — Step 2 (Intraday): Compute ORB signals and indicators
#
# Reads  : data/cache/prices_intraday.json
# Writes : data/cache/signals_intraday.json
#
# Indicators computed on 5-minute candles:
#   - ORB breakout status (above/below/inside range)
#   - Volume multiplier at the breakout candle
#   - VWAP (Volume Weighted Average Price)
#   - Intraday RSI(14) on 5-min candles
#   - Time-based penalty (penalise late entries)
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import logging
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

from config import get_mode_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def get_ist_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def _rsi_manual(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def compute_vwap(df: pd.DataFrame) -> float:
    """Compute intraday VWAP from open of session to now."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    vwap = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
    return float(vwap.iloc[-1]) if not vwap.empty else 0.0


def compute_intraday_signals(ticker: str, price_data: dict, entry_rules: dict) -> dict | None:
    """
    Compute all intraday signals for one stock.
    """
    try:
        candles = price_data["candles"]
        df = pd.DataFrame({
            "open":   candles["open"],
            "high":   candles["high"],
            "low":    candles["low"],
            "close":  candles["close"],
            "volume": candles["volume"],
        })
        df.index = pd.to_datetime(candles["timestamps"])

        if len(df) < 3:
            logger.warning(f"  ✗ {ticker}: insufficient candles ({len(df)})")
            return None

        orb_high = price_data["orb_high"]
        orb_low  = price_data["orb_low"]
        current_price = price_data["current_price"]
        last_time_str = price_data.get("last_time_ist", "00:00")

        # ── ORB Breakout Detection ───────────────────────────────────────────
        buffer_pct = entry_rules.get("breakout_buffer_pct", 0.001)
        orb_buy_level  = orb_high * (1 + buffer_pct)   # 0.1% above OR High
        orb_sell_level = orb_low  * (1 - buffer_pct)   # 0.1% below OR Low

        orb_status = "inside"
        if current_price > orb_buy_level:
            orb_status = "breakout_long"   # Bullish ORB breakout confirmed
        elif current_price < orb_sell_level:
            orb_status = "breakout_short"  # Bearish ORB breakdown

        # ── Breakout Candle Volume Multiplier ────────────────────────────────
        # Identify the breakout candle (first candle that crossed the ORB level)
        orb_end_time = df.index[0].replace(hour=9, minute=30, second=0)
        post_orb_df = df[df.index >= orb_end_time]

        volume_avg_5min = float(df["volume"].mean()) if not df.empty else 1
        volume_multiplier = 0.0

        if not post_orb_df.empty:
            # Find the first candle that confirmed the breakout
            for _, row in post_orb_df.iterrows():
                if (orb_status == "breakout_long"  and row["close"] > orb_high) or \
                   (orb_status == "breakout_short" and row["close"] < orb_low):
                    volume_multiplier = row["volume"] / volume_avg_5min if volume_avg_5min > 0 else 0.0
                    break

        # ── VWAP ─────────────────────────────────────────────────────────────
        vwap = compute_vwap(df)
        price_above_vwap = current_price > vwap

        # ── Intraday RSI(14) on 5-min candles ────────────────────────────────
        rsi_series = _rsi_manual(df["close"], 14)
        rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0
        if np.isnan(rsi):
            rsi = 50.0

        # ── Time-based scoring context ────────────────────────────────────────
        # Later entries in the day carry more risk (less time to hit target)
        try:
            last_hour, last_min = map(int, last_time_str.split(":"))
            minutes_since_open = (last_hour - 9) * 60 + last_min - 15
            # Scale: 0-60 min = full score, 60-120 min = 0.7, 120+ min = 0.4
            if minutes_since_open <= 60:
                time_factor = 1.0
            elif minutes_since_open <= 120:
                time_factor = 0.7
            else:
                time_factor = 0.4
        except Exception:
            time_factor = 1.0

        # ── Price metadata ────────────────────────────────────────────────────
        orb_range_pct = ((orb_high - orb_low) / orb_low) * 100 if orb_low > 0 else 0.0

        return {
            # ORB core
            "orb_high":            round(orb_high, 4),
            "orb_low":             round(orb_low, 4),
            "orb_buy_level":       round(orb_buy_level, 4),
            "orb_sell_level":      round(orb_sell_level, 4),
            "orb_status":          orb_status,
            "orb_range_pct":       round(orb_range_pct, 3),
            # Breakout quality
            "volume_multiplier":   round(volume_multiplier, 2),
            "volume_avg_5min":     int(volume_avg_5min),
            # VWAP
            "vwap":                round(vwap, 4),
            "price_above_vwap":    price_above_vwap,
            # Momentum
            "rsi":                 round(rsi, 2),
            # Price
            "current_price":       round(current_price, 4),
            "last_time_ist":       last_time_str,
            # Time context
            "time_factor":         round(time_factor, 2),
            # Booleans
            "is_breakout_long":    orb_status == "breakout_long",
            "is_breakout_short":   orb_status == "breakout_short",
            "is_inside_range":     orb_status == "inside",
        }

    except Exception as e:
        logger.error(f"  ✗ {ticker}: signal error — {e}")
        return None


def main():
    cfg = get_mode_config("intraday")

    if not os.path.exists(cfg["prices_cache"]):
        logger.critical(f"Price cache not found: {cfg['prices_cache']}. Run fetch_intraday.py first.")
        sys.exit(1)

    with open(cfg["prices_cache"], "r") as f:
        prices = json.load(f)

    signals = {}
    failed  = []

    for ticker, price_data in prices.items():
        logger.info(f"Computing intraday signals for {ticker} ...")
        sig = compute_intraday_signals(ticker, price_data, cfg["entry_rules"])
        if sig:
            signals[ticker] = sig
            status_icon = "🔼" if sig["is_breakout_long"] else ("🔽" if sig["is_breakout_short"] else "▶")
            logger.info(
                f"  ✓ {ticker:<20} {status_icon} {sig['orb_status']:<18} "
                f"RSI={sig['rsi']:5.1f} | VWAP={'✓' if sig['price_above_vwap'] else '✗'} | "
                f"VolMult={sig['volume_multiplier']:.1f}x"
            )
        else:
            failed.append(ticker)

    with open(cfg["signals_cache"], "w") as f:
        json.dump(signals, f, indent=2)

    logger.info(f"Saved intraday signals → {cfg['signals_cache']}")

    breakout_long  = [t for t, s in signals.items() if s["is_breakout_long"]]
    breakout_short = [t for t, s in signals.items() if s["is_breakout_short"]]

    print(f"\n{'='*60}")
    print(f"  INTRADAY SIGNALS COMPUTED  : {len(signals)} stocks")
    print(f"  FAILED                     : {len(failed)}")
    print(f"  ORB Long Breakouts         : {len(breakout_long)}")
    print(f"  ORB Short Breakdowns       : {len(breakout_short)}")
    if breakout_long:
        print(f"  Long Candidates: {', '.join(breakout_long)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
