# Scope Baseline & Work Breakdown Structure
## NewTradingOS v14.0

**PMBOK Knowledge Area:** Scope Management  
**Process Group:** Planning  
**Document Version:** 2.0  
**Date:** 2026-05-31

---

## 1. Project Scope Statement

### 1.1 Product Scope Description

NewTradingOS v14.0 is a self-hosted Streamlit web application that provides:

1. **Market Scanning** — Multi-timeframe technical signal scoring across 130+ Vietnam Stock Exchange (HOSE / HNX) tickers, with parallel batch processing and session-state caching.
2. **Signal Scoring** — A 100-point composite score assembled from 7 weighted components (Trend, Momentum, RSI, Volume/Flow, Foreign Flow, Macro Regime, ADX Strength), calibrated for VN market structure.
3. **VN-Specific Indicators** — Chaikin Money Flow (gap-adjusted), SuperTrend (ATR-based dynamic support), and Ceiling/Floor Streak counter (unique to VN ±7% daily limit rule).
4. **ML Forecasting** — Ensemble of 6 models (LSTM, XGBoost, Random Forest, Prophet, ARIMA, Monte Carlo) with per-timeframe weighted voting.
5. **Backtesting** — Historical simulation with VN-realistic cost model (0.15% broker fee + 0.1% sell tax + 0.05% slippage, T+2 settlement).
6. **Portfolio Management** — Position lifecycle (open → T+2 pending → close), P&L calculation, stop/target tracking, persisted to local JSON.
7. **Audit Logging** — Append-only JSONL event log for all business actions (open/close positions, data loads, macro updates, scan runs) with in-app filtered display.
8. **Macro Dashboard** — World market prices (8 assets via Yahoo Finance), VN-Index breadth indicators, foreign flow sentiment, composite macro score.

### 1.2 Acceptance Criteria

- All 407 automated unit tests pass on `python -m pytest`
- Application launches without errors on `python -m streamlit run app.py`
- Scanner scores 60 tickers in ≤ 2 seconds (benchmark: 1.04s achieved)
- Stop/Target values correctly derived from ATR × timeframe multiplier
- Portfolio JSON persists between sessions
- Audit JSONL file grows monotonically (never truncated)

### 1.3 Project Exclusions

- Live order execution
- Real-time (intraday) data
- Cloud hosting / multi-user support
- Mobile UI
- Paid data feeds

---

## 2. Work Breakdown Structure (WBS)

