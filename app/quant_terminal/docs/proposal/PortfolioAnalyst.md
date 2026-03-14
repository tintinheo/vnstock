*Product Proposal & Technical Specification*

Vietnam Equity Markets · Real-Time Portfolio Intelligence

| **Version** | 1.0 — Initial Release |
| --- | --- |
| **Date** | March 2026 |
| **Market** | HOSE · HNX · UPCOM (Vietnam) |
| **Data Source** | SSI iBoard API (Real-Time) |
| **Target Return** | **25% Net Annual Return** |

# 1. Executive Summary

Captain Seventh Quant Terminal is a local-first, real-time portfolio intelligence application designed for the Vietnam equity markets (HOSE/HNX/UPCOM). Built on a Python/Streamlit stack with SSI iBoard API integration, the terminal replicates and automates the advisory workflow of a quantitative research council — delivering institutional-grade portfolio analysis to individual traders at zero ongoing cost.

**Core Value Proposition**

Real-time portfolio P&L with SSI live price feeds — no manual Excel refresh

Per-stock scenario analysis (Bull / Base / Bear) with probability weighting

Automated trade recommendations: entry price, exit targets, stop-loss levels

LO/ATC order planning with slippage estimates and timing guidance

Technical signal aggregation: RSI, MACD, Bollinger, EMA across multiple timeframes

Market context overlay: VNINDEX trend, sector rotation, foreign flow

---

The application stores all portfolio data locally in a designated folder, supporting full data sovereignty. It requires no cloud subscription, no recurring API fees beyond the SSI brokerage account the user already holds, and runs entirely on a standard developer laptop.

# 2. Problem Statement

## 2.1 The Gap Between Data and Decision

Vietnam retail investors with technical backgrounds face a critical asymmetry: they have access to raw market data through brokerage platforms, but lack the analytical layer to convert data into structured, actionable decisions. The typical workflow today involves:

- Manual export of portfolio data from SSI iBoard as Excel files
- Ad-hoc price lookups on CafeF or Vietstock — no synthesis
- Unstructured decision-making with no scenario framework
- No systematic stop-loss or position sizing discipline
- No backtestable trade log or performance attribution

## 2.2 What Is Missing

| **Capability** | **Current State** | **Required State** |
| --- | --- | --- |
| Real-time P&L | Manual Excel refresh | Live SSI price feed |
| Scenario analysis | Mental model only | Structured 3-scenario framework with probabilities |
| Trade planning | Intuition-based | Quantitative entry/exit/stop with R:R ratio |
| Technical signals | Manual chart reading | Automated multi-indicator scoring |
| Risk management | None systematic | Kelly sizing + drawdown guardrails |
| Performance tracking | None | Sharpe, Alpha vs VNINDEX, trade log |

# 3. Solution Architecture

## 3.1 System Overview

The application follows a modular, layered architecture. Each layer is independently replaceable, allowing the data source to be swapped (e.g., from SSI to TCBS) or the UI to be upgraded without touching the core analysis engine.

**Architecture Layers**

Layer 1 — Data Ingestion: SSI iBoard API (REST + WebSocket) via vnstock/ssi-fcdata

Layer 2 — Portfolio Store: Local folder (JSON + Excel), versioned by date

Layer 3 — Analysis Engine: Technical indicators (ta-lib), scenario generator, risk calculator

Layer 4 — Recommendation Engine: Rule-based + statistical signal aggregation

Layer 5 — Presentation: Streamlit UI with Plotly charts and real-time refresh

---

## 3.2 Data Flow

| **Source** | **Data Type** | **Latency** | **Library** |
| --- | --- | --- | --- |
| SSI iBoard API | Real-time quotes (OHLCV, volume, foreign flow) | < 3 seconds | ssi-fcdata / vnstock |
| SSI iBoard API | Market depth (bid/ask 3 levels) | Real-time | ssi-fcdata WebSocket |
| SSI iBoard API | Index data (VNINDEX, VN30, HNX30) | < 5 seconds | vnstock |
| Local Excel/JSON | Portfolio positions, cost basis, trade log | Instant (local) | openpyxl / pandas |
| Yahoo Finance (backup) | Historical OHLCV for backtesting | End-of-day | yfinance |

