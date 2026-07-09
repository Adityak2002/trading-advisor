# =============================================================================
# fetch_intraday.py — Step 1 (Intraday): Download 5-minute candle data
#
# Fetches today's 5-minute OHLCV candles for the intraday watchlist.
# Identifies the Opening Range (first 15 minutes: 9:15-9:30 IST).
# Saves results to data/cache/prices_intraday.json
#
# Usage:
#   python scripts/fetch_intraday.py
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import logging
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

from config import get_mode_config, CACHE_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def get_ist_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def fetch_5min_candles(ticker: str) -> dict | None:
    """
    Download today's 5-minute OHLCV candles for a ticker.
    yfinance provides 5m data for the last 60 days.
    """
    try:
        df = yf.download(
            ticker,
            period="1d",
            interval="5m",
            auto_adjust=True,
            progress=False,
            threads=False,
        )

        # Flatten multi-level columns if present
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)

        if df.empty or len(df) < 3:
            logger.warning(f"  ✗ {ticker}: insufficient intraday data ({len(df)} candles)")
            return None

        # Convert index to IST (yfinance returns UTC-aware timestamps)
        try:
            df.index = df.index.tz_convert("Asia/Kolkata")
        except Exception:
            # If already naive or different tz, just localize
            try:
                df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
            except Exception:
                pass

        # Remove timezone info after conversion (make naive IST)
        df.index = df.index.tz_localize(None)

        # Filter to today's session only
        today = get_ist_now().date()
        df = df[df.index.date == today]

        if df.empty:
            logger.warning(f"  ✗ {ticker}: no data for today ({today})")
            return None

        # ── Opening Range: first 15 minutes (9:15 – 9:29 IST) ──────────────
        market_open = datetime.combine(today, datetime.strptime("09:15", "%H:%M").time())
        orb_end     = datetime.combine(today, datetime.strptime("09:30", "%H:%M").time())

        orb_candles = df[(df.index >= market_open) & (df.index < orb_end)]

        if orb_candles.empty:
            logger.warning(f"  ✗ {ticker}: no opening range candles found (market may not be open yet)")
            orb_high = float(df["High"].iloc[0])
            orb_low  = float(df["Low"].iloc[0])
        else:
            orb_high = float(orb_candles["High"].max())
            orb_low  = float(orb_candles["Low"].min())

        # Last candle (current price context)
        last = df.iloc[-1]
        current_price = float(last["Close"])
        last_time = df.index[-1].strftime("%H:%M")

        # Full candle series for VWAP / RSI computation in signals step
        candles = {
            "timestamps": [t.strftime("%Y-%m-%d %H:%M") for t in df.index],
            "open":   [round(float(v), 4) for v in df["Open"]],
            "high":   [round(float(v), 4) for v in df["High"]],
            "low":    [round(float(v), 4) for v in df["Low"]],
            "close":  [round(float(v), 4) for v in df["Close"]],
            "volume": [int(v) for v in df["Volume"]],
        }

        result = {
            "ticker":        ticker,
            "date":          str(today),
            "orb_high":      round(orb_high, 4),
            "orb_low":       round(orb_low, 4),
            "current_price": round(current_price, 4),
            "last_time_ist": last_time,
            "total_candles": len(df),
            "candles":       candles,
        }

        logger.info(
            f"  ✓ {ticker:<20} ORB [{orb_low:.2f} – {orb_high:.2f}] "
            f"Current: ₹{current_price:.2f} @ {last_time}"
        )
        return result

    except Exception as e:
        logger.error(f"  ✗ {ticker}: {e}")
        return None


def main():
    cfg = get_mode_config("intraday")
    os.makedirs(CACHE_DIR, exist_ok=True)

    ist_now = get_ist_now()
    logger.info(f"[Intraday] Starting 5-min data fetch at {ist_now.strftime('%H:%M IST')}")
    logger.info(f"Watchlist: {len(cfg['watchlist'])} stocks")

    prices = {}
    failed = []

    for ticker in cfg["watchlist"]:
        logger.info(f"Fetching {ticker} ...")
        result = fetch_5min_candles(ticker)
        if result:
            prices[ticker] = result
        else:
            failed.append(ticker)

    with open(cfg["prices_cache"], "w") as f:
        json.dump(prices, f, indent=2)

    logger.info(f"Saved intraday price data → {cfg['prices_cache']}")

    print(f"\n{'='*60}")
    print(f"  MODE         : Intraday (ORB)")
    print(f"  TIME IST     : {ist_now.strftime('%H:%M')}")
    print(f"  SUCCESS      : {len(prices)} stocks")
    print(f"  FAILED       : {len(failed)} stocks")
    if failed:
        print(f"  Skipped      : {', '.join(failed)}")
    print(f"{'='*60}\n")

    if len(prices) == 0:
        logger.critical("No intraday price data fetched! Aborting.")
        sys.exit(1)


if __name__ == "__main__":
    main()
