# =============================================================================
# config.py — Central configuration for Trading Advisory System
# Two modes:
#   etf   → ETF/MF swing trading corpus (₹10,000) — runs once daily
#   stock → Stock delivery/positional corpus (₹10,000) — runs every 2 hours
#
# All tunable settings live here. Never touch other scripts to change strategy.
# =============================================================================

import os

# ---------------------------------------------------------------------------
# ── MODE A: ETF / MF SWING TRADING WATCHLIST ─────────────────────────────
# Verify any ticker at: https://finance.yahoo.com/quote/<TICKER>
# All NSE instruments use the ".NS" suffix on Yahoo Finance.
# ---------------------------------------------------------------------------

WATCHLIST = {

    # ── Indian Sectoral / Thematic ETFs ─────────────────────────────────────
    # Lower single-stock risk; catch sector-wide momentum moves.
    "etf_sectoral": [
        "BANKBEES.NS",        # Nippon India ETF Bank BeES (broad banking)
        "PSUBNKBEES.NS",      # Nippon India ETF PSU Bank BeES
        "PHARMABEES.NS",      # Nippon India ETF Pharma BeES
        "ITETF.NS",           # ICICI Prudential IT ETF
        "AUTOBEES.NS",        # Mirae Asset Auto ETF
        "JUNIORBEES.NS",      # Nippon India ETF Junior BeES (Next 50 / midcap)
    ],

    # ── Commodity ETFs ───────────────────────────────────────────────────────
    # Crude Oil ETF gives exposure to energy price moves.
    "etf_commodity": [
        "OILIETF.NS",         # ICICI Prudential Crude Oil ETF (tracks WTI)
    ],

    # ── International ETFs (listed on NSE/BSE, traded in INR) ───────────────
    # USD-linked; benefits from rising dollar + global tech momentum.
    # Max 1 international position at a time (currency layered risk).
    "etf_international": [
        "N100.NS",            # Motilal Oswal NASDAQ 100 ETF
        "MAFANG.NS",          # Motilal Oswal FANG+ ETF (US Big Tech)
        "HNGSNGBEES.NS",      # Mirae Asset Hang Seng ETF
        "NIFTYIETF.NS",       # Nippon India Nifty IT ETF (alternate to ITETF)
    ],

    # ── Liquid Mid / Small-Cap Stocks (swing only) ───────────────────────────
    # High-beta, sector-driven — used for oversold bounce plays.
    "stocks": [
        "IRFC.NS",            # Indian Railway Finance Corp (infra/PSU)
        "RVNL.NS",            # Rail Vikas Nigam (infra)
        "IREDA.NS",           # Indian Renewable Energy Dev Agency
        "NHPC.NS",            # NHPC (hydropower / PSU)
        "RECLTD.NS",          # REC Limited (power finance)
        "TATAPOWER.NS",       # Tata Power (energy)
        "SUZLON.NS",          # Suzlon Energy (renewable, high beta)
        "CANBK.NS",           # Canara Bank (PSU bank)
        "BANKBARODA.NS",      # Bank of Baroda (PSU bank)
        "UNIONBANK.NS",       # Union Bank of India
        "ABFRL.NS",           # Aditya Birla Fashion (consumption)
        "HDFCAMC.NS",         # HDFC AMC (financials)
    ],
}

# ---------------------------------------------------------------------------
# ── MODE B: STOCK DELIVERY / POSITIONAL WATCHLIST ────────────────────────
# Strategy: Momentum Pullback — buy quality stocks dipping to EMA21
# in a confirmed uptrend (EMA9 > EMA21 > EMA50), target 10% in ~20 days.
# ---------------------------------------------------------------------------

STOCK_DELIVERY_WATCHLIST = {

    # ── Long-Term Hold (lower beta, high liquidity, consistent compounders) ──
    "long_term": [
        "ICICIBANK.NS",       # ICICI Bank — best-in-class private bank
        "HDFCBANK.NS",        # HDFC Bank — consistent compounder
        "RELIANCE.NS",        # Reliance Industries — diversified behemoth
    ],

    # ── Short-Term Fundamentally Strong (growth + liquid, strong momentum) ──
    "short_term_fundamentally_strong": [
        "CDSL.NS",            # Central Depository — market infra monopoly
        "POLYCAB.NS",         # Polycab — cables + wires, infra capex
        "BAJFINANCE.NS",      # Bajaj Finance — NBFC leader, trend follower
        "TITAN.NS",           # Titan — consumption, consistent uptrend
        "ANGELONE.NS",        # Angel One — fintech, high beta but liquid
        "PIDILITIND.NS",      # Pidilite — adhesives, steady compounder
        "KEI.NS",             # KEI Industries — electrical cables, infra
        "HAVELLS.NS",         # Havells — electricals + consumer durables
    ],
}

