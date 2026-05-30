# Architecture & Technical Design
## NewTradingOS v14.0

**PMBOK Baseline:** Technical Baseline  
**Document Version:** 2.0  
**Date:** 2026-05-30

---

## 1. System Context

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SYSTEMS                            │
│                                                                     │
│  DNSE API          SSI API         CafeF HTML      Yahoo Finance    │
│  (primary OHLCV)   (fallback 1)    (fallback 2)    (world markets)  │
└──────────┬─────────────┬──────────────┬───────────────┬─────────────┘
           │             │              │               │
           └─────────────┴──────────────┘               │
                         │                              │
            ┌────────────▼────────────┐   ┌────────────▼─────────┐
            │   core/data_fetcher.py   │   │  core/macro_data.py  │
            │   (OHLCV ingestion)      │   │  (world mkts, VN     │
            │   - 6s timeout           │   │   breadth, foreign)  │
            │   - parallel batch       │   │  - 8 parallel workers │
            └────────────┬────────────┘   └────────────┬─────────┘
                         │                              │
            ┌────────────▼────────────────────────────▼─────────┐
            │                  core/indicators.py                │
            │     compute_all(df, cfg) → DataFrame w/ 21 cols    │
            └────────────────────────┬───────────────────────────┘
                                     │
            ┌────────────────────────▼───────────────────────────┐
            │                  core/scoring.py                    │
            │     score_ticker() → SignalResult                   │
            │     batch_score() → List[SignalResult]              │
            │     (6 workers, ThreadPoolExecutor)                 │
            └────────────┬───────────────────┬───────────────────┘
                         │                   │
             ┌───────────▼───────┐  ┌────────▼──────────────────┐
             │  core/regime.py   │  │  ml/ensemble.py            │
             │  (HMM; bull/side/ │  │  (6 models → weighted avg) │
             │   bear)           │  └────────────────────────────┘
             └───────────┬───────┘
                         │
┌────────────────────────▼────────────────────────────────────────────┐
│                      Streamlit UI  (app.py + ui/)                   │
│                                                                     │
│  Tab 0: 🌐 Macro     Tabs 1–5: Scanners     Tab 6: 🧠 ML Forecast  │
│  Tab 7: 🧪 Backtest  Tab 8: 💼 Portfolio    Tab 9: 📜 Audit Log    │
│  Tab 10: 📖 Guide                                                   │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
            ┌──────────────────────▼───────────────────┐
            │              Data Persistence             │
            │  data/portfolio.json   data/audit.jsonl  │
            └──────────────────────────────────────────┘
```

---

## 2. Component Design

### 2.1 `core/data_fetcher.py`

**Responsibility:** Fetch and normalise OHLCV data for any ticker.

**Key functions:**
| Function | Description |
|---|---|
| `fetch_ohlcv(ticker, timeframe)` | Try DNSE → SSI → CafeF; return `pd.DataFrame` or `None` |
| `_fetch_dnse(ticker, tf)` | GET `https://services.entrade.com.vn/chart-api/v2/ohlcs/stock` |
| `_fetch_ssi(ticker, tf)` | SSI API fallback |
| `_fetch_cafef(ticker)` | HTML scrape, last resort |
| `fetch_batch(tickers, tf)` | ThreadPoolExecutor(6) over `fetch_ohlcv` |

**Data contract (output columns):** `open, high, low, close, volume` — all float64, DatetimeIndex.

**Error handling:** Each fetch function catches all exceptions; returns `None` on failure. Caller must guard against `None`.

---

### 2.2 `core/indicators.py`

**Responsibility:** Stateless indicator library. Pure functions operating on pandas Series.

**Indicator catalogue:**

| Column | Formula | Lookback |
|---|---|---|
| `SMA_fast` | SMA(close, cfg["sma_fast"]) | per timeframe |
| `SMA_slow` | SMA(close, cfg["sma_slow"]) | per timeframe |
| `EMA_fast` | EMA(close, cfg["ema_fast"]) | per timeframe |
| `EMA_slow` | EMA(close, cfg["ema_slow"]) | per timeframe |
| `RSI` | Wilder RSI(close, cfg["rsi_period"]) | per timeframe |
| `MACD` | EMA(12) − EMA(26) | 26 bars |
| `MACD_signal` | EMA(MACD, 9) | 9 bars |
| `MACD_hist` | MACD − MACD_signal | — |
| `BB_upper/mid/lower` | Bollinger(close, 20, 2) | 20 bars |
| `BB_pctB` | (close − lower) / (upper − lower) | 20 bars |
| `ATR` | Average True Range(H, L, C, cfg["atr_period"]) | per timeframe |
| `ADX` | Average Directional Index(H, L, C, 14) | 14 bars |
| `OBV` | On-Balance Volume ∑ | cumulative |
| `Vol_MA` | SMA(volume, cfg["volume_ma"]) | per timeframe |
| `Vol_ratio` | volume / Vol_MA | — |
| `MFI` | Money Flow Index(H, L, C, V, 14) | 14 bars |
| `ROC` | Rate of Change(close, cfg["roc_period"]) | per timeframe |
| `Manip_score` | spike detection heuristic | — |
| `CMF` | Chaikin Money Flow(H, L, C, V, period) | per timeframe |
| `ST` | SuperTrend line | — |
| `ST_dir` | SuperTrend direction (+1 bull / −1 bear) | — |
| `Streak` | Ceiling/Floor streak counter | — |

