# =============================================================================
# generate_intraday_report.py — Step 4 (Intraday): Write the intraday report
#
# Reads  : signals_intraday.json + scores_intraday.json
# Writes : reports/intraday_report.md + reports/YYYY-MM-DD/intraday_report.md
# =============================================================================

import sys
import os
import shutil
sys.path.insert(0, os.path.dirname(__file__))

import json
import logging
from datetime import datetime, timedelta

from config import get_mode_config, REPORTS_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def get_ist_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def status_icon(orb_status: str) -> str:
    return {"breakout_long": "🔼", "breakout_short": "🔽", "inside": "▶"}.get(orb_status, "▶")


def format_condition(val: bool) -> str:
    return "✅" if val else "❌"


def compute_trade_levels(sig: dict, exit_rules: dict, position_sizing: dict) -> dict:
    """Compute entry, target, stop-loss, and position size."""
    entry = sig["orb_buy_level"]
    stop  = round(entry * (1 - exit_rules["stop_loss_pct"]), 4)
    target = round(entry * (1 + exit_rules["profit_target_pct"]), 4)

    risk_per_trade = position_sizing["total_capital"] * position_sizing["risk_per_trade_pct"]
    risk_per_share = entry - stop
    shares = int(risk_per_trade / risk_per_share) if risk_per_share > 0 else 0
    capital_deployed = round(shares * entry, 2)

    return {
        "entry":            entry,
        "target":           target,
        "stop":             stop,
        "risk_reward":      round((target - entry) / (entry - stop), 2) if entry > stop else 0,
        "shares":           shares,
        "capital_deployed": capital_deployed,
        "risk_amount":      round(shares * (entry - stop), 2),
    }


