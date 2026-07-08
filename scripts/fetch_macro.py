# =============================================================================
# fetch_macro.py — Step 2: Fetch global macro data + RSS news sentiment
# Saves results to data/cache/macro.json and data/cache/news.json
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import yfinance as yf
import requests
import xml.etree.ElementTree as ET
import json
import logging
from datetime import datetime

from config import (
    MACRO_TICKERS, SECTOR_TICKERS, NEWS_FEEDS,
    POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS,
    WATCHLIST, STOCK_DELIVERY_WATCHLIST,
    MACRO_CACHE, NEWS_CACHE, CACHE_DIR, VIX_THRESHOLDS
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MACRO DATA
# ---------------------------------------------------------------------------

def fetch_macro_data() -> dict:
    """Download latest values for all macro indicators."""
    macro = {}

    for name, ticker in MACRO_TICKERS.items():
        try:
            # Use longer period for Nifty to compute 20-EMA trend gate
            period = "2mo" if name == "nifty" else "5d"
            df = yf.download(
                ticker, period=period, interval="1d",
                auto_adjust=True, progress=False, threads=False
            )
            if isinstance(df.columns, type(df.columns)) and hasattr(df.columns, "levels"):
                df.columns = df.columns.get_level_values(0)

            df = df.dropna()
            if len(df) >= 2:
                latest  = float(df["Close"].iloc[-1])
                prev    = float(df["Close"].iloc[-2])
                pct_chg = ((latest - prev) / prev) * 100

                entry = {
                    "ticker":     ticker,
                    "current":    round(latest, 4),
                    "prev_close": round(prev, 4),
                    "pct_change": round(pct_chg, 3),
                    "trend":      "up" if pct_chg >= 0 else "down",
                }

                # Nifty-specific: compute 20-EMA and 20-day return for trend gate
                if name == "nifty" and len(df) >= 22:
                    ema20 = float(df["Close"].ewm(span=20, adjust=False).mean().iloc[-1])
                    nifty_20d_ago = float(df["Close"].iloc[-21]) if len(df) >= 21 else latest
                    nifty_20d_return = ((latest - nifty_20d_ago) / nifty_20d_ago) * 100
                    entry["ema20"] = round(ema20, 4)
                    entry["above_ema20"] = latest > ema20
                    entry["return_20d"] = round(nifty_20d_return, 3)
                    logger.info(
                        f"  ⮞ Nifty 20-EMA: {ema20:.2f} | "
                        f"{'ABOVE ✅' if latest > ema20 else 'BELOW ❌'} | "
                        f"20d return: {nifty_20d_return:+.2f}%"
                    )

                macro[name] = entry
                logger.info(
                    f"  ✓ {name:<12} ({ticker}): "
                    f"{latest:.2f} ({pct_chg:+.2f}%)"
                )
            else:
                logger.warning(f"  ✗ {name}: insufficient data")
                macro[name] = None

        except Exception as e:
            logger.error(f"  ✗ {name} ({ticker}): {e}")
            macro[name] = None

    return macro


def compute_macro_signal(macro: dict) -> dict:
    """
    Convert macro snapshot into a scalar signal [-1.0, +1.0].
    Also returns the VIX sizing factor and human-readable factors list.
    """
    score = 0.0
    factors = []

    # ── India VIX (primary risk filter) ────────────────────────────────────
    vix_factor = 1.0
    if macro.get("india_vix"):
        vix = macro["india_vix"]["current"]
        if vix < VIX_THRESHOLDS["normal"]:
            score += 0.40
            vix_factor = 1.0
            factors.append(f"VIX {vix:.1f} — Low fear 🟢 (full sizing)")
        elif vix < VIX_THRESHOLDS["caution"]:
            score += 0.10
            vix_factor = 0.7
            factors.append(f"VIX {vix:.1f} — Moderate 🟡 (70% sizing)")
        elif vix < VIX_THRESHOLDS["danger"]:
            score -= 0.30
            vix_factor = 0.5
            factors.append(f"VIX {vix:.1f} — Elevated ⚠️ (50% sizing)")
        else:
            score -= 0.70
            vix_factor = 0.4
            factors.append(f"VIX {vix:.1f} — High fear ⛔ (40% sizing)")

    # ── S&P 500 overnight move (global sentiment) ───────────────────────────
    if macro.get("sp500"):
        chg = macro["sp500"]["pct_change"]
        if chg > 0.5:
            score += 0.25
            factors.append(f"S&P 500 {chg:+.2f}% — Positive overnight cues 📈")
        elif chg < -0.5:
            score -= 0.25
            factors.append(f"S&P 500 {chg:+.2f}% — Negative overnight cues 📉")
        else:
            factors.append(f"S&P 500 {chg:+.2f}% — Neutral")

    # ── NASDAQ (tech proxy, relevant for intl ETFs) ─────────────────────────
    if macro.get("nasdaq"):
        chg = macro["nasdaq"]["pct_change"]
        if chg > 0.8:
            score += 0.10
            factors.append(f"NASDAQ {chg:+.2f}% — Tech bullish (N100/MAFANG +ve)")
        elif chg < -0.8:
            score -= 0.10
            factors.append(f"NASDAQ {chg:+.2f}% — Tech bearish")

    # ── Nifty previous close direction ─────────────────────────────────────
    if macro.get("nifty"):
        chg = macro["nifty"]["pct_change"]
        if chg > 0.3:
            score += 0.15
            factors.append(f"Nifty {chg:+.2f}% — Domestic market bullish")
        elif chg < -0.3:
            score -= 0.15
            factors.append(f"Nifty {chg:+.2f}% — Domestic market bearish")

    # ── Crude Oil (relevant for OILIETF) ────────────────────────────────────
    if macro.get("crude_oil"):
        chg = macro["crude_oil"]["pct_change"]
        price = macro["crude_oil"]["current"]
        factors.append(
            f"WTI Crude ${price:.2f} ({chg:+.2f}%) — "
            + ("Bullish for OILIETF 📈" if chg > 1.5 else
               "Bearish for OILIETF 📉" if chg < -1.5 else "Neutral for OILIETF")
        )

    # ── USD/INR (relevant for international ETFs) ───────────────────────────
    if macro.get("usd_inr"):
        chg = macro["usd_inr"]["pct_change"]
        rate = macro["usd_inr"]["current"]
        factors.append(
            f"USD/INR {rate:.2f} ({chg:+.3f}%) — "
            + ("Dollar rising → intl ETFs gain in INR terms 📈" if chg > 0.2 else
               "Dollar weakening → intl ETFs headwind" if chg < -0.2 else "USD stable")
        )

    score = max(-1.0, min(1.0, score))

    if score > 0.3:
        summary = "🟢 Bullish — Good day for entries"
    elif score > 0.0:
        summary = "🟡 Mildly Bullish — Proceed with caution"
    elif score > -0.3:
        summary = "🟡 Mildly Bearish — Prefer staying light"
    else:
        summary = "🔴 Bearish — Avoid new entries; protect open positions"

    # Nifty trend gate flag
    nifty_above_ema20 = True  # default: don't block if data unavailable
    if macro.get("nifty") and "above_ema20" in macro["nifty"]:
        nifty_above_ema20 = macro["nifty"]["above_ema20"]

    return {
        "score":             round(score, 3),
        "vix_factor":        vix_factor,
        "summary":           summary,
        "factors":           factors,
        "nifty_above_ema20": nifty_above_ema20,
        "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------------------------------------------------------------------------
# NEWS SENTIMENT
# ---------------------------------------------------------------------------

def fetch_rss_headlines() -> list[str]:
    """Fetch headlines from configured RSS feeds."""
    headlines = []
    for url in NEWS_FEEDS:
        try:
            resp = requests.get(
                url, timeout=12,
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"}
            )
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                items = root.findall(".//item")
                for item in items[:20]:
                    el = item.find("title")
                    if el is not None and el.text:
                        headlines.append(el.text.strip())
                logger.info(f"  ✓ RSS {url.split('/')[2]}: {len(items)} headlines")
            else:
                logger.warning(f"  ✗ RSS {url}: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"  ✗ RSS {url}: {e}")
    return headlines


def score_headline(text: str) -> float:
    """Return sentiment score for one headline [-1, +1]."""
    t = text.lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in t)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in t)
    raw = pos - neg
    return max(-1.0, min(1.0, raw / 3.0))


def compute_news_sentiment(headlines: list[str]) -> dict:
    """
    Compute:
      - Per-ticker sentiment (mentions in headlines)
      - Overall market sentiment
    """
    # Combine tickers from both corpora for broader news coverage
    all_tickers = (
        [t for cats in WATCHLIST.values() for t in cats] +
        [t for cats in STOCK_DELIVERY_WATCHLIST.values() for t in cats]
    )
    ticker_sentiment = {}

    for ticker in all_tickers:
        base = ticker.replace(".NS", "").lower()
        # Match on first 6 chars to catch partial company name matches
        relevant = [h for h in headlines if base[:6] in h.lower()]

        pos = neg = 0
        for h in relevant:
            s = score_headline(h)
            if s > 0:
                pos += 1
            elif s < 0:
                neg += 1

        norm = max(-1.0, min(1.0, (pos - neg) / 3.0)) if relevant else 0.0
        ticker_sentiment[ticker] = {
            "score":     round(norm, 3),
            "pos_hits":  pos,
            "neg_hits":  neg,
            "mentions":  len(relevant),
            "headlines": relevant[:3],
        }

    # Overall market sentiment
    all_scores = [score_headline(h) for h in headlines]
    market_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

    return {
        "market_sentiment":  round(market_score, 3),
        "ticker_sentiment":  ticker_sentiment,
        "headlines_count":   len(headlines),
        "headlines_sample":  headlines[:8],
        "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------------------------------------------------------------------------
# SECTOR RELATIVE STRENGTH
# ---------------------------------------------------------------------------

def fetch_sector_data() -> dict:
    """
    Fetch sector indices (Bank Nifty, Nifty IT) with 2-month history.
    Compute 20-day return for each sector and for Nifty.
    Returns dict with sector_name -> {return_20d, relative_to_nifty}.
    """
    sector_data = {}

    # Get Nifty's 20-day return from macro cache if available
    nifty_20d_return = 0.0

    for name, ticker in SECTOR_TICKERS.items():
        try:
            df = yf.download(
                ticker, period="2mo", interval="1d",
                auto_adjust=True, progress=False, threads=False
            )
            if isinstance(df.columns, type(df.columns)) and hasattr(df.columns, "levels"):
                df.columns = df.columns.get_level_values(0)

            df = df.dropna()
            if len(df) >= 21:
                latest = float(df["Close"].iloc[-1])
                d20_ago = float(df["Close"].iloc[-21])
                ret_20d = ((latest - d20_ago) / d20_ago) * 100

                sector_data[name] = {
                    "ticker":     ticker,
                    "current":    round(latest, 4),
                    "return_20d": round(ret_20d, 3),
                }
                logger.info(
                    f"  ✓ Sector {name:<12} ({ticker}): "
                    f"{latest:.2f} | 20d return: {ret_20d:+.2f}%"
                )
            else:
                logger.warning(f"  ✗ Sector {name}: insufficient data ({len(df)} rows)")
                sector_data[name] = None
        except Exception as e:
            logger.error(f"  ✗ Sector {name} ({ticker}): {e}")
            sector_data[name] = None

    return sector_data


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    os.makedirs(CACHE_DIR, exist_ok=True)

    # ── Macro data ──────────────────────────────────────────────────────────
    logger.info("Fetching macro / global market data ...")
    macro = fetch_macro_data()
    signal = compute_macro_signal(macro)
    macro["_signal"] = signal

    # ── Sector indices (for relative strength gate) ────────────────────────
    logger.info("Fetching sector index data ...")
    sector_data = fetch_sector_data()

    # Compute relative strength vs Nifty for each sector
    nifty_20d = 0.0
    if macro.get("nifty") and "return_20d" in macro["nifty"]:
        nifty_20d = macro["nifty"]["return_20d"]

    for name, sdata in sector_data.items():
        if sdata:
            relative = round(sdata["return_20d"] - nifty_20d, 3)
            sdata["relative_to_nifty"] = relative
            emoji = "✅" if relative >= -3.0 else "❌"
            logger.info(
                f"  ⮞ {name}: {sdata['return_20d']:+.2f}% vs Nifty {nifty_20d:+.2f}% "
                f"→ relative {relative:+.2f}% {emoji}"
            )

    macro["_sector_data"] = sector_data

    with open(MACRO_CACHE, "w") as f:
        json.dump(macro, f, indent=2)
    logger.info(f"Macro + sector data saved → {MACRO_CACHE}")

    # ── News ────────────────────────────────────────────────────────────────
    logger.info("Fetching news headlines ...")
    headlines = fetch_rss_headlines()
    news = compute_news_sentiment(headlines)

    with open(NEWS_CACHE, "w") as f:
        json.dump(news, f, indent=2)
    logger.info(f"News data saved → {NEWS_CACHE}")

    # Summary
    print(f"\n{'='*55}")
    print(f"  MACRO SIGNAL  : {signal['summary']}")
    print(f"  VIX Factor    : {signal['vix_factor']} (sizing multiplier)")
    print(f"  Nifty > EMA20 : {'YES ✅' if signal.get('nifty_above_ema20', True) else 'NO ❌ (entries suppressed)'}")
    print(f"  Headlines     : {len(headlines)} fetched")
    print(f"  Market Sent   : {news['market_sentiment']:+.2f}")
    print(f"{'='*55}\n")
    for f_item in signal["factors"]:
        print(f"  • {f_item}")
    print()


if __name__ == "__main__":
    main()