**VN-specific functions (added 2026-05):**

```python
def chaikin_money_flow(high, low, close, volume, period=14) -> pd.Series:
    mfm = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    mf_vol = mfm * volume
    return mf_vol.rolling(period).sum() / volume.rolling(period).sum()

def supertrend(high, low, close, atr_period=10, multiplier=3.0) -> tuple[pd.Series, pd.Series]:
    # Returns (line, direction): direction +1 = bullish, -1 = bearish
    # Ratchets: upper_band never rises, lower_band never falls (trend-direction dependent)

def ceiling_floor_streak(close, limit_pct=0.07) -> pd.Series:
    # Threshold = limit_pct * 0.97 (3% tolerance for rounding)
    # +N = N consecutive ceiling days (trần)
    # -N = N consecutive floor days (sàn)
```

---

### 2.3 `core/scoring.py`

**Responsibility:** Translate computed indicators into an actionable signal.

**Scoring model (100-point composite):**

| Component | Max Pts | Key Signals | VN Notes |
|---|---|---|---|
| Trend | 25 | SMA/EMA alignment, momentum direction, SuperTrend direction | SuperTrend adds 4pts for confirmation |
| Momentum | 20 | MACD cross, histogram, ROC | Cross = 8pts, histogram positive = 6pts, ROC > 5% = 6pts |
| RSI | 15 | Zone scoring | 45-65 = 15pts (VN sweet spot); 65-75 = 10pts (momentum continuation) |
| Volume/Flow | 20 | Vol ratio, MFI, CMF, Streak | CMF > 0.05 = +3pts; consecutive ceiling ≥ 2 = +2pts; floor ≤ -2 = -3pts |
| Foreign Flow | 5 | Net foreign buy | 1M/3M/5M timeframes only |
| Macro Regime | 10 | Composite macro score | macro_score / 10 |
| ADX Strength | 5 | ADX trend quality gate | ADX > 25 = 5pts |

**Decision thresholds:**

| Score | Action |
|---|---|
| ≥ 80 | STRONG BUY |
| ≥ 65 | BUY |
| ≥ 50 | WATCH |
| ≥ 35 | NEUTRAL |
| < 35 | AVOID |

**ATR-based Stop / Target per timeframe:**

| Timeframe | stop_atr_mult | target_rr |
|---|---|---|
| 1W | 1.0× | 1.5 |
| 2W | 1.5× | 2.0 |
| 1M | 2.0× | 2.5 |
| 3M | 2.0× | 3.0 |
| 5M | 2.5× | 4.0 |

```
stop  = entry_price − (ATR × stop_atr_mult)
target = entry_price + (entry_price − stop) × target_rr
```

---

### 2.4 `core/macro_data.py`

**Responsibility:** Aggregate macro environment into a 0–10 score used as one scoring component.

**Data sources:**

| Symbol | Meaning |
|---|---|
| `^GSPC` | S&P 500 |
| `^N225` | Nikkei 225 |
| `^HSI` | Hang Seng Index |
| `000001.SS` | Shanghai Composite |
| `GC=F` | Gold Futures |
| `CL=F` | Crude Oil WTI |
| `DX-Y.NYB` | US Dollar Index |
| `^VIX` | CBOE Volatility Index |

**Fetch:** `ThreadPoolExecutor(max_workers=8)` — all 8 symbols fetched simultaneously.

**Scoring logic:**
- Each market contributes 0–1 pts based on recent performance direction
- VN-Index advance/decline ratio adds breadth signal
- Foreign net buy/sell modifies final score ±1
- Final `macro_score` ∈ [0, 10]

---

### 2.5 `ml/ensemble.py`

**Responsibility:** Generate a price forecast confidence interval for a given ticker + timeframe.

**Models and weights (configurable per timeframe):**

| Model | Weight (default) | Notes |
|---|---|---|
| LSTM | 0.25 | Falls back to Holt's Exponential Smoothing if TensorFlow absent |
| XGBoost | 0.20 | Trained on 60+ feature columns |
| Random Forest | 0.20 | — |
| Prophet | 0.15 | Additive seasonality model |
| ARIMA | 0.10 | SARIMAX(1,1,1)(0,1,0,5) |
| Monte Carlo | 0.10 | Geometric Brownian Motion, 1000 simulations |

**Output:** `{"forecast": float, "low": float, "high": float, "confidence": str}`

---

### 2.6 `core/audit.py`

**Responsibility:** Immutable event log for all business actions.

**File:** `data/audit.jsonl` — one JSON object per line, newline-delimited.

**Schema:**
```json
{
  "timestamp": "2026-05-30T14:32:11.421Z",
  "action": "OPEN",
  "ticker": "VNM",
  "timeframe": "1M",
  "detail": {"entry": 82500, "shares": 120, "stop": 79000, "target": 91000},
  "result": "ok"
}
```

