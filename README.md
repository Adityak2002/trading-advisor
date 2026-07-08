# 📊 Personal Trading Advisory System

> **Personal use only. Not SEBI-registered advice. All trade decisions are manual.**

Automated dual-corpus trading signal engine that runs on **GitHub Actions** (zero cost).
- **ETF/MF Corpus (₹10,000)** → Daily report at 8:30 AM IST (oversold bounce strategy)
- **Stock Delivery Corpus (₹10,000)** → Report every 2 hours during market hours (momentum pullback strategy)

---

## 📁 Project Structure

```
trading-advisor/
├── scripts/
│   ├── config.py              ← All tunable settings (watchlists, weights, thresholds, mode helper)
│   ├── fetch_data.py          ← Step 1: Download OHLCV via yfinance  [--mode etf|stock]
│   ├── fetch_macro.py         ← Step 2: Macro data (VIX, S&P, Crude, USD/INR) + RSS news
│   ├── signals.py             ← Step 3: Technical indicators (RSI, EMA, ATR, BB, Vol-Z, EMA21 proximity)
│   ├── score.py               ← Step 4: Composite scoring — dual strategy per mode
│   ├── generate_report.py     ← Step 5: Write report.md + update state files  [--mode etf|stock]
│   └── update_position.py     ← Manual: Record a Groww trade  [--mode etf|stock]
├── reports/
│   ├── etf_report.md          ← ETF daily report (overwritten each morning)
│   └── stock_report.md        ← Stock delivery report (overwritten every 2 hours)
├── data/
│   ├── positions_etf.json     ← Open ETF swing positions
│   ├── positions_stock.json   ← Open stock delivery positions
│   ├── history_etf.csv        ← Closed ETF trades (append-only)
│   ├── history_stock.csv      ← Closed stock trades (append-only)
│   └── cache/                 ← Intermediate JSON files (gitignored, re-built each run)
├── .github/workflows/
│   ├── etf_daily.yml          ← Cron: 3:00 AM UTC (8:30 AM IST), Mon–Fri  + manual trigger
│   └── stock_intraday.yml     ← Cron: every 2h during market hours (4/6/8/10 UTC)  + manual trigger
├── requirements.txt
└── README.md
```

---

## 🚀 Deployment Guide (One-time setup)

### Step 1 — Initialise Git and Push

Open terminal in your `trading-advisor` folder:

```bash
git init
git add .
git commit -m "Initial commit — Trading Advisory System v2.0"
```

### Step 2 — Create GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Name it `trading-advisor`
3. Choose **Public** (recommended — lets you access raw URLs easily)
4. **Do NOT** add README or .gitignore (you already have them)
5. Click **Create repository**

### Step 3 — Push Your Code

```bash
git remote add origin https://github.com/YOUR_USERNAME/trading-advisor.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

### Step 4 — Enable Write Permissions for Actions

Go to: **Repo → Settings → Actions → General → Workflow permissions**  
Select: ✅ **Read and write permissions** → Save

### Step 5 — Test Both Workflows Manually

Go to: **Repo → Actions** tab

1. Click **ETF Daily Report** → **Run workflow** → **Run workflow**
2. Wait ~3 minutes, check **reports/etf_report.md** was committed

3. Click **Stock Delivery Report** → **Run workflow** → **Run workflow**
4. Wait ~3 minutes, check **reports/stock_report.md** was committed

✅ You're live! Both workflows will now run on their schedules automatically.

After each run, reports are available at your **Secret Gist** URLs (always showing the latest run):

```
# ETF Swing Report (Daily):
https://gist.githubusercontent.com/Adityak2002/131ba7a474fa2af554f0d3d4259dbdde/raw/etf_report.md