```
1.0  NewTradingOS v14.0
│
├── 1.1  Data Layer
│   ├── 1.1.1  OHLCV Ingestion (DNSE primary, SSI fallback)
│   ├── 1.1.2  Batch Download (parallel ticker fetching, 6-second timeout)
│   ├── 1.1.3  World Market Data (Yahoo Finance, 8 symbols, parallel)
│   ├── 1.1.4  KBS Market Snapshot (breadth + foreign flow, session-only)
│   └── 1.1.5  Data Caching (5-minute TTL, session-state scan cache)
│
├── 1.2  Technical Indicators (core/indicators.py)
│   ├── 1.2.1  Trend — SMA(fast/slow), EMA(fast/slow), Golden Cross
│   ├── 1.2.2  Momentum — RSI, MACD(line/signal/histogram), ROC
│   ├── 1.2.3  Volatility — ATR, Bollinger Bands (upper/mid/lower/%B)
│   ├── 1.2.4  Trend Strength — ADX, Keltner Channels
│   ├── 1.2.5  Volume/Flow — Volume Ratio, OBV, VWAP, MFI
│   ├── 1.2.6  VN-Specific — Chaikin Money Flow, SuperTrend, Ceiling/Floor Streak
│   ├── 1.2.7  Manipulation Detection — Manip_score (volume spike + price move)
│   └── 1.2.8  compute_all() — unified computation for one DataFrame + config
│
├── 1.3  Signal Scoring Engine (core/scoring.py)
│   ├── 1.3.1  Component 1: Trend (25 pts) — SMA/EMA alignment + SuperTrend
│   ├── 1.3.2  Component 2: Momentum (20 pts) — MACD cross/histogram/ROC
│   ├── 1.3.3  Component 3: RSI (15 pts) — VN-tuned zone scoring
│   ├── 1.3.4  Component 4: Volume/Flow (20 pts) — Vol ratio + MFI + CMF + Streak
│   ├── 1.3.5  Component 5: Foreign Flow (5 pts) — net foreign buy (1M+ only)
│   ├── 1.3.6  Component 6: Macro Regime (10 pts) — macro_score / 10
│   ├── 1.3.7  Component 7: ADX Strength (5 pts) — trend quality gate
│   ├── 1.3.8  ATR Stop/Target — per-timeframe multiplier × ATR
│   ├── 1.3.9  Regime Filter — downgrade BUY → WATCH outside allowed regimes
│   ├── 1.3.10 Manipulation Flag — downgrade STRONG BUY → BUY + floor streak flag
│   └── 1.3.11 batch_score() — parallel ThreadPoolExecutor(6 workers)
│
├── 1.4  Macro & Regime (core/macro_data.py, core/regime.py)
│   ├── 1.4.1  World Market Fetch (parallel, 8 symbols)
│   ├── 1.4.2  VN-Index Breadth (advance/decline ratio)
│   ├── 1.4.3  Foreign Flow Aggregation
│   ├── 1.4.4  Composite Macro Score (0-10)
│   └── 1.4.5  Hidden Markov Model Regime Detection (bull/sideways/bear)
│
├── 1.5  ML Forecasting (ml/)
│   ├── 1.5.1  Feature Engineering (ml/features.py)
│   ├── 1.5.2  LSTM Model (fallback to Holt's if TF not installed)
│   ├── 1.5.3  XGBoost Regressor
│   ├── 1.5.4  Random Forest Regressor
│   ├── 1.5.5  Prophet Time-Series
│   ├── 1.5.6  ARIMA / SARIMAX
│   ├── 1.5.7  Monte Carlo Simulation
│   └── 1.5.8  Ensemble Weighted Voting (per-timeframe weights in config)
│
├── 1.6  Backtesting Engine (backtest/)
│   ├── 1.6.1  Signal-based entry/exit simulation
│   ├── 1.6.2  VN Cost Model (BUY_TOTAL = 0.20%, SELL_TOTAL = 0.30%)
│   ├── 1.6.3  T+2 Settlement Simulation
│   ├── 1.6.4  Performance Metrics (CAGR, Sharpe, Max Drawdown, Win Rate)
│   └── 1.6.5  Equity Curve Export
│
├── 1.7  Portfolio Tracker (portfolio/tracker.py)
│   ├── 1.7.1  Position Dataclass (ticker, timeframe, entry, stop, target, cost)
│   ├── 1.7.2  open_position() — lot-size calculation + audit log
│   ├── 1.7.3  close_position() — P&L calculation + audit log
│   ├── 1.7.4  T+2 Close Readiness Management
│   └── 1.7.5  JSON Persistence (data/portfolio.json)
│
├── 1.8  Audit System (core/audit.py)
│   ├── 1.8.1  log_event() — append-only JSONL writer
│   ├── 1.8.2  load_events() / filter_events() — query layer
│   └── 1.8.3  Action Constants (OPEN, CLOSE, LOAD, MACRO, SCAN)
│
├── 1.9  User Interface (ui/)
│   ├── 1.9.1  Tab 0: 🌐 Macro Pulse (ui/macro_tab.py)
│   ├── 1.9.2  Tabs 1-5: Scanners 1W/2W/1M/3M/5M (ui/scanner_tab.py)
│   ├── 1.9.3  Tab 6: 🧠 ML Forecast (ui/ml_tab.py)
│   ├── 1.9.4  Tab 7: 🧪 Backtest (ui/backtest_tab.py)
│   ├── 1.9.5  Tab 8: 💼 Portfolio (ui/portfolio_tab.py)
│   ├── 1.9.6  Tab 9: 📜 Audit Log (ui/audit_tab.py)
│   ├── 1.9.7  Tab 10: 📖 Guide (inline)
│   └── 1.9.8  Shared Components (ui/components.py — badges, colour tokens)
│
├── 1.10 Configuration (config.py)
│   ├── 1.10.1 Trading Cost Constants
│   ├── 1.10.2 API URL Constants
│   ├── 1.10.3 Ticker Universe (VN30, VN100, HOSE, HNX, MARKET_SCAN_LIST)
│   ├── 1.10.4 Sector Map (17 sectors, 150+ tickers)
│   ├── 1.10.5 Exchange Routing (TICKER_EXCHANGE)
│   └── 1.10.6 TIMEFRAME_CONFIG (per-timeframe indicator params + score config)
│
└── 1.11 Testing & Quality
    ├── 1.11.1 test_indicators.py (indicator correctness)
    ├── 1.11.2 test_scoring.py (score range, breakdown, regime filter)
    ├── 1.11.3 test_portfolio.py (open/close/P&L logic)
    ├── 1.11.4 test_backtest.py (simulation correctness)
    ├── 1.11.5 test_data_fetcher.py (API fetch + fallback)
    ├── 1.11.6 test_ensemble.py (ML model integration)
    └── 1.11.7 test_regime.py (HMM regime detection)
```

---

## 3. WBS Dictionary (Key Work Packages)

| WBS ID | Work Package | Owner | Inputs | Outputs | Acceptance Criteria |
|---|---|---|---|---|---|
| 1.2.8 | `compute_all()` | Core Dev | Raw OHLCV DataFrame + cfg dict | DataFrame with 21 indicator columns | All columns present; no all-NaN series |
| 1.3.11 | `batch_score()` | Core Dev | Dict of (ticker → DataFrame) + tf + regime | List of `SignalResult` | 60 tickers < 2s; score ∈ [0,100] |
| 1.5.8 | Ensemble voting | ML Dev | 6 model predictions + weights | Single price forecast + confidence | Forecast not NaN; weights sum to 1 |
| 1.7.3 | `close_position()` | Portfolio Dev | ticker, exit_price, reason | Updated Position + audit event | P&L = (exit − entry − fees) × shares |
| 1.8.1 | `log_event()` | Core Dev | action, detail dict | Appended line in audit.jsonl | File grows; no data loss on crash |
| 1.11.x | Full test suite | QA | All modules | 407 passing tests | Zero failures on `pytest` |

---

## 4. Scope Control

- **Formal change requests** must update this document and the Project Charter before implementation.
- **Scope creep indicators:** new tabs, new API integrations, or changes to the 100-point scoring scale all require scope change review.
- **Version gate:** any change that breaks existing 407 tests is blocked until tests are fixed or test suite updated.
