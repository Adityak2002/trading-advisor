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

    # ── Large-Cap Anchors (lower beta, high liquidity) ───────────────────────
    # Used as stabilisers — reliable trends, less headline risk.
    "large_caps": [
        "ICICIBANK.NS",       # ICICI Bank — best-in-class private bank
        "HDFCBANK.NS",        # HDFC Bank — consistent compounder
        "RELIANCE.NS",        # Reliance Industries — diversified behemoth
    ],

    # ── Quality Mid-Caps (growth + liquid) ──────────────────────────────────
    # Strong business moats + part of infra/digital/consumption cycle.
    "quality_midcaps": [
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
}

# ── MODE B: STOCK DELIVERY — POSITION SIZING ─────────────────────────────
# Keep ₹3,000 idle reserve — delivery trades need room for drawdown.

STOCK_POSITION_SIZING = {
    "total_capital":                10000,  # ₹ second corpus
    "position_1_pct":               0.70,   # Primary position = 70% (₹7,000)
    "position_2_pct":               0.30,   # Secondary position = 30% (₹3,000)
    "idle_reserve":                 3000,   # Psychological buffer — don't deploy all
    "max_positions":                2,      # Max concurrent delivery positions
}

# ---------------------------------------------------------------------------
# ── MODE A: ETF SWING — EXIT RULES ──────────────────────────────────────
# ---------------------------------------------------------------------------

EXIT_RULES = {
    "profit_target_pct":         0.04,   # 4% take-profit
    "stop_loss_atr_multiplier":  1.5,    # Stop = Entry − (1.5 × ATR14)
    "max_hold_days":             10,     # Flag for review after 10 trading days
}

# ── MODE B: STOCK DELIVERY — EXIT RULES ──────────────────────────────────
# Wider targets + stops — delivery trades need room to develop.

STOCK_EXIT_RULES = {
    "profit_target_pct":         0.10,   # 10% take-profit (delivery trades need space)
    "stop_loss_atr_multiplier":  2.5,    # Wider stop — avoid noise shakeouts
    "max_hold_days":             20,     # Review after 20 trading days (~4 weeks)
    "review_hold_days":          15,     # Soft review flag at 15 days
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

# ---------------------------------------------------------------------------
# MODE CONFIG HELPER
# Call get_mode_config(mode) in every pipeline script to get the right
# watchlist, file paths, and rule sets for that mode.
# ---------------------------------------------------------------------------

def get_mode_config(mode: str) -> dict:
    """
    Returns a unified config dict for the requested mode.

    Args:
        mode: "etf" or "stock"

    Returns:
        dict with keys: watchlist, prices_cache, signals_cache, scores_cache,
                        positions_file, history_file, report_file,
                        position_sizing, entry_rules, exit_rules, weights
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