# 4. Feature Specifications

## 4.1 Module 1 — Portfolio Dashboard

The entry point of the application. Loads the portfolio from a local folder and enriches each position with real-time market data from SSI.

- Auto-detect SSI iBoard Excel exports in the configured portfolio folder
- Display full position table: symbol, cost basis, market price, P&L (VND + %), weight (%)
- Color-coded risk tier per position: Low / Medium / High / Critical
- One-click drill-down to per-stock deep analysis
- Portfolio-level metrics: Total value, Net P&L, Sharpe (trailing 30d), Beta vs VNINDEX
- Export refreshed portfolio snapshot as Excel with current prices

## 4.2 Module 2 — Stock Analysis Engine

For each stock in the portfolio, the engine runs a full technical and fundamental snapshot.

**Technical Signals**

- RSI (14): Overbought/oversold with divergence detection
- MACD (12,26,9): Trend direction, signal crossover, histogram momentum
- Bollinger Bands (20,2): Squeeze detection, breakout signals
- EMA 20/50/200: Trend structure, golden/death cross
- Volume profile: Relative volume vs 20-day average
- Beta (60-day rolling vs VNINDEX)

**Fundamental Snapshot**

- P/E, P/B, EV/EBITDA sourced from SSI financial data
- Analyst consensus: target price, rating distribution
- Debt/equity, ROE, ROIC for risk scoring
- Upcoming catalyst calendar: earnings dates, AGM, dividend ex-date

## 4.3 Module 3 — Scenario Planner

The core advisory module. For each stock, the engine generates three structured scenarios with explicit triggers, price targets, and probability weights.

| **Scenario** | **Default Probability** | **Key Inputs** | **Output** |
| --- | --- | --- | --- |
| Bull | 30% | Positive catalyst, trend continuation, sector momentum | Target price, hold strategy |
| Base | 45% | Range-bound market, mixed signals, neutral macro | Partial exit levels, monitoring triggers |
| Bear | 25% | Technical breakdown, adverse macro, sector rotation out | Stop-loss levels, full exit protocol |

Probabilities are user-adjustable. The engine computes expected value of holding vs. exiting and recommends the dominant action.

## 4.4 Module 4 — Trade Planner

Converts scenario analysis into executable order instructions, with full awareness of HOSE trading rules.

- Order type selection: LO (Limit Order) vs. ATC vs. ATO with rationale
- Price tick validation: enforces 100 VND step on HOSE
- Session timing: ATO (8:30-9:00), Continuous (9:00-11:30 / 13:00-14:30), ATC (14:30-15:00)
- Slippage estimate based on average bid-ask spread and daily volume
- T+2 settlement tracker: which positions are currently tradeable
- Kelly Criterion position sizing: optimal allocation given edge and bankroll
- Risk-per-trade calculator: max 2% portfolio rule enforcement

## 4.5 Module 5 — Market Overview

Macro context that frames all individual stock decisions.

- VNINDEX and VN30 live chart with EMA overlays
- Foreign investor flow: net buy/sell by session and rolling 5-day
- Sector heatmap: relative performance vs VNINDEX
- Market breadth: advance/decline ratio, new highs/lows
- Macro alerts panel: configurable watchlist (oil price, USD/VND, Fed rate)

## 4.6 Module 6 — Trade Log & Performance

Tracks every completed trade and computes portfolio-level statistics.

- Automatic trade detection from SSI portfolio snapshots (delta comparison)
- Manual trade entry for corrections
- Performance metrics: total return, CAGR, Sharpe ratio, Sortino ratio, max drawdown
- Alpha vs VNINDEX: excess return attribution
- Win rate, average R:R, largest winner/loser
- Monthly P&L calendar view

# 5. Technical Stack

