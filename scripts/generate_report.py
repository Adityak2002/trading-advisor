# =============================================================================
# generate_report.py — Step 5: Write report.md + update state files
#
# Reads  : signals / scores / macro / news cache + positions + history
# Writes : reports/etf_report.md  OR  reports/stock_report.md
#          data/positions_etf.json OR data/positions_stock.json
#          data/history_etf.csv    OR data/history_stock.csv
#
# Usage:
#   python scripts/generate_report.py --mode etf    (default)
#   python scripts/generate_report.py --mode stock
# =============================================================================

import sys
import os
import shutil
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import json
import csv
import logging
from datetime import datetime, timedelta
from typing import Optional

from config import (
    get_mode_config,
    MACRO_CACHE, NEWS_CACHE, REPORTS_DIR,
    VIX_THRESHOLDS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Generate trading report")
    parser.add_argument(
        "--mode", choices=["etf", "stock"], default="etf",
        help="etf = ETF/MF swing corpus | stock = delivery corpus"
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers — positions & history I/O
# ---------------------------------------------------------------------------

HISTORY_FIELDS = [
    "instrument", "entry_date", "entry_price",
    "exit_date", "exit_price", "shares", "capital_deployed",
    "gross_pnl", "pnl_pct", "exit_reason",
]


def load_positions(positions_file: str) -> list[dict]:
    if os.path.exists(positions_file):
        with open(positions_file, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    return []


def save_positions(positions: list[dict], positions_file: str):
    with open(positions_file, "w") as f:
        json.dump(positions, f, indent=2)


def append_to_history(trade: dict, history_file: str):
    exists = os.path.exists(history_file)
    with open(history_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({k: trade.get(k, "") for k in HISTORY_FIELDS})


def load_history(history_file: str) -> list[dict]:
    if not os.path.exists(history_file):
        return []
    with open(history_file, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Trading-day counter (Mon–Fri, no holiday calendar — good enough approximation)
# ---------------------------------------------------------------------------

def get_ist_now() -> datetime:
    """Return current time in Indian Standard Time (IST) as naive datetime."""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def trading_days_held(entry_date_str: str) -> int:
    entry = datetime.strptime(entry_date_str, "%Y-%m-%d")
    today = get_ist_now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    cur   = entry + timedelta(days=1)
    while cur <= today:
        if cur.weekday() < 5:
            count += 1
        cur += timedelta(days=1)
    return count


# ---------------------------------------------------------------------------
# Exit checker — updates P&L, closes positions that hit target/stop
# ---------------------------------------------------------------------------

def process_open_positions(
    positions: list[dict],
    signals: dict,
    today_str: str,
    cfg: dict,
) -> tuple[list[dict], list[dict]]:
    """
    Returns (still_open, closed_today).
    Mutates position dicts with current_price, current_pnl, etc.
    Handles: target hit, stop hit, time exit, partial exit, trailing stop.
    """
    exit_rules   = cfg["exit_rules"]
    still_open   = []
    closed_today = []

    # Partial exit + trailing stop config
    partial_exit_pct      = exit_rules.get("partial_exit_pct", 0)
    partial_exit_fraction  = exit_rules.get("partial_exit_fraction", 0.50)
    trailing_trigger_pct   = exit_rules.get("trailing_stop_trigger_pct", 0)

    for pos in positions:
        if pos.get("status") != "open":
            continue

        ticker = pos["instrument"]
        sig    = signals.get(ticker, {})

        current_price = sig.get("current_price", pos.get("entry_price", 0.0))
        pos["current_price"] = round(current_price, 4)

        days_held = trading_days_held(pos["entry_date"])
        pos["days_held"] = days_held

        pnl     = (current_price - pos["entry_price"]) * pos["shares"]
        pnl_pct = ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100
        pos["current_pnl"]     = round(pnl, 2)
        pos["current_pnl_pct"] = round(pnl_pct, 3)

        pos["pct_to_target"] = round(
            ((pos["target_price"] - current_price) / current_price) * 100, 3)
        pos["pct_to_stop"]   = round(
            ((current_price - pos["stop_price"])   / current_price) * 100, 3)

        # ── Trailing stop: move stop to breakeven at +4% (stock) / +2% (ETF) ──
        if trailing_trigger_pct > 0 and pnl_pct >= (trailing_trigger_pct * 100):
            if pos["stop_price"] < pos["entry_price"]:
                old_stop = pos["stop_price"]
                pos["stop_price"] = pos["entry_price"]
                pos["trailing_stop_active"] = True
                logger.info(
                    f"  TRAILING STOP ↑ {ticker}: stop moved from "
                    f"₹{old_stop:.2f} → ₹{pos['entry_price']:.2f} (breakeven)"
                )

        # ── Partial exit: sell half at +5% (stock) / +3% (ETF) ────────────────
        if (partial_exit_pct > 0 and
                not pos.get("partial_exit_taken") and
                pnl_pct >= (partial_exit_pct * 100) and
                pos["shares"] >= 2):
            shares_to_sell = max(1, int(pos["shares"] * partial_exit_fraction))
            partial_pnl = (current_price - pos["entry_price"]) * shares_to_sell
            partial_pnl_pct = pnl_pct

            # Record partial exit in history
            partial_trade = {
                "instrument":       ticker,
                "entry_date":       pos["entry_date"],
                "entry_price":      pos["entry_price"],
                "exit_date":        today_str,
                "exit_price":       current_price,
                "shares":           shares_to_sell,
                "capital_deployed": round(pos["entry_price"] * shares_to_sell, 2),
                "gross_pnl":        round(partial_pnl, 2),
                "pnl_pct":          round(partial_pnl_pct, 3),
                "exit_reason":      "PARTIAL_EXIT",
            }
            append_to_history(partial_trade, cfg["history_file"])

            pos["shares"] -= shares_to_sell
            pos["capital_deployed"] = round(pos["entry_price"] * pos["shares"], 2)
            pos["partial_exit_taken"] = True
            pos["partial_shares_sold"] = shares_to_sell
            pos["partial_pnl_booked"] = round(partial_pnl, 2)

            # Also move stop to breakeven after partial exit
            if pos["stop_price"] < pos["entry_price"]:
                pos["stop_price"] = pos["entry_price"]
                pos["trailing_stop_active"] = True

            logger.info(
                f"  PARTIAL EXIT {ticker}: sold {shares_to_sell} shares "
                f"@ ₹{current_price:.2f} | Booked P&L: ₹{partial_pnl:+.2f} | "
                f"Remaining: {pos['shares']} shares with stop at breakeven"
            )

        # Recompute P&L with updated shares
        pnl = (current_price - pos["entry_price"]) * pos["shares"]
        pos["current_pnl"] = round(pnl, 2)

        exit_reason: Optional[str] = None
        review_days = exit_rules.get("review_hold_days", exit_rules["max_hold_days"])

        if current_price >= pos["target_price"]:
            exit_reason = "TARGET_HIT"
        elif current_price <= pos["stop_price"]:
            exit_reason = "STOP_HIT"
        elif days_held >= exit_rules["max_hold_days"]:
            exit_reason = "TIME_EXIT_REVIEW"
        elif days_held >= review_days and exit_reason is None:
            exit_reason = "TIME_REVIEW"   # soft flag — user decides

        if exit_reason and exit_reason not in ("TIME_EXIT_REVIEW", "TIME_REVIEW"):
            trade = {
                "instrument":       ticker,
                "entry_date":       pos["entry_date"],
                "entry_price":      pos["entry_price"],
                "exit_date":        today_str,
                "exit_price":       current_price,
                "shares":           pos["shares"],
                "capital_deployed": pos["capital_deployed"],
                "gross_pnl":        round(pnl, 2),
                "pnl_pct":          round(pnl_pct, 3),
                "exit_reason":      exit_reason,
            }
            append_to_history(trade, cfg["history_file"])
            pos["status"]      = "closed"
            pos["exit_date"]   = today_str
            pos["exit_price"]  = current_price
            pos["exit_reason"] = exit_reason
            closed_today.append(pos)
            logger.info(
                f"  CLOSED {ticker}: {exit_reason}  "
                f"P&L ₹{pnl:+.2f} ({pnl_pct:+.2f}%)"
            )
        else:
            pos["exit_flag"] = exit_reason
            still_open.append(pos)

    return still_open, closed_today


# ---------------------------------------------------------------------------
# Entry candidate selector
# ---------------------------------------------------------------------------

def get_entry_candidates(
    scores: dict,
    signals: dict,
    open_positions: list[dict],
    macro_data: dict,
    cfg: dict,
) -> list[dict]:
    pos_sizing  = cfg["position_sizing"]
    entry_rules = cfg["entry_rules"]
    exit_rules  = cfg["exit_rules"]
    mode        = cfg["mode"]

    max_open     = entry_rules.get("max_open_positions", pos_sizing.get("max_positions", 2))
    current_tickers = {p["instrument"] for p in open_positions}
    num_open        = len(open_positions)

    if num_open >= max_open:
        return []

    slots_to_fill = max_open - num_open
    deployed      = sum(p.get("capital_deployed", 0) for p in open_positions)
    available     = pos_sizing["total_capital"] - deployed

    vix_factor = macro_data.get("_signal", {}).get("vix_factor", 1.0)

    # ETF: track international positions cap
    intl_open = 0
    if mode == "etf":
        intl_open = sum(
            1 for p in open_positions
            if scores.get(p["instrument"], {}).get("category") == "etf_international"
        )

    ranked     = sorted(scores.values(), key=lambda x: x["composite_score"], reverse=True)
    candidates = []

    for item in ranked:
        if not item["meets_entry"]:
            continue
        ticker   = item["ticker"]
        category = item["category"]

        if ticker in current_tickers:
            continue

        # ETF-only: cap 1 international position
        if (mode == "etf" and category == "etf_international" and
                intl_open >= pos_sizing.get("max_international_positions", 1)):
            continue

        sig = signals.get(ticker)
        if not sig:
            continue

        current_price = sig["current_price"]
        atr14         = sig["atr14"]

        # ── ATR-based risk sizing (new) ────────────────────────────────────
        # "I'm willing to risk ₹X per trade" → work backwards from stop distance
        risk_pct_per_trade = pos_sizing.get("risk_per_trade_pct", 0.05)
        risk_budget = pos_sizing["total_capital"] * risk_pct_per_trade * vix_factor
        stop_mult   = exit_rules["stop_loss_atr_multiplier"]
        stop_distance = stop_mult * atr14

        if stop_distance > 0:
            atr_shares = int(risk_budget / stop_distance)
        else:
            atr_shares = 0

        # Capital cap — don't exceed available capital
        max_shares_by_capital = int(available / current_price) if current_price > 0 else 0
        shares = min(atr_shares, max_shares_by_capital)

        # ETF-only: cap crude exposure
        if mode == "etf" and ticker == "OILIETF.NS":
            crude_cap = pos_sizing.get("max_crude_allocation", 3000) * vix_factor
            max_crude_shares = int(crude_cap / current_price)
            shares = min(shares, max_crude_shares)

        if shares < 1:
            continue

        actual_deploy = shares * current_price
        profit_pct    = exit_rules["profit_target_pct"]

        target_price = round(current_price * (1 + profit_pct), 4)
        stop_price   = round(current_price - stop_distance, 4)
        risk_amt     = round(stop_distance * shares, 2)
        risk_pct     = round((stop_distance / current_price) * 100, 3)

        candidates.append({
            "ticker":            ticker,
            "category":          category,
            "composite_score":   item["composite_score"],
            "current_price":     current_price,
            "shares":            shares,
            "capital_to_deploy": round(actual_deploy, 2),
            "target_price":      target_price,
            "stop_price":        stop_price,
            "atr14":             atr14,
            "risk_amount":       risk_amt,
            "risk_pct":          risk_pct,
            "risk_budget":       round(risk_budget, 2),
            "vix_factor":        vix_factor,
            "entry_conditions":  item["entry_conditions"],
            "component_scores":  item["component_scores"],
            "signals_snapshot":  sig,
        })

        if len(candidates) >= slots_to_fill:
            break

    return candidates


# ---------------------------------------------------------------------------
# Performance summary
# ---------------------------------------------------------------------------

def performance_summary(history_file: str) -> Optional[dict]:
    history = load_history(history_file)
    closed  = [h for h in history if h.get("exit_reason") not in
               ("TIME_EXIT_REVIEW", "TIME_REVIEW", "")]
    if not closed:
        return None

    pnls     = [float(h["gross_pnl"]) for h in closed]
    pnl_pcts = [float(h["pnl_pct"])   for h in closed]
    wins     = [p for p in pnls if p > 0]
    losses   = [p for p in pnls if p <= 0]

    reasons = {}
    for h in closed:
        r = h.get("exit_reason", "unknown")
        reasons[r] = reasons.get(r, 0) + 1

    return {
        "total_trades":  len(closed),
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate":      round(len(wins) / len(pnls) * 100, 1) if pnls else 0,
        "total_pnl":     round(sum(pnls), 2),
        "avg_win":       round(sum(wins) / len(wins), 2)     if wins   else 0,
        "avg_loss":      round(sum(losses) / len(losses), 2) if losses else 0,
        "best_pct":      round(max(pnl_pcts), 2) if pnl_pcts else 0,
        "worst_pct":     round(min(pnl_pcts), 2) if pnl_pcts else 0,
        "exit_reasons":  reasons,
    }


# ---------------------------------------------------------------------------
# Report builder — ETF entry checklist block
# ---------------------------------------------------------------------------

def _etf_entry_checklist(cand: dict, sig: dict) -> list[str]:
    ec = cand["entry_conditions"]
    return [
        f"- {'✅' if ec['rsi_oversold'] else '❌'} RSI < 38 &nbsp; *(actual: {sig['rsi']:.1f})*",
        f"- {'✅' if ec['above_ema50'] else '❌'} Price > EMA50 &nbsp; *(EMA50: ₹{sig['ema50']:,.4f})*",
        f"- {'✅' if ec['volume_confirmed'] else '❌'} Volume Z-score ≥ 1.5 &nbsp; *(actual: {sig['volume_zscore']:.2f})*",
        f"- {'✅' if ec['score_sufficient'] else '❌'} Composite score ≥ 40 &nbsp; *(actual: {cand['composite_score']:.1f})*",
    ]


# ---------------------------------------------------------------------------
# Report builder — Stock entry checklist block
# ---------------------------------------------------------------------------

def _stock_entry_checklist(cand: dict, sig: dict) -> list[str]:
    ec = cand["entry_conditions"]
    dist_pct = sig.get("ema21_proximity_pct", 0) * 100
    return [
        f"- {'✅' if ec['rsi_pullback_zone'] else '❌'} RSI in 42–55 (healthy pullback) &nbsp; *(actual: {sig['rsi']:.1f})*",
        f"- {'✅' if ec['ema21_above_ema50'] else '❌'} EMA21 > EMA50 (medium uptrend intact) &nbsp; *(EMA21: ₹{sig['ema21']:,.4f} | EMA50: ₹{sig['ema50']:,.4f})*",
        f"- {'✅' if ec['price_near_ema21'] else '❌'} Price within 4% of EMA21 &nbsp; *(distance: {dist_pct:+.2f}%)*",
        f"- {'✅' if ec['volume_calm'] else '❌'} Volume Z-score ≤ 2.0 (calm pullback) &nbsp; *(actual: {sig['volume_zscore']:.2f})*",
        f"- {'✅' if ec['score_sufficient'] else '❌'} Composite score ≥ 50 &nbsp; *(actual: {cand['composite_score']:.1f})*",
        f"- {'✅' if ec.get('nifty_trend_ok', True) else '❌'} Nifty above 20-EMA (market trend gate)",
        f"- {'✅' if ec.get('sector_strength_ok', True) else '❌'} Sector not underperforming Nifty by >3%",
    ]


# ---------------------------------------------------------------------------
# Full report builder
# ---------------------------------------------------------------------------

def build_report(
    today_str: str,
    open_positions: list[dict],
    closed_today: list[dict],
    candidates: list[dict],
    scores: dict,
    signals: dict,
    macro_data: dict,
    news_data: Optional[dict],
    cfg: dict,
) -> str:
    L = []
    add = L.append
    mode        = cfg["mode"]
    pos_sizing  = cfg["position_sizing"]
    exit_rules  = cfg["exit_rules"]
    entry_rules = cfg["entry_rules"]

    max_open   = entry_rules.get("max_open_positions", pos_sizing.get("max_positions", 2))
    total_cap  = pos_sizing["total_capital"]
    profit_pct = int(exit_rules["profit_target_pct"] * 100)

    # ── Header ───────────────────────────────────────────────────────────────
    if mode == "stock":
        title    = "📈 Stock Delivery Report"
        subtitle = "Strategy: Momentum Pullback | Capital: ₹10,000 | Hold: ~20 days"
        schedule = "2-hour scan during market hours (9:30–15:30 IST)"
    else:
        title    = "📊 ETF/MF Daily Report"
        subtitle = "Strategy: Oversold Bounce | Capital: ₹10,000 | Hold: ~10 days"
        schedule = "Daily 08:30 IST"

    add(f"# {title} — {today_str}")
    add(f"> *Auto-generated at {get_ist_now().strftime('%H:%M')} IST | {schedule}*  ")
    add(f"> *{subtitle} | Manual execution on Groww*")
    add("")

    # ── Market Context ────────────────────────────────────────────────────────
    add("---")
    add("## 🌍 Market Context")
    add("")

    macro_sig = macro_data.get("_signal", {}) if macro_data else {}
    summary   = macro_sig.get("summary", "N/A")
    add(f"**Overall Signal:** {summary}")
    add("")

    add("| Index / Asset | Level | Change |")
    add("|---------------|-------|--------|")

    def _mrow(name, key, fmt=",.2f", prefix=""):
        d = macro_data.get(key) if macro_data else None
        if d:
            chg   = d.get("pct_change", 0)
            arrow = "📈" if chg >= 0 else "📉"
            add(f"| {name} | {prefix}{d['current']:{fmt}} | {arrow} {chg:+.2f}% |")

    _mrow("Nifty 50",           "nifty")
    _mrow("India VIX",          "india_vix", fmt=".2f")
    _mrow("S&P 500 (overnight)","sp500",     fmt=",.2f")
    _mrow("NASDAQ",             "nasdaq",    fmt=",.2f")
    _mrow("WTI Crude Oil",      "crude_oil", fmt=".2f", prefix="$")
    _mrow("USD / INR",          "usd_inr",   fmt=".4f")
    add("")

    if macro_sig.get("factors"):
        add("**Key Factors:**")
        for fct in macro_sig["factors"]:
            add(f"- {fct}")
    add("")

    # ── Portfolio Status ──────────────────────────────────────────────────────
    add("---")
    add(f"## 💼 Portfolio Status — {cfg['label']}")
    add("")

    deployed    = sum(p.get("capital_deployed", 0) for p in open_positions)
    idle        = total_cap - deployed
    running_pnl = sum(p.get("current_pnl", 0) for p in open_positions)
    pnl_emoji   = "📈" if running_pnl >= 0 else "📉"

    add("| Metric | Value |")
    add("|--------|-------|")
    add(f"| Corpus | {cfg['label']} |")
    add(f"| Starting Capital | ₹{total_cap:,} |")
    add(f"| Capital Deployed | ₹{deployed:,.2f} |")
    add(f"| Idle Cash | ₹{idle:,.2f} |")
    add(f"| Open Positions | {len(open_positions)} / {max_open} |")
    add(f"| Running P&L | {pnl_emoji} ₹{running_pnl:+,.2f} |")
    add("")

    if closed_today:
        add("**Positions Closed Today:**")
        add("")
        add("| Instrument | Exit Reason | P&L | P&L % |")
        add("|------------|-------------|-----|-------|")
        for pos in closed_today:
            ep  = pos.get("current_pnl", 0)
            epp = pos.get("current_pnl_pct", 0)
            em  = "✅" if ep > 0 else "❌"
            add(f"| {pos['instrument']} | {pos.get('exit_reason','?')} | {em} ₹{ep:+,.2f} | {epp:+.2f}% |")
        add("")

    # ── Open Positions ────────────────────────────────────────────────────────
    add("---")
    add("## 📂 Open Positions")
    add("")

    if open_positions:
        for pos in open_positions:
            pnl     = pos.get("current_pnl", 0)
            pnl_pct = pos.get("current_pnl_pct", 0)
            pnl_em  = "📈" if pnl >= 0 else "📉"
            exit_flag = pos.get("exit_flag")

            add(f"### {pos['instrument']}")

            if exit_flag in ("TIME_EXIT_REVIEW", "TIME_REVIEW"):
                label = "MAX" if exit_flag == "TIME_EXIT_REVIEW" else "SOFT"
                add(f"> ⚠️ **TIME EXIT REVIEW ({label})** — Held {pos['days_held']} trading days. "
                    f"Consider exiting before capital becomes stale.")
                add("")

            # Show partial exit and trailing stop status
            if pos.get("partial_exit_taken"):
                add(f"> ✅ **Partial profit booked:** Sold {pos.get('partial_shares_sold', '?')} shares, "
                    f"locked in ₹{pos.get('partial_pnl_booked', 0):+,.2f}. "
                    f"Remaining {pos['shares']} shares riding with stop at breakeven.")
                add("")
            if pos.get("trailing_stop_active") and not pos.get("partial_exit_taken"):
                add(f"> 🛡️ **Trailing stop active:** Stop moved to breakeven (₹{pos['entry_price']:,.4f}). "
                    f"This trade can no longer lose money.")
                add("")

            add("| Field | Value |")
            add("|-------|-------|")
            add(f"| Entry Date | {pos['entry_date']} |")
            add(f"| Entry Price | ₹{pos['entry_price']:,.4f} |")
            add(f"| Current Price | ₹{pos.get('current_price', '?'):,.4f} |")
            add(f"| Shares | {pos['shares']}{' (after partial exit)' if pos.get('partial_exit_taken') else ''} |")
            add(f"| Capital Deployed | ₹{pos['capital_deployed']:,.2f} |")
            add(f"| 🎯 Target (+{profit_pct}%) | **₹{pos['target_price']:,.4f}** |")
            add(f"| 🛑 Stop-Loss | **₹{pos['stop_price']:,.4f}**{' (🟢 breakeven)' if pos.get('trailing_stop_active') else ''} |")
            add(f"| P&L | {pnl_em} **₹{pnl:+,.2f} ({pnl_pct:+.2f}%)** |")
            add(f"| Distance to Target | {pos.get('pct_to_target', 0):.2f}% remaining |")
            add(f"| Distance to Stop | {pos.get('pct_to_stop', 0):.2f}% buffer |")
            add(f"| Trading Days Held | {pos.get('days_held', 0)} / {exit_rules['max_hold_days']} |")
            add(f"| Action | {'⚠️ **REVIEW EXIT**' if exit_flag else '✅ **HOLD**'} |")
            add("")
    else:
        add("*No open positions. Capital fully idle — looking for new entries.*")
        add("")

    # ── Entry Candidates ──────────────────────────────────────────────────────
    add("---")
    add("## 🎯 Entry Candidates")
    add("")

    if candidates:
        for i, cand in enumerate(candidates, 1):
            sig  = cand["signals_snapshot"]
            comp = cand["component_scores"]
            vixf = cand["vix_factor"]

            add(f"### #{i} — {cand['ticker']}")
            add(f"**Composite Score:** {cand['composite_score']:.1f} / 100 &nbsp;|&nbsp; "
                f"**Strategy:** {cfg['label']} &nbsp;|&nbsp; "
                f"**Category:** {cand['category'].replace('_', ' ').title()}")
            add("")

            if vixf < 1.0:
                add(f"> ⚠️ Position sized at **{int(vixf*100)}%** of normal due to elevated VIX")
                add("")

            add("| Field | Value |")
            add("|-------|-------|")
            add(f"| Current Price | ₹{cand['current_price']:,.4f} |")
            add(f"| 🟢 **Buy at (market/limit)** | **₹{cand['current_price']:,.4f}** |")
            add(f"| **Shares to Buy** | **{cand['shares']}** |")
            add(f"| **Capital to Deploy** | **₹{cand['capital_to_deploy']:,.2f}** |")
            add(f"| 🎯 **Target Price (+{profit_pct}%)** | **₹{cand['target_price']:,.4f}** |")
            add(f"| 🛑 **Stop-Loss ({exit_rules['stop_loss_atr_multiplier']}×ATR)** | **₹{cand['stop_price']:,.4f}** |")
            add(f"| ATR(14) | ₹{cand['atr14']:.4f} |")
            add(f"| Max Risk (if stop hit) | ₹{cand['risk_amount']:,.2f} ({cand['risk_pct']:.2f}% of deployed) |")
            add(f"| Risk Budget (ATR-sized) | ₹{cand.get('risk_budget', 0):,.2f} |")
            if mode == "stock":
                hold_hint = f"~{exit_rules['max_hold_days']} trading days (~4 weeks)"
                add(f"| Expected Hold Period | {hold_hint} |")
            add("")

            # Signal breakdown
            add("**Signal Breakdown:**")
            add("")
            add("| Indicator | Raw Value | Signal |")
            add("|-----------|-----------|--------|")
            add(f"| RSI(14) | {sig['rsi']:.1f} | {comp.get('rsi_signal', 0):+.3f} |")
            add(f"| EMA Trend | {'🟢 EMA9>21' if sig['ema9_above_ema21'] else '🔴 EMA9<21'}"
                f"{'  🔔Fresh!' if sig.get('fresh_bullish_cross') else ''} | {comp.get('ema_signal', 0):+.3f} |")

            if mode == "stock":
                dist_pct = sig.get("ema21_proximity_pct", 0) * 100
                add(f"| EMA21 Proximity | {dist_pct:+.2f}% from EMA21 {'🟢' if sig.get('price_near_ema21') else '🔴'} | {comp.get('pullback_signal', 0):+.3f} |")
            else:
                add(f"| Bollinger | {'Below Lower 🟢' if sig['price_below_bb_lower'] else 'Above Lower'} | {comp.get('bb_signal', 0):+.3f} |")

            add(f"| Volume Z-score | {sig['volume_zscore']:.2f} | {comp.get('volume_signal', 0):+.3f} |")
            add(f"| News Sentiment | — | {comp.get('news_signal', 0):+.3f} |")
            add(f"| Macro Filter | — | {comp.get('macro_signal', 0):+.3f} |")
            add("")

            # Entry checklist
            if mode == "stock":
                add("**Entry Checklist** *(all 7 must be ✅)*")
                add("")
                for line in _stock_entry_checklist(cand, sig):
                    add(line)
            else:
                add("**Entry Checklist** *(all 4 must be ✅)*")
                add("")
                for line in _etf_entry_checklist(cand, sig):
                    add(line)
            add("")

            # Groww action
            add("> **Action on Groww:**")
            add(f"> 1. Search `{cand['ticker'].replace('.NS', '')}` → Buy **{cand['shares']} shares** at market")
            add(f"> 2. Immediately place GTT (Good-Till-Triggered) sell at **₹{cand['target_price']:,.2f}** (target)")
            add(f"> 3. Place Stop-Loss sell at **₹{cand['stop_price']:,.2f}**")
            if mode == "stock":
                add(f"> 4. Run `python scripts/update_position.py --mode stock` to record the trade")
            else:
                add(f"> 4. Run `python scripts/update_position.py --mode etf` to record the trade")
            add("")

    else:
        add("*No entry candidates right now. All conditions not met or max positions reached.*")
        add("")

        # Near-miss watchlist
        ranked    = sorted(scores.values(), key=lambda x: x["composite_score"], reverse=True)
        near_miss = [x for x in ranked if not x["meets_entry"]][:5]

        if near_miss:
            add("**🔍 Monitor These (Getting Closer):**")
            add("")
            add("| Ticker | Score | Blocking Reason |")
            add("|--------|-------|-----------------|")
            for item in near_miss:
                tk  = item["ticker"]
                sig = signals.get(tk, {})
                ec  = item["entry_conditions"]
                reasons = []
                if mode == "stock":
                    if not ec.get("rsi_pullback_zone"):
                        reasons.append(f"RSI={sig.get('rsi',0):.0f} (need 42–55)")
                    if not ec.get("ema21_above_ema50"):
                        reasons.append("EMA21 < EMA50")
                    if not ec.get("price_near_ema21"):
                        dist = sig.get("ema21_proximity_pct", 0) * 100
                        reasons.append(f"Price {dist:+.1f}% from EMA21 (need ±4%)")
                    if not ec.get("volume_calm"):
                        reasons.append(f"VolZ={sig.get('volume_zscore',0):.1f} (need ≤2.0)")
                    if not ec.get("nifty_trend_ok", True):
                        reasons.append("Nifty below 20-EMA ❌")
                    if not ec.get("sector_strength_ok", True):
                        reasons.append("Sector underperforming ❌")
                else:
                    if not ec.get("rsi_oversold"):
                        reasons.append(f"RSI={sig.get('rsi',0):.0f} (need <38)")
                    if not ec.get("above_ema50"):
                        reasons.append("Below EMA50")
                    if not ec.get("volume_confirmed"):
                        reasons.append(f"VolZ={sig.get('volume_zscore',0):.1f} (need ≥1.5)")
                if not ec.get("score_sufficient"):
                    reasons.append(f"Score={item['composite_score']:.0f} (need ≥{entry_rules.get('min_composite_score',40)})")
                add(f"| {tk} | {item['composite_score']:.1f} | {' · '.join(reasons)} |")
            add("")

    # ── News ──────────────────────────────────────────────────────────────────
    add("---")
    add("## 📰 News & Sentiment")
    add("")

    if news_data:
        msent = news_data.get("market_sentiment", 0)
        sent_label = "🟢 Positive" if msent > 0.1 else "🔴 Negative" if msent < -0.1 else "🟡 Neutral"
        add(f"**Market Sentiment:** {sent_label} ({msent:+.2f})")
        add("")

        headlines = news_data.get("headlines_sample", [])
        if headlines:
            add("**Top Headlines:**")
            add("")
            for h in headlines[:6]:
                add(f"- {h}")
            add("")

        notable = [
            (tk, s) for tk, s in news_data.get("ticker_sentiment", {}).items()
            if abs(s.get("score", 0)) >= 0.3 and s.get("mentions", 0) > 0
        ]
        if notable:
            add("**Instrument News Flags:**")
            add("")
            for tk, s in sorted(notable, key=lambda x: -abs(x[1]["score"]))[:6]:
                em = "📈" if s["score"] > 0 else "📉"
                add(f"- **{tk}** {em} (sentiment {s['score']:+.2f}) — "
                    f"{s['headlines'][0] if s['headlines'] else 'see RSS'}")
            add("")
    else:
        add("*News data unavailable.*")
        add("")

    # ── Full Rankings ─────────────────────────────────────────────────────────
    add("---")
    add("## 📋 Full Watchlist Rankings")
    add("")

    if mode == "stock":
        add("| # | Ticker | Score | RSI | EMA Align | Near EMA21 | Vol-Z | Action |")
        add("|---|--------|-------|-----|-----------|------------|-------|--------|")
        ranked = sorted(scores.values(), key=lambda x: x["composite_score"], reverse=True)
        for i, item in enumerate(ranked, 1):
            tk    = item["ticker"]
            sig   = signals.get(tk, {})
            rsi   = sig.get("rsi", 0)
            vz    = sig.get("volume_zscore", 0)
            ema_a = "🟢" if sig.get("ema21_above_ema50") else "🔴"
            near  = "✅" if sig.get("price_near_ema21") else "—"
            act   = "🎯 ENTRY" if item["meets_entry"] else "👀 Watch" if item["composite_score"] > 30 else "⏸ Skip"
            add(f"| {i} | {tk} | {item['composite_score']:.1f} | {rsi:.0f} | {ema_a} | {near} | {vz:.1f} | {act} |")
    else:
        add("| # | Ticker | Score | RSI | EMA | Vol-Z | 52W High | Action |")
        add("|---|--------|-------|-----|-----|-------|----------|--------|")
        ranked = sorted(scores.values(), key=lambda x: x["composite_score"], reverse=True)
        for i, item in enumerate(ranked, 1):
            tk  = item["ticker"]
            sig = signals.get(tk, {})
            rsi = sig.get("rsi", 0)
            vz  = sig.get("volume_zscore", 0)
            ema = "🟢" if sig.get("ema9_above_ema21") else "🔴"
            h52 = sig.get("pct_from_52w_high", 0)
            act = "🎯 ENTRY" if item["meets_entry"] else "👀 Watch" if item["composite_score"] > 20 else "⏸ Skip"
            add(f"| {i} | {tk} | {item['composite_score']:.1f} | {rsi:.0f} | {ema} | {vz:.1f} | {h52:.1f}% | {act} |")
    add("")

    # ── Performance ───────────────────────────────────────────────────────────
    add("---")
    add(f"## 📈 Strategy Performance — {cfg['label']} (Closed Trades)")
    add("")

    perf = performance_summary(cfg["history_file"])
    if perf:
        em = "📈" if perf["total_pnl"] >= 0 else "📉"
        add("| Metric | Value |")
        add("|--------|-------|")
        add(f"| Total Trades | {perf['total_trades']} |")
        add(f"| Win Rate | {perf['win_rate']}% ({perf['wins']}W / {perf['losses']}L) |")
        add(f"| Total P&L | {em} ₹{perf['total_pnl']:+,.2f} |")
        add(f"| Avg Win | ₹{perf['avg_win']:+,.2f} |")
        add(f"| Avg Loss | ₹{perf['avg_loss']:+,.2f} |")
        add(f"| Best Trade | {perf['best_pct']:+.2f}% |")
        add(f"| Worst Trade | {perf['worst_pct']:+.2f}% |")
        if perf.get("exit_reasons"):
            add(f"| Exit Breakdown | " +
                " · ".join(f"{k}: {v}" for k, v in perf["exit_reasons"].items()) +
                " |")
    else:
        add("*No closed trades yet — performance data will populate after first trade cycle.*")
    add("")

    # ── Footer ────────────────────────────────────────────────────────────────
    add("---")
    add(f"*Generated by Trading Advisory System v2.0 | {today_str} {get_ist_now().strftime('%H:%M')} IST*  ")
    add(f"*Mode: {cfg['label']} | ⚠️ Personal research tool only. Not SEBI-registered advice.*  ")
    add(f"*All decisions are manual. STCG tax (20%) applies on gains held < 1 year.*")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    args      = parse_args()
    cfg       = get_mode_config(args.mode)
    today_str = get_ist_now().strftime("%Y-%m-%d")

    for path in [cfg["signals_cache"], cfg["scores_cache"], MACRO_CACHE]:
        if not os.path.exists(path):
            logger.critical(f"Required cache missing: {path}")
            sys.exit(1)

    with open(cfg["signals_cache"], "r") as f:
        signals = json.load(f)
    with open(cfg["scores_cache"], "r") as f:
        scores = json.load(f)
    with open(MACRO_CACHE, "r") as f:
        macro_data = json.load(f)

    news_data = None
    if os.path.exists(NEWS_CACHE):
        with open(NEWS_CACHE, "r") as f:
            news_data = json.load(f)

    positions            = load_positions(cfg["positions_file"])
    open_pos, closed_pos = process_open_positions(positions, signals, today_str, cfg)

    candidates = get_entry_candidates(scores, signals, open_pos, macro_data, cfg)

    save_positions(open_pos, cfg["positions_file"])

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = build_report(
        today_str, open_pos, closed_pos, candidates,
        scores, signals, macro_data, news_data, cfg
    )
    with open(cfg["report_file"], "w", encoding="utf-8") as f:
        f.write(report)

    # Archive a copy into a date-based folder
    dated_dir = os.path.join(REPORTS_DIR, today_str)
    os.makedirs(dated_dir, exist_ok=True)
    archived_file = os.path.join(dated_dir, os.path.basename(cfg["report_file"]))
    shutil.copy2(cfg["report_file"], archived_file)

    logger.info(f"Report written → {cfg['report_file']}")
    logger.info(f"Report archived → {archived_file}")

    print(f"\n{'='*60}")
    print(f"  MODE             : {cfg['label']}")
    print(f"  REPORT GENERATED : {today_str}")
    print(f"  Open positions   : {len(open_pos)}")
    print(f"  Closed today     : {len(closed_pos)}")
    print(f"  Entry candidates : {len(candidates)}")
    if candidates:
        for c in candidates:
            print(
                f"    → {c['ticker']:<22} "
                f"Buy {c['shares']} shares @ ₹{c['current_price']:,.2f} | "
                f"Target ₹{c['target_price']:,.2f} | Stop ₹{c['stop_price']:,.2f}"
            )
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