# ---------------------------------------------------------------------------
# MACRO / GLOBAL MARKET TICKERS (Yahoo Finance)
# Used for macro sentiment layer in composite scoring. Shared by both modes.
# ---------------------------------------------------------------------------

MACRO_TICKERS = {
    "nifty":      "^NSEI",       # Nifty 50 Index
    "sp500":      "^GSPC",       # S&P 500 (overnight global cue)
    "nasdaq":     "^IXIC",       # NASDAQ Composite
    "india_vix":  "^INDIAVIX",   # India VIX (fear gauge)
    "crude_oil":  "CL=F",        # WTI Crude Oil Futures
    "usd_inr":    "USDINR=X",    # USD/INR exchange rate
}

# ---------------------------------------------------------------------------
# SECTOR INDEX TICKERS — for relative strength comparison
# Used to suppress entries in stocks whose sector is underperforming Nifty.
# ---------------------------------------------------------------------------

SECTOR_TICKERS = {
    "bank_nifty":    "^NSEBANK",   # Nifty Bank (banking & financial services)
    "nifty_it":      "^CNXIT",     # Nifty IT
}

# Maps each stock ticker to its sector index key (from SECTOR_TICKERS).
# Stocks mapped to "nifty" use Nifty 50 itself as the benchmark.
STOCK_SECTOR_MAP = {
    "ICICIBANK.NS":   "bank_nifty",
    "HDFCBANK.NS":    "bank_nifty",
    "BAJFINANCE.NS":  "bank_nifty",
    "ANGELONE.NS":    "bank_nifty",
    "CDSL.NS":        "bank_nifty",
    "RELIANCE.NS":    "nifty",
    "TITAN.NS":       "nifty",
    "POLYCAB.NS":     "nifty",
    "KEI.NS":         "nifty",
    "HAVELLS.NS":     "nifty",
    "PIDILITIND.NS":  "nifty",
}

# Suppress stock entry if its sector underperforms Nifty by more than this %
SECTOR_UNDERPERFORM_THRESHOLD = -3.0  # percent

# ---------------------------------------------------------------------------
# ── MODE C: INTRADAY — WATCHLIST ─────────────────────────────────────────
# High-liquidity, high-beta NSE stocks that generate clean intraday moves.
# Only the top ~12 names by volume/liquidity — essential for tight spreads.
# ---------------------------------------------------------------------------

INTRADAY_WATCHLIST = [
    "RELIANCE.NS",     # Reliance Industries — highest market cap, liquid
    "ICICIBANK.NS",    # ICICI Bank — best intraday banking play
    "HDFCBANK.NS",     # HDFC Bank — consistent intraday mover
    "INFY.NS",         # Infosys — liquid IT large-cap
    "TCS.NS",          # TCS — liquid, responds to global IT cues
    "SBIN.NS",         # SBI — PSU bank, high-beta
    "TATAMOTORS.NS",   # Tata Motors — high-beta, EV plays
    "BAJFINANCE.NS",   # Bajaj Finance — NBFC, high-beta
    "AXISBANK.NS",     # Axis Bank — private bank, clean mover
    "ADANIENT.NS",     # Adani Enterprises — volatile, high-beta
    "WIPRO.NS",        # Wipro — IT, global cue follower
    "POWERGRID.NS",    # Power Grid — defensive high-volume
]

# ---------------------------------------------------------------------------
# ── MODE C: INTRADAY — SCORING WEIGHTS  (must sum to 1.0) ────────────────
# ORB breakout + volume confirmation are the primary drivers.
# ---------------------------------------------------------------------------

INTRADAY_WEIGHTS = {
    "orb_breakout": 0.40,   # Opening Range Breakout — most critical
    "volume":       0.25,   # Volume multiplier at breakout
    "vwap":         0.20,   # Price position relative to VWAP
    "rsi":          0.15,   # Intraday RSI momentum
}

# ── MODE C: INTRADAY — ENTRY RULES ───────────────────────────────────────