| **Layer** | **Technology** | **Version** | **Purpose** |
| --- | --- | --- | --- |
| Frontend UI | Streamlit | >=1.32 | Web-based local dashboard |
| Data Visualization | Plotly | >=5.18 | Interactive OHLCV, portfolio charts |
| Market Data | vnstock | >=0.3.x | SSI data source integration |
| Real-Time Data | ssi-fcdata | >=1.0 | WebSocket live quotes |
| Technical Analysis | pandas-ta | >=0.3.14b | RSI, MACD, BB, EMA, volume |
| Data Processing | pandas / numpy | >=2.0 | Portfolio analytics, scenario math |
| Excel I/O | openpyxl | >=3.1 | SSI portfolio file parsing and export |
| Persistence | JSON + Excel | — | Local portfolio store (no database needed) |
| HTTP Client | requests | >=2.31 | SSI REST API calls |
| Scheduling | APScheduler | >=3.10 | Auto-refresh price feeds every 30s |

**System Requirements**

Python 3.10+  ·  4GB RAM minimum (8GB recommended for full technical analysis)

Operating System: macOS 12+ / Windows 10+ / Ubuntu 20.04+

Network: Stable internet connection for SSI API (standard broadband sufficient)

SSI Account: Active iBoard account with API access enabled

Storage: <500MB for app + portfolio data (grows with trade log history)

---

# 6. Implementation Roadmap

| **Phase** | **Duration** | **Deliverables** | **Target** |
| --- | --- | --- | --- |
| Phase 0 — Foundation | Week 1–2 | App skeleton, SSI auth, portfolio loader, live price refresh | Working dashboard with real prices |
| Phase 1 — Analysis Core | Week 3–4 | Technical indicators, scenario engine, P&L analytics | Full stock analysis module |
| Phase 2 — Trade Planner | Week 5–6 | Order builder, Kelly sizing, stop-loss manager, T+2 tracker | Executable trade instructions |
| Phase 3 — Market Context | Week 7–8 | VNINDEX chart, sector heatmap, foreign flow, macro panel | Full market overview |
| Phase 4 — Performance | Week 9–10 | Trade log, Sharpe/Sortino, alpha attribution, monthly P&L | Complete performance tracking |
| Phase 5 — Hardening | Week 11–12 | Error handling, offline mode, config UI, documentation | Production-ready local app |

# 7. Risk Assessment

| **Risk** | **Likelihood** | **Impact** | **Mitigation** |
| --- | --- | --- | --- |
| SSI API rate limiting | Medium | High | Cache aggressively; exponential backoff; fallback to vnstock |
| SSI API schema changes | Low | High | Strict version pinning; integration tests on market open |
| Data quality (stale/incorrect prices) | Low | Critical | Cross-validate with Vietstock; flag anomalies >5% vs prior close |
| Market session edge cases | Medium | Medium | Hardcode HOSE holiday calendar; handle ATO/ATC separately |
| T+2 calculation errors | Low | High | Unit-tested settlement calculator; warn before trade |
| Regulatory changes (circuit breakers, ±7%) | Very Low | Medium | Configurable band parameters; auto-refresh from SSI on market open |

# 8. Success Metrics

The terminal is considered production-ready when all of the following criteria are met:

- Portfolio refreshes with live SSI prices within 5 seconds of market data update
- Scenario analysis generated for any HOSE/HNX stock in under 3 seconds
- Trade plan output matches manual calculation to within 1 tick (100 VND)
- Technical signals match TradingView readings within acceptable indicator variance
- Zero data loss on portfolio save/load cycle across 3 months of daily use
- App runs stable for 7-hour trading session without memory leak or crash

**Investment Target Alignment**

Primary KPI: Net portfolio return >= 25% per annum on live capital

The terminal is an instrument, not a guarantee. Edge comes from discipline in using it.

Track Sharpe ratio monthly. Target Sharpe > 1.5 after 6 months live trading.

The system earns its keep if it prevents even one -10% drawdown per year.

---

*Captain Seventh Quant Terminal  ·  Confidential  ·  March 2026*