# NewTradingOS v14.0 — Installation & User Guide

Vietnam Multi-Timeframe Trading Platform  
*Powered by Claude Sonnet 4.6 | Captain Seventh*

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Installation](#2-installation)
3. [Launching the App](#3-launching-the-app)
4. [Architecture Overview](#4-architecture-overview)
5. [Tab-by-Tab User Guide](#5-tab-by-tab-user-guide)
   - [Macro Pulse](#51-macro-pulse)
   - [Scanners (1W / 2W / 1M / 3M / 5M)](#52-scanners)
   - [ML Forecast](#53-ml-forecast)
   - [Backtest](#54-backtest)
   - [Portfolio](#55-portfolio)
6. [Configuration Reference](#6-configuration-reference)
7. [Trading Cost Model](#7-trading-cost-model)
8. [Signal Scoring System](#8-signal-scoring-system)
9. [Running Tests](#9-running-tests)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python    | 3.10    | 3.13        |
| RAM       | 4 GB    | 8 GB        |
| Disk      | 500 MB  | 2 GB        |
| OS        | Windows 10 / macOS 12 / Ubuntu 22.04 | — |

**Internet access** is required for live price data (DNSE, SSI, CafeF APIs).

---

## 2. Installation

### 2.1 Clone / Download

Place the project folder at any path, e.g.:

```
D:\portfolio\vnstock\newTradingOS\Sonet4.6\
```

### 2.2 Create a Virtual Environment (recommended)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2.3 Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all core packages:

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `pandas`, `numpy` | Data processing |
| `plotly` | Interactive charts |
| `scikit-learn`, `xgboost` | ML models (RF, XGB) |
| `prophet` | Facebook Prophet forecasting |
| `statsmodels` | ARIMA / SARIMAX |
| `hmmlearn` | Hidden Markov Model (regime detection) |
| `scipy` | Statistics |
| `requests`, `lxml` | HTTP / HTML parsing |

### 2.4 Optional: Enable LSTM (TensorFlow)

LSTM is disabled by default (the app falls back to Holt's exponential smoothing). To enable:

1. Uncomment in `requirements.txt`:
   ```
   tensorflow>=2.15.0
   ```
2. Re-run `pip install -r requirements.txt`

TensorFlow requires ~2 GB of disk space and a compatible Python version.

### 2.5 Verify Installation

```bash
python -c "
import streamlit, pandas, numpy, plotly, sklearn, xgboost
import prophet, statsmodels, hmmlearn
print('All core dependencies OK')
"
```

---

## 3. Launching the App

```bash
cd D:\portfolio\vnstock\newTradingOS\Sonet4.6
streamlit run app.py
```

Streamlit will open your browser at `http://localhost:8501` automatically.

To specify a port:

```bash
streamlit run app.py --server.port 8502
```

To expose on your local network (for mobile access):

```bash
streamlit run app.py --server.address 0.0.0.0
```

---

## 4. Architecture Overview

```
Sonet4.6/
├── app.py                  ← Entry point, Streamlit tab router
├── config.py               ← All constants, universe, timeframe configs
│
├── core/
│   ├── data_fetcher.py     ← OHLCV download (DNSE → SSI → CafeF fallback)
│   ├── macro_data.py       ← World markets, foreign flow, market breadth
│   ├── indicators.py       ← All technical indicators
│   ├── regime.py           ← Market regime detection (HMM + rule-based)
│   └── scoring.py          ← Signal scoring engine
│
├── ml/
│   ├── features.py         ← Feature engineering for ML models
│   ├── lstm_model.py       ← LSTM (+ Holt fallback)
│   ├── classical_models.py ← RF, XGB, ARIMA, Prophet, Monte Carlo
│   └── ensemble.py         ← Ensemble forecast with adaptive weights
│
├── portfolio/
│   ├── sizing.py           ← Kelly criterion, position sizing, metrics
│   └── tracker.py          ← Portfolio state, open/close positions
│
├── backtest/
│   └── engine.py           ← Multi-timeframe backtesting engine
│
├── ui/
│   ├── components.py       ← Shared Streamlit components
│   ├── scanner_tab.py      ← Scanner UI (all 5 timeframes)
│   ├── macro_tab.py        ← Macro Pulse UI
│   ├── ml_tab.py           ← ML Forecast UI
│   ├── backtest_tab.py     ← Backtest UI
│   └── portfolio_tab.py    ← Portfolio tracker UI
│
├── tests/                  ← pytest suite (159 tests)
└── requirements.txt
```

### Data Flow

```
Internet APIs
     │
     ▼
data_fetcher  ──►  indicators  ──►  scoring  ──►  Scanner tabs
     │                │
     │                ▼
     │            regime.py  ──►  ML ensemble  ──►  ML Forecast tab
     │
     ▼
macro_data  ──►  Macro Pulse tab

scoring + sizing  ──►  backtest/engine  ──►  Backtest tab
portfolio/tracker  ──►  Portfolio tab
```

---

## 5. Tab-by-Tab User Guide

### 5.1 Macro Pulse

**What it shows:** A real-time snapshot of the macro environment that sets context for all trading decisions.

**Sections:**

| Section | Description |
|---------|-------------|
| World Markets | Gold, WTI Oil, DXY, S&P 500, VIX, CSI 300, Nikkei — price and % change |
| Foreign Flow | Net foreign buy/sell for the current session (VN market) |
| Market Breadth | Advance/decline ratio, stocks above SMA20 |
| Macro Score | Composite 0–100 score; drives regime bias and score adjustments |

**Macro Score interpretation:**

| Score | Meaning |
|-------|---------|
| 70–100 | Strong bull conditions — full position sizing |
| 50–69 | Neutral — standard sizing |
| 30–49 | Caution — reduce size, prefer 3M/5M holds |
| 0–29 | Risk-off — avoid new entries |

---

### 5.2 Scanners

Five timeframe scanners: **1W** (1 week), **2W** (2 weeks), **1M** (1 month), **3M** (3 months), **5M** (5 months).

**Workflow:**

1. Select tickers to scan (default watchlist or full market list)
2. Click **Run Scanner**
3. Results table shows all tickers above the minimum score threshold
4. Click any ticker row to see its full signal breakdown

**Scanner results columns:**

| Column | Description |
|--------|-------------|
| Ticker | Stock symbol |
| Score | Signal strength 0–100 |
| Action | BUY / WATCH / HOLD / AVOID |
| Price | Last close price (VND) |
| Stop | Recommended stop-loss price |
| Target | Recommended take-profit price |
| R/R | Risk-to-reward ratio |
| Regime | Current market regime (bull/sideways/bear) |

**Score → Action mapping:**

| Score | Action |
|-------|--------|
| ≥ 75 | BUY |
| 60–74 | WATCH |
| 45–59 | HOLD |
| < 45 | AVOID |

**Timeframe selection guide:**

| Timeframe | Hold Period | Best For |
|-----------|-------------|----------|
| 1W | ~5 sessions | Active swing traders |
| 2W | ~10 sessions | Standard swing |
| 1M | ~22 sessions | Position trading |
| 3M | ~66 sessions | Medium-term holds |
| 5M | ~110 sessions | Long-term positions |

Longer timeframes (3M, 5M) use a more lenient regime filter (accepts bear market entries), while shorter timeframes (1W, 2W) are filtered to bull/sideways only.

---

### 5.3 ML Forecast

**What it does:** Generates a multi-model price forecast for a single ticker with bull/base/bear scenarios.

**Models used:**

| Model | Weight (1M, typical) | Notes |
|-------|----------------------|-------|
| LSTM | 0.20 | Requires TensorFlow; falls back to Holt |
| XGBoost | 0.25 | Gradient boosting on engineered features |
| Random Forest | 0.20 | Ensemble of decision trees |
| Prophet | 0.15 | Facebook Prophet (trend + seasonality) |
| ARIMA | 0.10 | Classic time series model |
| Monte Carlo | 0.10 | Stochastic simulation |

Weights are automatically redistributed if a model fails or is unavailable.

**Inputs:**

- **Ticker** — VN stock code (e.g., `VCB`, `HPG`, `FPT`)
- **Timeframe** — determines forecast horizon and model weights
- **Epochs** — LSTM training epochs (only relevant if TensorFlow installed)

**Output:**

- Forecast chart with base / bull (+1σ) / bear (−1σ) price paths
- Current price and target price
- Upside potential %
- Individual model predictions table

---

### 5.4 Backtest

**What it does:** Simulates the trading strategy on historical data for one or all timeframes.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| Ticker | VNM | Stock to backtest |
| Timeframe | All | Run single or all 5 timeframes |
| Initial Capital | 100,000,000 VND | Starting capital |
| Min Score | Per-TF config | Minimum signal score to enter |

**Output tabs:**

- **Equity Curve** — portfolio value over time
- **Trades Table** — every trade with entry/exit dates, prices, PnL
- **Summary** — per-timeframe statistics

**Summary statistics:**

| Metric | Description |
|--------|-------------|
| CAGR % | Compound annual growth rate |
| Total Ret % | Total return over backtest period |
| Sharpe | Sharpe ratio (annualised) |
| Calmar | CAGR / Max Drawdown |
| Max DD % | Maximum drawdown |
| Win Rate % | % of winning trades |
| PF | Profit factor (gross profit / gross loss) |
| # Trades | Number of completed trades |
| Avg Win % | Average winning trade return |
| Avg Loss % | Average losing trade return |
| Kelly % | Kelly criterion fraction |

**Important implementation details:**

- **T+2 settlement** is enforced — positions cannot be sold until 2 sessions after entry
- **VN trading costs** are applied: buy 0.15% + 0.05% slippage, sell 0.15% + 0.1% tax + 0.05% slippage
- Indicator warmup bars are skipped — the equity curve starts after sufficient data exists for all indicators

---

### 5.5 Portfolio

**What it does:** Tracks live open positions, records closed trades, and shows portfolio metrics.

**Actions:**

| Action | Description |
|--------|-------------|
| Open Position | Enter a new trade with ticker, price, shares, stop, target |
| Close Position | Exit a position at a given price with an exit reason |
| View Positions | Current open positions with unrealised P&L |
| View Trades | Full trade history |
| Metrics | Portfolio-level Sharpe, Calmar, max drawdown |

**Position sizing helper:**

Enter your available capital and the system computes recommended position size using the Kelly criterion, capped by the timeframe's `position_pct` limit (e.g., 15% of capital for 1M timeframe, max 5 simultaneous positions).

**Portfolio file:** State is saved to `data/portfolio.json` automatically after every operation. The file is loaded on startup so positions persist across sessions.

---

## 6. Configuration Reference

All settings live in `config.py`. Key sections:

### Trading Costs

```python
BUY_FEE   = 0.0015   # 0.15% broker fee
SELL_FEE  = 0.0015
SELL_TAX  = 0.001    # 0.1% securities tax
SLIPPAGE  = 0.0005   # 0.05% slippage estimate
```

### Default Capital

```python
INITIAL_CAPITAL = 100_000_000   # 100M VND
LOT_SIZE        = 100           # minimum lot
```

### Timeframe Config Keys

Each timeframe in `TIMEFRAME_CONFIG` has:

```python
{
  "hold_sessions":  int,    # expected holding period
  "lookback_days":  int,    # historical data to fetch
  "sma_fast/slow":  int,    # SMA periods
  "ema_fast/slow":  int,    # EMA periods
  "rsi_period":     int,
  "bb_period":      int,    # Bollinger Band period
  "atr_period":     int,
  "macd_fast/slow/signal": int,
  "stop_atr_mult":  float,  # stop = entry - ATR × mult
  "target_rr":      float,  # target = entry + stop_distance × rr
  "min_score":      int,    # minimum score to generate BUY signal
  "position_pct":   float,  # max % of capital per position
  "max_positions":  int,    # max simultaneous open positions
  "regime_filter":  list,   # allowed regimes for entry
  "ml_weights":     dict,   # per-model forecast weights
}
```

### Customising the Universe

To add or remove tickers from the scanner:

```python
# In config.py
DEFAULT_WATCHLIST = ["VCB", "HPG", "FPT", ...]   # your watchlist
MARKET_SCAN_LIST  = [...]                          # full scan universe
```

---

## 7. Trading Cost Model

Total round-trip cost (buy + sell) per trade:

$$\text{Round-trip cost} = \text{BUY\_TOTAL} + \text{SELL\_TOTAL} = 0.20\% + 0.35\% = 0.55\%$$

Where:
- **BUY\_TOTAL** = buy fee (0.15%) + slippage (0.05%) = **0.20%**
- **SELL\_TOTAL** = sell fee (0.15%) + securities tax (0.10%) + slippage (0.05%) = **0.30%**

All backtests and PnL calculations account for this cost model. A trade must overcome 0.55% just to break even, which is why the minimum score thresholds are set conservatively.

---

## 8. Signal Scoring System

The score (0–100) is a weighted composite of:

| Component | Max Points | Indicators |
|-----------|-----------|------------|
| Trend | 25 | SMA golden/death cross, EMA alignment, ADX strength |
| Momentum | 20 | RSI zone, MACD signal, ROC |
| Volatility | 15 | Bollinger Band position, ATR regime |
| Volume | 15 | Volume ratio vs MA, OBV direction, MFI |
| Regime bonus/penalty | ±10 | Bull adds points, bear subtracts |
| Macro adjustment | ±5 | Macro score above/below neutral |
| Foreign flow | ±5 | Net foreign buy/sell direction |

**Manipulation detection:** If `manipulation_score ≥ 50` (abnormal volume spike pattern), a warning is shown and the raw score is capped. Avoid entering on manipulation signals.

---

## 9. Running Tests

```bash
cd D:\portfolio\vnstock\newTradingOS\Sonet4.6
python -m pytest tests/ -v
```

Expected: **159 tests, all passing** (~3 minutes due to ML model tests).

To run a specific module's tests:

```bash
python -m pytest tests/test_indicators.py -v
python -m pytest tests/test_backtest.py   -v
python -m pytest tests/test_ensemble.py  -v
```

To run with coverage:

```bash
python -m pytest tests/ --cov=core --cov=ml --cov=portfolio --cov=backtest --cov-report=term-missing
```

Test files:

| File | Tests | Covers |
|------|-------|--------|
| `test_backtest.py` | 23 | Backtest engine, trades, T+2, fees, summaries |
| `test_data_fetcher.py` | 17 | OHLCV download, normalization, parsing |
| `test_ensemble.py` | 17 | ML ensemble, forecast results, weight redistribution |
| `test_indicators.py` | 30 | All technical indicators |
| `test_portfolio.py` | 28 | Kelly, sizing, tracker, metrics |
| `test_regime.py` | 15 | Regime detection (HMM + rule-based) |
| `test_scoring.py` | 29 | Signal scoring, batch scanner |

---

## 10. Troubleshooting

### App won't start

**Error:** `ModuleNotFoundError: No module named 'prophet'`  
**Fix:** `pip install prophet` (may require `pystan` — see Prophet docs for platform-specific build steps)

**Error:** `ModuleNotFoundError: No module named 'hmmlearn'`  
**Fix:** `pip install hmmlearn`

### No data returned for a ticker

- Check the ticker code is correct (e.g., `VCB` not `vcb`)
- HNX and UPCOM tickers are mapped automatically via `TICKER_EXCHANGE` in `config.py`
- Some tickers may be delisted or temporarily unavailable; the app falls back across three data sources (DNSE → SSI → CafeF)

### ML Forecast is very slow

- The first run trains models from scratch; subsequent runs within the same session are faster
- Reduce the LSTM epoch count (default 50) to 10–20 for faster iteration
- If TensorFlow is not installed, LSTM is skipped and Holt's method runs instantly

### Backtest shows very few trades

- The minimum score threshold may be too high — lower `min_score` in `config.py` for the relevant timeframe
- Short data history may not provide enough warmup bars for indicators — increase `lookback_days`

### Portfolio file corrupted

Delete `data/portfolio.json` to reset. The portfolio will start fresh from `INITIAL_CAPITAL`.

### Streamlit cache issues

```bash
streamlit cache clear
```

Or delete the `.streamlit/` cache folder in the project directory.

---

*NewTradingOS v14.0 — Built for Vietnamese equity markets (HOSE, HNX, UPCOM)*  
*T+2 settlement | LOT_SIZE = 100 | Default capital: 100,000,000 VND*