def build_report(signals: dict, scores: dict, cfg: dict) -> str:
    ist_now = get_ist_now()
    today_str = ist_now.strftime("%Y-%m-%d")
    time_str  = ist_now.strftime("%H:%M")
    entry_rules = cfg["entry_rules"]
    exit_rules  = cfg["exit_rules"]
    position_sizing = cfg["position_sizing"]

    # Sort by composite score
    ranked = sorted(scores.values(), key=lambda x: x["composite_score"], reverse=True)
    candidates = [x for x in ranked if x["meets_entry"]]
    watching   = [x for x in ranked if not x["meets_entry"] and x["orb_status"] != "breakout_short"]

    lines = []

    # ── Header ───────────────────────────────────────────────────────────────
    lines.append(f"# 📈 Intraday Report — {today_str}")
    lines.append("")
    lines.append(f"> Auto-generated at **{time_str} IST** | Strategy: Opening Range Breakout (ORB) | Capital: ₹{position_sizing['total_capital']:,} | Hard Square-Off: {exit_rules['hard_squareoff_time']} IST")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Strategy Summary ─────────────────────────────────────────────────────
    lines.append("## 🎯 Strategy: Opening Range Breakout (ORB)")
    lines.append("")
    lines.append(f"- **Opening Range Period:** First {entry_rules['orb_period_minutes']} minutes of the session (9:15–9:30 IST)")
    lines.append(f"- **Buy Signal:** Price breaks above the OR High with ≥{entry_rules['min_volume_multiplier']}× average volume")
    lines.append(f"- **Target:** +{exit_rules['profit_target_pct']*100:.1f}% per trade | **Stop Loss:** -{exit_rules['stop_loss_pct']*100:.1f}% | **R:R = 2:1**")
    lines.append(f"- **Hard Square-Off:** {exit_rules['hard_squareoff_time']} IST — NO overnight positions")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── All Stocks Snapshot ───────────────────────────────────────────────────
    lines.append("## 📊 Watchlist Snapshot")
    lines.append("")
    lines.append("| Ticker | Price (₹) | ORB Status | Score | RSI | VWAP | Vol Mult | Entry? |")
    lines.append("|--------|-----------|------------|-------|-----|------|----------|--------|")

    for item in ranked:
        t   = item["ticker"]
        sig = signals.get(t, {})
        icon = status_icon(item["orb_status"])
        entry_str = "🎯" if item["meets_entry"] else "—"
        vwap_str  = "✅" if sig.get("price_above_vwap") else "❌"
        vol_m = sig.get("volume_multiplier", 0)
        vol_str = f"{vol_m:.1f}×" if vol_m > 0 else "—"

        lines.append(
            f"| **{t}** | ₹{sig.get('current_price', 0):,.2f} | {icon} {item['orb_status']} "
            f"| {item['composite_score']:.1f} | {sig.get('rsi', 0):.1f} "
            f"| {vwap_str} | {vol_str} | {entry_str} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Entry Candidates ─────────────────────────────────────────────────────
    if candidates:
        lines.append("## 🎯 Entry Candidates")
        lines.append("")

        for item in candidates:
            t   = item["ticker"]
            sig = signals.get(t, {})
            levels = compute_trade_levels(sig, exit_rules, position_sizing)

            lines.append(f"### {status_icon(item['orb_status'])} {t}")
            lines.append("")
            lines.append(f"**Composite Score: {item['composite_score']:.1f}/100** | ORB Range: ₹{sig.get('orb_low', 0):.2f} – ₹{sig.get('orb_high', 0):.2f} ({sig.get('orb_range_pct', 0):.2f}% wide)")
            lines.append("")
            lines.append("| Level | Price | Notes |")
            lines.append("|-------|-------|-------|")
            lines.append(f"| 🟢 **Entry**  | ₹{levels['entry']:.2f} | 0.1% above ORB High |")
            lines.append(f"| 🎯 **Target** | ₹{levels['target']:.2f} | +{exit_rules['profit_target_pct']*100:.1f}% from entry |")
            lines.append(f"| 🔴 **Stop**   | ₹{levels['stop']:.2f} | -{exit_rules['stop_loss_pct']*100:.1f}% from entry |")
            lines.append("")
            lines.append(f"**Position:** {levels['shares']} shares × ₹{levels['entry']:.2f} = **₹{levels['capital_deployed']:,}** deployed | Risk: ₹{levels['risk_amount']:.0f} | R:R = {levels['risk_reward']}:1")
            lines.append("")

            ec = item["entry_conditions"]
            lines.append("**Entry Checklist:**")
            lines.append(f"- {format_condition(ec.get('orb_breakout_confirmed', False))} ORB Long Breakout Confirmed")
            lines.append(f"- {format_condition(ec.get('volume_sufficient', False))} Volume Multiplier ≥ {entry_rules['min_volume_multiplier']}×")
            lines.append(f"- {format_condition(ec.get('price_above_vwap', False))} Price Above VWAP (₹{sig.get('vwap', 0):.2f})")
            lines.append(f"- {format_condition(ec.get('rsi_not_overbought', False))} RSI ≤ {entry_rules['rsi_max']} (Current: {sig.get('rsi', 0):.1f})")
            lines.append(f"- {format_condition(ec.get('score_sufficient', False))} Composite Score ≥ {entry_rules['min_composite_score']}")
            lines.append(f"- {format_condition(ec.get('time_ok', False))} Entry Window Open (before {entry_rules['max_entry_time_ist']} IST)")
            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("## 🎯 Entry Candidates")
        lines.append("")
        lines.append("> **No confirmed ORB breakouts at this time.** Monitoring the watchlist for developing setups.")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Stocks to Watch ───────────────────────────────────────────────────────
    if watching:
        lines.append("## 👁️ Stocks Building Setup (Inside ORB Range)")
        lines.append("")
        lines.append("| Ticker | Current Price | ORB High | ORB Low | RSI | VWAP |")
        lines.append("|--------|--------------|----------|---------|-----|------|")
        for item in watching[:6]:
            t   = item["ticker"]
            sig = signals.get(t, {})
            vwap_str = "✅" if sig.get("price_above_vwap") else "❌"
            lines.append(
                f"| {t} | ₹{sig.get('current_price', 0):,.2f} "
                f"| ₹{sig.get('orb_high', 0):.2f} | ₹{sig.get('orb_low', 0):.2f} "
                f"| {sig.get('rsi', 0):.1f} | {vwap_str} |"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Risk Reminders ────────────────────────────────────────────────────────
    lines.append("## ⚠️ Risk Management Rules")
    lines.append("")
    lines.append(f"- 🕒 **Hard Square-Off at {exit_rules['hard_squareoff_time']} IST** — Close ALL positions regardless of P&L.")
    lines.append(f"- 🛑 Max **{position_sizing['max_positions']} concurrent positions** — Do not over-trade.")
    lines.append(f"- 📉 Risk max **₹{position_sizing['total_capital'] * position_sizing['risk_per_trade_pct']:.0f} per trade** ({position_sizing['risk_per_trade_pct']*100:.0f}% of corpus).")
    lines.append(f"- 🚫 **Never average down** on an intraday position — exit if stop is hit.")
    lines.append(f"- ⚡ Trailing stop activates at +{exit_rules['trailing_trigger_pct']*100:.1f}% — trail {exit_rules['trailing_stop_pct']*100:.1f}% below running high.")
    lines.append("")

    return "\n".join(lines)


def main():
    cfg = get_mode_config("intraday")

    for path in [cfg["signals_cache"], cfg["scores_cache"]]:
        if not os.path.exists(path):
            logger.critical(f"Required file missing: {path}")
            sys.exit(1)

    with open(cfg["signals_cache"], "r") as f:
        signals = json.load(f)
    with open(cfg["scores_cache"], "r") as f:
        scores = json.load(f)

    report = build_report(signals, scores, cfg)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(cfg["report_file"], "w", encoding="utf-8") as f:
        f.write(report)

    # Archive dated copy
    ist_now = get_ist_now()
    today_str = ist_now.strftime("%Y-%m-%d")
    dated_dir = os.path.join(REPORTS_DIR, today_str)
    os.makedirs(dated_dir, exist_ok=True)
    archived_file = os.path.join(dated_dir, "intraday_report.md")
    shutil.copy2(cfg["report_file"], archived_file)

    logger.info(f"Report written → {cfg['report_file']}")
    logger.info(f"Report archived → {archived_file}")

    candidates = [t for t, sc in scores.items() if sc["meets_entry"]]

    print(f"\n{'='*60}")
    print(f"  MODE         : Intraday (ORB)")
    print(f"  TIME IST     : {ist_now.strftime('%H:%M')}")
    print(f"  CANDIDATES   : {len(candidates)}")
    if candidates:
        print(f"  STOCKS       : {', '.join(candidates)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