INTRADAY_ENTRY_RULES = {
    "min_composite_score":      55,    # Higher bar — intraday capital at stake
    "orb_period_minutes":       15,    # Opening range = first 15 minutes (9:15–9:30 IST)
    "breakout_buffer_pct":      0.001, # 0.1% buffer above OR High to confirm breakout
    "min_volume_multiplier":    1.8,   # Breakout candle volume must be 1.8× 5-min avg (up from 1.5)
    "rsi_max":                  70,    # Don't chase if already overbought (RSI > 70, down from 75)
    "max_entry_time_ist":       "13:30",# No new entries after 1:30 PM IST
    "max_open_positions":       2,     # Max concurrent intraday positions
    "require_nifty_trend":      True,  # Only buy when Nifty is trending up intraday
}

# ── MODE C: INTRADAY — EXIT RULES ────────────────────────────────────────

INTRADAY_EXIT_RULES = {
    "profit_target_pct":    0.012,  # 1.2% target per trade (up from 0.8% for 3:1 R:R)
    "stop_loss_pct":        0.004,  # 0.4% stop loss
    "hard_squareoff_time":  "15:10",# Hard square-off time — never carry intraday positions overnight
    "trailing_trigger_pct": 0.005, # Activate trailing stop at +0.5% profit
    "trailing_stop_pct":    0.003, # Trail 0.3% below the running high
}

# ── MODE C: INTRADAY — POSITION SIZING ───────────────────────────────────

INTRADAY_POSITION_SIZING = {
    "total_capital":        5000,   # ₹5,000 dedicated intraday corpus
    "risk_per_trade_pct":   0.02,   # Risk 2% of capital = ₹100 per trade
    "max_positions":        2,      # Max 2 concurrent intraday trades
}

# ---------------------------------------------------------------------------
# ── MODE A: ETF SWING — SCORING WEIGHTS  (must sum to 1.0) ──────────────
# ---------------------------------------------------------------------------

WEIGHTS = {
    "rsi":       0.25,   # RSI momentum oscillator
    "ema_cross": 0.25,   # EMA crossover trend signal
    "bollinger": 0.15,   # Bollinger Band mean-reversion
    "volume":    0.15,   # Volume Z-score confirmation
    "news":      0.10,   # RSS headline sentiment
    "macro":     0.10,   # Global macro filter (VIX, S&P, Nifty)
}

# ── MODE B: STOCK DELIVERY — SCORING WEIGHTS  (must sum to 1.0) ──────────
# Heavier on EMA alignment + pullback zone; lighter on news/macro.

STOCK_WEIGHTS = {
    "rsi":       0.20,   # RSI pullback zone (42–55 sweet spot)
    "ema_cross": 0.30,   # EMA alignment — most critical for momentum
    "pullback":  0.25,   # Price proximity to EMA21 (entry zone detector)
    "volume":    0.15,   # Volume calm during dip
    "news":      0.05,   # Minor weight — delivery trades aren't news-driven
    "macro":     0.05,   # Minor weight — macro matters less for quality stocks
}

# ---------------------------------------------------------------------------
# ── MODE A: ETF SWING — ENTRY RULES ─────────────────────────────────────
# All 4 conditions must be met simultaneously.
# ---------------------------------------------------------------------------

ENTRY_RULES = {
    "min_composite_score":       40,    # Composite score > 40 required
    "rsi_oversold_threshold":    38,    # RSI must be below this
    "volume_zscore_threshold":   1.5,   # Volume spike confirmation
    "max_open_positions":        2,     # Max concurrent positions
}

# ── MODE B: STOCK DELIVERY — ENTRY RULES ─────────────────────────────────
# Momentum pullback strategy — NOT oversold hunting.

STOCK_ENTRY_RULES = {
    "min_composite_score":       50,    # Higher bar — delivery capital at stake
    "rsi_pullback_min":          42,    # RSI floor (avoid falling knives)
    "rsi_pullback_max":          55,    # RSI ceiling (don't chase overbought)
    "ema21_proximity_pct":       0.04,  # Price within 4% of EMA21 = pullback zone
    "volume_zscore_max":         2.0,   # Calm volume during dip (< 2 = consolidating)
    "max_open_positions":        2,     # Max concurrent delivery positions
    "require_nifty_trend":       True,  # Hard gate: Nifty must be above 20-EMA
    "require_sector_strength":   True,  # Gate: stock's sector must not underperform
}

# ---------------------------------------------------------------------------
# ── MODE A: ETF SWING — POSITION SIZING ─────────────────────────────────
# ---------------------------------------------------------------------------

