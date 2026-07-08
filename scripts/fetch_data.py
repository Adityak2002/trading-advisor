# =============================================================================
# fetch_data.py — Step 1: Download OHLCV price data from Yahoo Finance
# Saves results to data/cache/prices_etf.json or prices_stock.json
#
# Usage:
#   python scripts/fetch_data.py --mode etf    (default)
#   python scripts/fetch_data.py --mode stock
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import yfinance as yf
import json
import logging
from datetime import datetime

from config import get_mode_config, CACHE_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch OHLCV price data")
    parser.add_argument(
        "--mode", choices=["etf", "stock"], default="etf",
        help="etf = ETF/MF swing corpus | stock = delivery corpus"
    )
    return parser.parse_args()


def get_all_tickers(watchlist: dict) -> list[str]:
    """Flatten all tickers from all watchlist categories."""
    tickers = []
    for category, symbols in watchlist.items():
        tickers.extend(symbols)
    return tickers


def fetch_price_data(tickers: list[str], period: str = "6mo") -> tuple[dict, list]:
    """
    Download OHLCV daily data for each ticker.

    Returns:
        prices  : dict[ticker → OHLCV dict]
        failed  : list of tickers that could not be fetched
    """
    prices = {}
    failed = []

    for ticker in tickers:
        try:
            logger.info(f"Fetching {ticker} ...")
            df = yf.download(
                ticker,
                period=period,
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
            )

            # yfinance may return multi-level columns; flatten if so
            if isinstance(df.columns, type(df.columns)) and hasattr(df.columns, "levels"):
                df.columns = df.columns.get_level_values(0)

            if df.empty or len(df) < 30:
                logger.warning(f"  ✗ {ticker}: insufficient data ({len(df)} rows)")
                failed.append(ticker)
                continue

            # Drop NaN rows and serialize
            df = df.dropna()
            prices[ticker] = {
                "dates":      [d.strftime("%Y-%m-%d") for d in df.index],
                "open":       [round(float(v), 4) for v in df["Open"]],
                "high":       [round(float(v), 4) for v in df["High"]],
                "low":        [round(float(v), 4) for v in df["Low"]],
                "close":      [round(float(v), 4) for v in df["Close"]],
                "volume":     [int(v) for v in df["Volume"]],
                "last_close": round(float(df["Close"].iloc[-1]), 4),
                "last_date":  df.index[-1].strftime("%Y-%m-%d"),
                "rows":       len(df),
            }
            logger.info(
                f"  ✓ {ticker}: {len(df)} days | "
                f"Last close ₹{prices[ticker]['last_close']:.2f}"
            )

        except Exception as e:
            logger.error(f"  ✗ {ticker}: {e}")
            failed.append(ticker)

    return prices, failed


def main():
    args = parse_args()
    cfg  = get_mode_config(args.mode)

    os.makedirs(CACHE_DIR, exist_ok=True)

    tickers = get_all_tickers(cfg["watchlist"])
    logger.info(
        f"[{cfg['label']}] Starting data fetch for {len(tickers)} instruments ..."
    )

    prices, failed = fetch_price_data(tickers)

    # Persist to mode-specific cache
    with open(cfg["prices_cache"], "w") as f:
        json.dump(prices, f)
    logger.info(f"Saved price data → {cfg['prices_cache']}")

    # Summary
    print(f"\n{'='*55}")
    print(f"  MODE     : {cfg['label']}")
    print(f"  FETCH COMPLETE  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Success : {len(prices):>3} instruments")
    print(f"  Failed  : {len(failed):>3} instruments")
    if failed:
        print(f"  Skipped : {', '.join(failed)}")
    print(f"{'='*55}\n")

    if len(prices) == 0:
        logger.critical("No price data fetched! Subsequent steps will fail.")
        sys.exit(1)


if __name__ == "__main__":
    main()
