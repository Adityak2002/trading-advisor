# =============================================================================
# update_position.py — Manually record a Groww trade into the position file
#
# Usage (after buying on Groww):
#   python scripts/update_position.py --mode etf     ← ETF/MF swing trade
#   python scripts/update_position.py --mode stock   ← Stock delivery trade
#
# The script prompts for trade details and saves to the correct positions file
# so the next report run can track it.
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import json
from datetime import datetime

from config import get_mode_config, DATA_DIR


def parse_args():
    parser = argparse.ArgumentParser(description="Record a Groww trade")
    parser.add_argument(
        "--mode", choices=["etf", "stock"], default="etf",
        help="etf = ETF/MF swing corpus | stock = delivery corpus"
    )
    return parser.parse_args()


def load_positions(positions_file: str):
    if os.path.exists(positions_file):
        with open(positions_file, "r") as f:
            return json.load(f)
    return []


def save_positions(positions, positions_file: str):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(positions_file, "w") as f:
        json.dump(positions, f, indent=2)


def load_latest_atr(ticker: str, signals_cache: str):
    """Try to get ATR14 from the most recent signals cache."""
    if os.path.exists(signals_cache):
        with open(signals_cache, "r") as f:
            signals = json.load(f)
        sig = signals.get(ticker, {})
        return sig.get("atr14", None)
    return None


def prompt(label, default=None, cast=str):
    if default is not None:
        val = input(f"  {label} [{default}]: ").strip()
        val = val if val else str(default)
    else:
        val = input(f"  {label}: ").strip()
        while not val:
            print("  (required)")
            val = input(f"  {label}: ").strip()
    try:
        return cast(val)
    except ValueError:
        print(f"  Invalid value — expected {cast.__name__}")
        return prompt(label, default, cast)


def main():
    args = parse_args()
    cfg  = get_mode_config(args.mode)

    exit_rules      = cfg["exit_rules"]
    positions_file  = cfg["positions_file"]
    signals_cache   = cfg["signals_cache"]
    profit_pct      = exit_rules["profit_target_pct"]
    stop_mult       = exit_rules["stop_loss_atr_multiplier"]
    profit_label    = f"+{int(profit_pct * 100)}%"
    stop_label      = f"{stop_mult}×ATR"

    print("\n" + "="*60)
    print(f"  RECORD NEW POSITION [{cfg['label']}] (Groww Trade Entry)")
    print("="*60)
    print(f"  Strategy : {cfg['label']}")
    print(f"  Target   : {profit_label} | Stop: {stop_label}")
    print(f"  Max hold : {exit_rules['max_hold_days']} trading days")
    print("  Enter the details of the trade you just executed.\n")

    ticker = prompt("Ticker (e.g. BANKBEES.NS)").upper()
    if not ticker.endswith(".NS"):
        ticker += ".NS"

    entry_date  = prompt(
        "Entry date (YYYY-MM-DD)",
        default=datetime.now().strftime("%Y-%m-%d")
    )
    entry_price = prompt("Entry price (₹)", cast=float)
    shares      = prompt("Number of shares bought", cast=int)

    capital_deployed = round(entry_price * shares, 2)
    print(f"\n  Capital deployed: ₹{capital_deployed:,.2f}")

    # Auto-compute target
    target_price = round(entry_price * (1 + profit_pct), 4)
    print(f"  Auto target ({profit_label}): ₹{target_price:,.4f}")

    # Try auto ATR for stop, else ask
    atr = load_latest_atr(ticker, signals_cache)
    if atr:
        auto_stop = round(entry_price - stop_mult * atr, 4)
        print(f"  ATR(14) = ₹{atr:.4f} → Auto stop ({stop_label}): ₹{auto_stop:,.4f}")
        stop_price = prompt(
            "Stop-loss price (press Enter to use auto)",
            default=auto_stop,
            cast=float
        )
    else:
        print("  (Signal cache not found — enter stop-loss manually)")
        stop_price = prompt("Stop-loss price (₹)", cast=float)

    # Confirm
    print(f"\n{'─'*60}")
    print(f"  Corpus      : {cfg['label']}")
    print(f"  Instrument  : {ticker}")
    print(f"  Entry Date  : {entry_date}")
    print(f"  Entry Price : ₹{entry_price:,.4f}")
    print(f"  Shares      : {shares}")
    print(f"  Deployed    : ₹{capital_deployed:,.2f}")
    print(f"  Target      : ₹{target_price:,.4f}  ({profit_label})")
    print(f"  Stop-Loss   : ₹{stop_price:,.4f}  ({stop_label})")
    print(f"  Max Hold    : {exit_rules['max_hold_days']} trading days")
    print(f"{'─'*60}")

    confirm = input("\n  Save this position? [Y/n]: ").strip().lower()
    if confirm in ("n", "no"):
        print("  Cancelled.")
        return

    positions = load_positions(positions_file)

    # Remove any stale open position for same ticker in this corpus
    positions = [p for p in positions if not (
        p["instrument"] == ticker and p["status"] == "open"
    )]

    new_pos = {
        "instrument":       ticker,
        "entry_date":       entry_date,
        "entry_price":      entry_price,
        "shares":           shares,
        "capital_deployed": capital_deployed,
        "target_price":     target_price,
        "stop_price":       stop_price,
        "status":           "open",
        "days_held":        0,
        "mode":             args.mode,
    }
    positions.append(new_pos)
    save_positions(positions, positions_file)

    print(f"\n  ✅ Position saved → {positions_file}")
    print(f"  It will appear in the next {cfg['label']} report.\n")


if __name__ == "__main__":
    main()