POSITION_SIZING = {
    "total_capital":                10000,  # ₹ total available
    "position_1_pct":               0.60,   # Primary position = 60% (₹6,000)
    "position_2_pct":               0.40,   # Secondary position = 40% (₹4,000)
    "max_crude_allocation":         3000,   # Crude ETF cap (volatile)
    "max_international_positions":  1,      # Only 1 intl ETF at a time
    "risk_per_trade_pct":           0.05,   # ATR risk sizing: risk 5% of capital per trade (₹500)
}

# ── MODE B: STOCK DELIVERY — POSITION SIZING ─────────────────────────────
# Keep ₹3,000 idle reserve — delivery trades need room for drawdown.

STOCK_POSITION_SIZING = {
    "total_capital":                10000,  # ₹ second corpus
    "position_1_pct":               0.70,   # Fallback if ATR sizing gives too many shares
    "position_2_pct":               0.30,   # Fallback secondary
    "idle_reserve":                 3000,   # Psychological buffer — don't deploy all
    "max_positions":                2,      # Max concurrent delivery positions
    "risk_per_trade_pct":           0.05,   # ATR risk sizing: risk 5% of capital per trade (₹500)
}

# ---------------------------------------------------------------------------
# ── MODE A: ETF SWING — EXIT RULES ──────────────────────────────────────
# ---------------------------------------------------------------------------

EXIT_RULES = {
    "profit_target_pct":         0.04,   # 4% take-profit
    "stop_loss_atr_multiplier":  1.5,    # Stop = Entry − (1.5 × ATR14)
    "max_hold_days":             10,     # Flag for review after 10 trading days
    # ── Partial exit + trailing stop (new) ─────────────────────────────────
    "partial_exit_pct":          0.03,   # Sell half at +3% for ETFs (shorter hold)
    "partial_exit_fraction":     0.50,   # Fraction of shares to sell
    "trailing_stop_trigger_pct": 0.02,   # Move stop to breakeven at +2% for ETFs
}

# ── MODE B: STOCK DELIVERY — EXIT RULES ──────────────────────────────────
# Wider targets + stops — delivery trades need room to develop.

STOCK_EXIT_RULES = {
    "profit_target_pct":         0.10,   # 10% take-profit (delivery trades need space)
    "stop_loss_atr_multiplier":  2.5,    # Wider stop — avoid noise shakeouts
    "max_hold_days":             20,     # Review after 20 trading days (~4 weeks)
    "review_hold_days":          15,     # Soft review flag at 15 days
    # ── Partial exit + trailing stop (new) ─────────────────────────────────
    "partial_exit_pct":          0.05,   # Sell half at +5% profit
    "partial_exit_fraction":     0.50,   # Fraction of shares to sell (50%)
    "trailing_stop_trigger_pct": 0.04,   # Move stop to breakeven at +4%
}

# ---------------------------------------------------------------------------
# VIX-BASED RISK FILTERS
# Reduces position sizes during high-fear regimes. Shared by both modes.
# ---------------------------------------------------------------------------

VIX_THRESHOLDS = {
    "normal":  15,   # VIX < 15  → full sizing (factor = 1.0)
    "caution": 20,   # VIX 15-20 → 70% sizing  (factor = 0.7)
    "danger":  25,   # VIX > 20  → 50% sizing  (factor = 0.5)
}

# ---------------------------------------------------------------------------
# NEWS RSS FEEDS
# ---------------------------------------------------------------------------

NEWS_FEEDS = [
    "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "https://economictimes.indiatimes.com/markets/rss.cms",
]

POSITIVE_KEYWORDS = [
    "breakout", "surge", "rally", "upgrade", "beat", "strong",
    "outperform", "growth", "record", "bullish", "gain", "rise",
    "profit", "buy", "momentum", "positive", "recovery", "boost",
    "jump", "soar", "high", "up", "climb",
]

NEGATIVE_KEYWORDS = [
    "fall", "crash", "downgrade", "miss", "weak", "bearish",
    "losses", "concerns", "selloff", "cut", "drop", "decline",
    "loss", "sell", "slowdown", "negative", "risk", "warning",
    "down", "slump", "plunge", "sink", "low",
]

# ---------------------------------------------------------------------------
# FILE PATHS  (relative to project root)
# ---------------------------------------------------------------------------

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR    = os.path.join(BASE_DIR, "data")
CACHE_DIR   = os.path.join(DATA_DIR, "cache")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# ── Shared caches (macro + news are mode-independent) ────────────────────
MACRO_CACHE = os.path.join(CACHE_DIR, "macro.json")
NEWS_CACHE  = os.path.join(CACHE_DIR, "news.json")