**Action types:** `OPEN`, `CLOSE`, `LOAD`, `MACRO`, `SCAN`

---

### 2.7 `portfolio/tracker.py`

**Responsibility:** Manage position lifecycle; persist state.

**Position dataclass:**
```python
@dataclass
class Position:
    ticker:     str
    timeframe:  str
    entry:      float
    shares:     int
    stop:       float
    target:     float
    cost_basis: float      # entry × shares × (1 + BUY_FEE + SLIPPAGE)
    status:     str        # "open" | "t2_pending" | "closed"
    open_date:  str        # ISO 8601
    close_date: str | None
    exit_price: float | None
    pnl:        float | None
```

**Key calculations:**
```
lot_size   = floor((capital × risk_pct) / (entry − stop))
cost_basis = lot_size × entry × (1 + BUY_FEE + SLIPPAGE)
pnl        = lot_size × (exit − entry) − (lot_size × exit × (SELL_FEE + SELL_TAX))
```

**Trading cost constants (from `config.py`):**
```
BUY_FEE  = 0.0015   (0.15%)
SELL_FEE = 0.0015   (0.15%)
SELL_TAX = 0.001    (0.10%)
SLIPPAGE = 0.0005   (0.05%)
─────────────────────
Buy total:  0.20%
Sell total: 0.30%
Round trip: 0.50%
```

---

## 3. Data Flow — Scanning a Timeframe

```
User clicks "Scan 1M" button in scanner tab
        │
        ▼
Check session_state._scan_cache[key]
        │ miss
        ▼
fetch_batch(MARKET_SCAN_LIST, "1M")   ← parallel, 6 workers
        │
        ▼
For each ticker DataFrame:
  compute_all(df, TIMEFRAME_CONFIG["1M"])
        │
        ▼
batch_score(dfs, "1M", regime)        ← parallel, 6 workers
        │
        ▼
Sort by score DESC
        │
        ▼
Write _scan_cache[key] = results
        │
        ▼
Render table with badges + stop/target
```

---

## 4. Configuration Reference (`config.py`)

### 4.1 `TIMEFRAME_CONFIG`

| Key | 1W | 2W | 1M | 3M | 5M |
|---|---|---|---|---|---|
| `sma_fast` | 5 | 10 | 20 | 50 | 100 |
| `sma_slow` | 20 | 40 | 60 | 120 | 200 |
| `ema_fast` | 5 | 10 | 20 | 50 | 100 |
| `ema_slow` | 20 | 40 | 60 | 120 | 200 |
| `rsi_period` | 7 | 9 | 14 | 21 | 28 |
| `atr_period` | 7 | 10 | 14 | 21 | 28 |
| `volume_ma` | 5 | 10 | 20 | 50 | 60 |
| `roc_period` | 5 | 10 | 20 | 40 | 60 |
| `stop_atr_mult` | 1.0 | 1.5 | 2.0 | 2.0 | 2.5 |
| `target_rr` | 1.5 | 2.0 | 2.5 | 3.0 | 4.0 |

### 4.2 Ticker Universes

| List | Count | Description |
|---|---|---|
| `VN30_LIST` | 30 | Large-cap blue chips (HoSE) |
| `VN100_LIST` | 100 | Top 100 by market cap |
| `HOSE_LIST` | 110 | Broader HoSE selection |
| `HNX_LIST` | 20 | Hanoi Exchange tickers |
| `MARKET_SCAN_LIST` | 130 | Combined HOSE + HNX for default scan |

### 4.3 VN Market Constants

```python
INITIAL_CAPITAL   = 100_000_000  # VND
BUY_FEE           = 0.0015
SELL_FEE          = 0.0015
SELL_TAX          = 0.001
SLIPPAGE          = 0.0005
HOSE_LIMIT_PCT    = 0.07         # ±7% daily price ceiling/floor
HNX_LIMIT_PCT     = 0.10
UPCOM_LIMIT_PCT   = 0.15
SETTLEMENT_T_PLUS = 2.5          # T+2.5 (migrating to T+1)
TRADING_DAYS_YEAR = 240
```

---

## 5. Deployment

### 5.1 Requirements

```bash
Python >= 3.10
pip install -r requirements.txt
```

### 5.2 Launch

```bash
cd D:\portfolio\vnstock\newTradingOS\Sonet4.6
python -m streamlit run app.py
```

### 5.3 Key Files

```
app.py              ← entry point
config.py           ← all constants
requirements.txt    ← dependencies
pytest.ini          ← test runner config
data/               ← portfolio.json, audit.jsonl (auto-created)
core/               ← indicators, scoring, data fetcher, audit, macro, regime
ml/                 ← ensemble, features, individual models
backtest/           ← engine
portfolio/          ← tracker
ui/                 ← tab components
tests/              ← 159 automated tests
docs/               ← this documentation
```

### 5.4 Optional Dependencies

| Package | Feature | Fallback |
|---|---|---|
| `tensorflow` | LSTM model | Holt's Exponential Smoothing |
| `ta-lib` | TA-Lib indicators | Pure-Python pandas implementation |