# Stock Delivery Report (2h):
https://gist.githubusercontent.com/Adityak2002/c367f5f984d23240566c5657609f922f/raw/stock_report.md
```

In Claude chat, say:
> "Fetch this URL and explain today's trading signals: https://gist.githubusercontent.com/..."

---

## 🌍 Instrument Universe

### Corpus A — ETF/MF Swing (₹10,000)

| Category | Instruments | Purpose |
|----------|------------|---------|
| Indian Sectoral ETFs | BANKBEES, PSUBNKBEES, PHARMABEES, ITETF, AUTOBEES, JUNIORBEES | Sector rotation |
| Commodity ETF | OILIETF | Crude oil exposure (max ₹3,000) |
| International ETFs | N100, MAFANG, HNGSNGBEES, NIFTYIETF | USD-linked global tech momentum |
| Swing Stocks | IRFC, RVNL, IREDA, NHPC, RECLTD, TATAPOWER, SUZLON, CANBK, BANKBARODA, UNIONBANK, ABFRL, HDFCAMC | High-beta sector swings |

### Corpus B — Stock Delivery (₹10,000)

| Category | Instruments | Purpose |
|----------|------------|---------|
| Large-Cap Anchors | ICICIBANK, HDFCBANK, RELIANCE | Stable trend rides, lower risk |
| Quality Mid-Caps | CDSL, POLYCAB, BAJFINANCE, TITAN, ANGELONE, PIDILITIND, KEI, HAVELLS | Growth + strong uptrends |

> **Verify tickers** at https://finance.yahoo.com/quote/TICKER.NS before first run.

---

## ⚙️ Dual Signal Engine

### Corpus A — ETF Swing: Mean-Reversion Strategy

**Indicators:** RSI(14), EMA(9/21/50), ATR(14), Bollinger Bands(20), Volume Z-score

**Entry (all 4 must be true):**

| # | Condition | Rationale |
|---|-----------|-|
| 1 | RSI(14) < 38 | Oversold territory |
| 2 | Price > EMA(50) | Broader uptrend intact |
| 3 | Volume Z-score ≥ 1.5 | Confirms the move |
| 4 | Composite score ≥ 40 | Overall setup strong |

**Exit:** Target +4% · Stop 1.5×ATR · Max hold 10 days

---

### Corpus B — Stock Delivery: Momentum Pullback Strategy

**Core idea:** Buy quality stocks dipping to EMA21 inside a confirmed uptrend

**Indicators:** RSI(14), EMA(9/21/50), ATR(14), Bollinger Bands, Volume Z-score, EMA21 Proximity

**Entry (all 5 must be true):**

| # | Condition | Rationale |
|---|-----------|-|
| 1 | RSI in 42–55 | Healthy pullback — not a falling knife |
| 2 | EMA21 > EMA50 | Medium-term uptrend intact |
| 3 | Price within ±4% of EMA21 | Price in the pullback zone |
| 4 | Volume Z-score ≤ 2.0 | Calm dip, not aggressive selling |
| 5 | Composite score ≥ 50 | Higher bar for delivery capital |

**Exit:** Target +10% · Stop 2.5×ATR · Max hold 20 days (~4 weeks)

---

## 💰 Position Sizing

### Corpus A — ETF Swing (₹10,000)

| Situation | Allocation |
|-----------|-----------|
| 1st position | ₹6,000 (60%) |
| 2nd position | ₹4,000 (40%) |
| Crude ETF cap | ₹3,000 max |

### Corpus B — Stock Delivery (₹10,000)

| Situation | Allocation |
|-----------|-----------|
| 1st position | ₹7,000 (70%) |
| 2nd position | ₹3,000 (30%) |
| Recommended idle reserve | ₹3,000 |

### VIX Adjustments (both corpora)

- VIX < 15 → 100% of calculated size
- VIX 15–20 → 70% of size
- VIX > 20 → 50% of size

---

## 📅 Schedule

| Workflow | Trigger | File Updated |
|----------|---------|-------------|
| ETF Daily Report | 8:30 AM IST, Mon–Fri | `reports/etf_report.md` |
| Stock Delivery Report | 9:30, 11:30, 13:30, 15:30 IST, Mon–Fri | `reports/stock_report.md` |
| Manual Trigger (both) | GitHub Actions → Run workflow | Same as above |

---

## 📱 Daily Workflow (5–10 minutes)

| Time | Action |
|------|--------|
| 8:30 AM | ETF workflow runs automatically |
| 9:15 AM | Check Claude with ETF report URL |
| 9:30 AM | First stock delivery scan runs |
| 11:30 AM | **Best entry time** — stock scan runs, opening volatility settled |
| After buying | Run `python scripts/update_position.py --mode etf` or `--mode stock` |

---

## 🛠️ Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# ── ETF pipeline ──────────────────────────────────────────────────────────
python scripts/fetch_data.py --mode etf
python scripts/fetch_macro.py
python scripts/signals.py --mode etf
python scripts/score.py --mode etf
python scripts/generate_report.py --mode etf

# ── Stock delivery pipeline ───────────────────────────────────────────────
python scripts/fetch_data.py --mode stock
python scripts/fetch_macro.py        # (shared — skip if already run today)
python scripts/signals.py --mode stock
python scripts/score.py --mode stock
python scripts/generate_report.py --mode stock

# ── Record a trade after buying on Groww ──────────────────────────────────
python scripts/update_position.py --mode etf     # for ETF trade
python scripts/update_position.py --mode stock   # for stock delivery trade
```

---

## ⚠️ Risk Disclosure

- This system provides analysis and signals only. All trade decisions are yours.
- Short-term trading carries real risk of capital loss.
- Stop-losses reduce but do not eliminate loss risk (gap-down opens can breach stops).
- **STCG tax: 20%** applies on equity gains held < 1 year. Factor into net return.
- ETF corpus max loss per trade: Target ≤ ₹400–500 (4–5% of corpus)
- Stock corpus max loss per trade: Target ≤ ₹500–700 (5–7% of corpus)
- Strategy performance is not guaranteed to repeat.

---

*Version 2.0 — July 2026 | Built for personal use by Aditya*  
*Dual corpus: ₹10k ETF swing + ₹10k Stock delivery | Total: ₹20,000*