# ── ETF mode paths ────────────────────────────────────────────────────────
ETF_PRICES_CACHE   = os.path.join(CACHE_DIR, "prices_etf.json")
ETF_SIGNALS_CACHE  = os.path.join(CACHE_DIR, "signals_etf.json")
ETF_SCORES_CACHE   = os.path.join(CACHE_DIR, "scores_etf.json")
ETF_POSITIONS_FILE = os.path.join(DATA_DIR, "positions_etf.json")
ETF_HISTORY_FILE   = os.path.join(DATA_DIR, "history_etf.csv")
ETF_REPORT_FILE    = os.path.join(REPORTS_DIR, "etf_report.md")

# ── Stock delivery mode paths ─────────────────────────────────────────────
STOCK_PRICES_CACHE   = os.path.join(CACHE_DIR, "prices_stock.json")
STOCK_SIGNALS_CACHE  = os.path.join(CACHE_DIR, "signals_stock.json")
STOCK_SCORES_CACHE   = os.path.join(CACHE_DIR, "scores_stock.json")
STOCK_POSITIONS_FILE = os.path.join(DATA_DIR, "positions_stock.json")
STOCK_HISTORY_FILE   = os.path.join(DATA_DIR, "history_stock.csv")
STOCK_REPORT_FILE    = os.path.join(REPORTS_DIR, "stock_report.md")

# ── Intraday mode paths ───────────────────────────────────────────────────
INTRADAY_PRICES_CACHE   = os.path.join(CACHE_DIR, "prices_intraday.json")
INTRADAY_SIGNALS_CACHE  = os.path.join(CACHE_DIR, "signals_intraday.json")
INTRADAY_SCORES_CACHE   = os.path.join(CACHE_DIR, "scores_intraday.json")
INTRADAY_REPORT_FILE    = os.path.join(REPORTS_DIR, "intraday_report.md")

# ---------------------------------------------------------------------------
# MODE CONFIG HELPER
# Call get_mode_config(mode) in every pipeline script to get the right
# watchlist, file paths, and rule sets for that mode.
# ---------------------------------------------------------------------------

def get_mode_config(mode: str) -> dict:
    """
    Returns a unified config dict for the requested mode.

    Args:
        mode: "etf", "stock", or "intraday"

    Returns:
        dict with keys: watchlist, prices_cache, signals_cache, scores_cache,
                        report_file, position_sizing, entry_rules, exit_rules, weights
    """
    if mode == "stock":
        return {
            "mode":            "stock",
            "label":           "Stock Delivery",
            "watchlist":       STOCK_DELIVERY_WATCHLIST,
            "prices_cache":    STOCK_PRICES_CACHE,
            "signals_cache":   STOCK_SIGNALS_CACHE,
            "scores_cache":    STOCK_SCORES_CACHE,
            "positions_file":  STOCK_POSITIONS_FILE,
            "history_file":    STOCK_HISTORY_FILE,
            "report_file":     STOCK_REPORT_FILE,
            "position_sizing": STOCK_POSITION_SIZING,
            "entry_rules":     STOCK_ENTRY_RULES,
            "exit_rules":      STOCK_EXIT_RULES,
            "weights":         STOCK_WEIGHTS,
        }
    elif mode == "intraday":
        return {
            "mode":            "intraday",
            "label":           "Intraday (ORB)",
            "watchlist":       INTRADAY_WATCHLIST,
            "prices_cache":    INTRADAY_PRICES_CACHE,
            "signals_cache":   INTRADAY_SIGNALS_CACHE,
            "scores_cache":    INTRADAY_SCORES_CACHE,
            "report_file":     INTRADAY_REPORT_FILE,
            "position_sizing": INTRADAY_POSITION_SIZING,
            "entry_rules":     INTRADAY_ENTRY_RULES,
            "exit_rules":      INTRADAY_EXIT_RULES,
            "weights":         INTRADAY_WEIGHTS,
        }
    else:  # "etf" (default)
        return {
            "mode":            "etf",
            "label":           "ETF/MF Swing",
            "watchlist":       WATCHLIST,
            "prices_cache":    ETF_PRICES_CACHE,
            "signals_cache":   ETF_SIGNALS_CACHE,
            "scores_cache":    ETF_SCORES_CACHE,
            "positions_file":  ETF_POSITIONS_FILE,
            "history_file":    ETF_HISTORY_FILE,
            "report_file":     ETF_REPORT_FILE,
            "position_sizing": POSITION_SIZING,
            "entry_rules":     ENTRY_RULES,
            "exit_rules":      EXIT_RULES,
            "weights":         WEIGHTS,
        }
