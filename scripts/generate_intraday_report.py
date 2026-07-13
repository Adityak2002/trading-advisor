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
from gemini_helper import get_gemini_summary

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
    lines.append(f"> Auto-generated at **{time_str} IST** | Strategy: Opening Price Breakout | Capital: ₹{position_sizing['total_capital']:,} | Square-Off Time: {exit_rules['hard_squareoff_time']} IST")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Strategy Summary ─────────────────────────────────────────────────────
    lines.append("## 🎯 Strategy Summary")
    lines.append("")
    lines.append(f"- **Opening Price Range:** Monitored during first {entry_rules['orb_period_minutes']} minutes (9:15–9:30 AM)")
    lines.append(f"- **Buy Signal:** Price breaks above the opening high with a strong volume surge (≥{entry_rules['min_volume_multiplier']}× average volume)")
    lines.append(f"- **Exit Target:** +{exit_rules['profit_target_pct']*100:.1f}% profit | **Stop Loss:** -{exit_rules['stop_loss_pct']*100:.1f}% risk | **R:R = 3:1**")
    lines.append(f"- **No Overnight Positions:** Auto-closes at **{exit_rules['hard_squareoff_time']} IST** to prevent overnight risk")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── All Stocks Snapshot ───────────────────────────────────────────────────
    lines.append("## 📊 Watchlist Snapshot")
    lines.append("")
    lines.append("| Ticker | Price (₹) | Breakout Status | Action Score | Momentum | Above Average Price? | Volume Surge | Entry? |")
    lines.append("|--------|-----------|-----------------|--------------|----------|----------------------|--------------|--------|")
    for item in ranked:
        t   = item["ticker"]
        sig = signals.get(t, {})
        icon = status_icon(item["orb_status"])
        entry_str = "🎯 BUY" if item["meets_entry"] else "—"
        vwap_str  = "✅ Yes" if sig.get("price_above_vwap") else "❌ No"
        vol_m = sig.get("volume_multiplier", 0)
        vol_str = f"{vol_m:.1f}×" if vol_m > 0 else "—"
        status_label = "Broken Out 🔼" if item["orb_status"] == "breakout_long" else "Broken Down 🔽" if item["orb_status"] == "breakout_short" else "Inside Range ▶"

        lines.append(
            f"| **{t}** | ₹{sig.get('current_price', 0):,.2f} | {icon} {status_label} "
            f"| {item['composite_score']:.1f}/100 | {sig.get('rsi', 0):.0f} "
            f"| {vwap_str} | {vol_str} | {entry_str} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Entry Candidates ─────────────────────────────────────────────────────
    if candidates:
        lines.append("## 🎯 Active Buy Signals (Entry Candidates)")
        lines.append("")

        for item in candidates:
            t   = item["ticker"]
            sig = signals.get(t, {})
            levels = compute_trade_levels(sig, exit_rules, position_sizing)

            lines.append(f"### {status_icon(item['orb_status'])} {t}")
            lines.append("")
            lines.append(f"**Action Rating:** Strong (Score: {item['composite_score']:.1f}/100) | Opening Range: ₹{sig.get('orb_low', 0):.2f} – ₹{sig.get('orb_high', 0):.2f}")
            lines.append("")
            lines.append("| Action | Price | Notes |")
            lines.append("|---|---|---|")
            add_buffer = entry_rules.get("breakout_buffer_pct", 0.001) * 100
            lines.append(f"| 🟢 **Buy Trigger** | **₹{levels['entry']:.2f}** | Buy if price breaks above ORB high (with {add_buffer:.1f}% buffer) |")
            lines.append(f"| 🎯 **Target (Profit)** | **₹{levels['target']:.2f}** | Auto-sell at +{exit_rules['profit_target_pct']*100:.1f}% profit |")
            lines.append(f"| 🛑 **Stop-Loss** | **₹{levels['stop']:.2f}** | Auto-sell at -{exit_rules['stop_loss_pct']*100:.1f}% to limit loss |")
            lines.append("")
            lines.append(f"**Recommended Trade:** Buy **{levels['shares']} shares** (Total Investment: **₹{levels['capital_deployed']:,}** | Max Risk if stop hit: ₹{levels['risk_amount']:.0f})")
            lines.append("")

            ec = item["entry_conditions"]
            lines.append("**Simple Entry Checklist:**")
            lines.append(f"- {format_condition(ec.get('orb_breakout_confirmed', False))} Price has broken above the opening high")
            lines.append(f"- {format_condition(ec.get('volume_sufficient', False))} Strong buying volume confirmed ({sig.get('volume_multiplier', 0):.1f}x vs target {entry_rules['min_volume_multiplier']}x)")
            lines.append(f"- {format_condition(ec.get('price_above_vwap', False))} Price is trading above daily average price (₹{sig.get('vwap', 0):.2f})")
            lines.append(f"- {format_condition(ec.get('rsi_not_overbought', False))} Stock is not overbought / over-extended (Momentum: {sig.get('rsi', 0):.1f})")
            lines.append(f"- {format_condition(ec.get('score_sufficient', False))} Setup strength rating is high (Score ≥ {entry_rules['min_composite_score']})")
            lines.append(f"- {format_condition(ec.get('time_ok', False))} Trade window is open (must enter before {entry_rules['max_entry_time_ist']} IST)")
            lines.append("")
            
            lines.append("> **Action on Groww:**")
            lines.append(f"> 1. Search `{t.replace('.NS', '')}` ➔ Buy **{levels['shares']} shares** at limit order of **₹{levels['entry']:.2f}**")
            lines.append(f"> 2. Immediately place GTC/GTT Sell order at **₹{levels['target']:.2f}** (Target)")
            lines.append(f"> 3. Place GTC/GTT Stop-Loss Sell order at **₹{levels['stop']:.2f}** (Stop)")
            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("## 🎯 Active Buy Signals (Entry Candidates)")
        lines.append("")
        lines.append("> **No active buy signals at this time.** Watchlist is stable, waiting for opening range breakouts.")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Stocks to Watch ───────────────────────────────────────────────────────
    if watching:
        lines.append("## 👁️ Stocks to Watch (Building Setup)")
        lines.append("")
        lines.append("| Ticker | Current Price | Opening High | Opening Low | Momentum | Above Average Price? |")
        lines.append("|--------|--------------|--------------|-------------|----------|----------------------|")
        for item in watching[:6]:
            t   = item["ticker"]
            sig = signals.get(t, {})
            vwap_str = "🟢 Yes" if sig.get("price_above_vwap") else "🔴 No"
            lines.append(
                f"| {t} | ₹{sig.get('current_price', 0):,.2f} "
                f"| ₹{sig.get('orb_high', 0):.2f} | ₹{sig.get('orb_low', 0):.2f} "
                f"| {sig.get('rsi', 0):.1f} | {vwap_str} |"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Risk Reminders ────────────────────────────────────────────────────────
    lines.append("## ⚠️ Crucial Risk Management Rules")
    lines.append("")
    lines.append(f"- 🕒 **Auto-Close at {exit_rules['hard_squareoff_time']} IST** ➔ Exit all positions before market close, no overnight carries.")
    lines.append(f"- 🛑 Max **{position_sizing['max_positions']} trades at once** ➔ Keep focus tight, do not over-trade.")
    lines.append(f"- 📉 Risk cap: **₹{position_sizing['total_capital'] * position_sizing['risk_per_trade_pct']:.0f} max loss per trade** ({position_sizing['risk_per_trade_pct']*100:.0f}% of capital).")
    lines.append(f"- 🚫 **Never add to a losing trade** ➔ If the stop loss is triggered, exit immediately.")
    lines.append(f"- ⚡ Trailing stop moves to breakeven at +{exit_rules['trailing_trigger_pct']*100:.1f}% profit (trails {exit_rules['trailing_stop_pct']*100:.1f}% below highs).")
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

    try:
        print("Generating AI Insights Summary...")
        ai_summary = get_gemini_summary(report)
        full_report = f"# 🤖 Gemini AI Insights\n\n{ai_summary}\n\n---\n\n{report}"
    except Exception as e:
        print(f"Error generating AI Summary: {e}")
        full_report = report

    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(cfg["report_file"], "w", encoding="utf-8") as f:
        f.write(full_report)

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
