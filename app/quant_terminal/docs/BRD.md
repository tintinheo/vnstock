# Business Requirements Document (BRD)

**Project:** Captain Seventh Quant Terminal  
**Document ID:** QT-BRD-001  
**Version:** 1.0  
**Status:** Approved  
**Date:** 2026-03-14  
**Prepared by:** TheCaptain7th (Product Owner / Requestor)  
**Reviewed by:** Academic Board — Quant Finance, Senior Trader, CS Director  
**Classification:** Internal / Confidential  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Context & Problem Statement](#2-business-context--problem-statement)
3. [Business Objectives](#3-business-objectives)
4. [Stakeholder Register](#4-stakeholder-register)
5. [Scope](#5-scope)
6. [Business Requirements](#6-business-requirements)
7. [Functional Requirements Summary](#7-functional-requirements-summary)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Assumptions & Constraints](#9-assumptions--constraints)
10. [Dependencies](#10-dependencies)
11. [Risk Register](#11-risk-register)
12. [Acceptance Criteria](#12-acceptance-criteria)
13. [Glossary](#13-glossary)

---

## 1. Executive Summary

The **Captain Seventh Quant Terminal** is a personal quantitative trading and portfolio management application for the Vietnamese equity market (HOSE/HNX/UPCOM). It consolidates live market data from SSI iBoard, technical analysis, scenario planning, risk management, and trade journaling into a single Streamlit-based dashboard — eliminating the need to switch between iboard.ssi.com.vn, Excel spreadsheets, and manual calculations.

The primary business driver is the owner's goal to achieve a **net annual return of ≥ 25%** from Vietnamese equities while following a disciplined, data-driven quantitative process, with a 12-month horizon to develop the skill set required to trade global markets professionally.

---

## 2. Business Context & Problem Statement

### 2.1 Background

The requestor is a Technology Lead with strong Python and AI/Data engineering skills but **zero prior finance or investment experience**. Trading decisions have historically been discretionary and unstructured:

- No systematic entry/exit criteria
- No risk quantification (VaR, drawdown limits)
- No portfolio performance tracking relative to benchmark
- Data scattered across broker platforms, news sites, and manual notes
- No historical performance record for learning and iteration

### 2.2 Problem Statement

> **Without a structured, data-driven system, the requestor cannot:**
> 1. Know objectively whether a trade has a positive expected value before executing it
> 2. Measure portfolio risk in real-time against predefined limits
> 3. Track which decisions produced alpha vs. which were lucky/unlucky
> 4. Build the systematic knowledge required to transition to global quantitative trading roles

### 2.3 Market Context (Vietnam Equities as Training Ground)

- Vietnam stock market (HOSE) has ~700+ listed companies, daily value ~15,000–25,000 billion VND
- T+2 settlement introduces unique liquidity constraints
- ±7% daily price band (HOSE) requires precise stop-loss discipline
- SSI Securities provides the most comprehensive public API for retail investors in Vietnam
- Target VN-Index benchmark return: ~12–15% annually; target alpha: ≥ 10–13%

---

## 3. Business Objectives

| ID | Objective | Metric | Target | Horizon |
|----|-----------|--------|--------|---------|
| BO-01 | Achieve net annual return | Portfolio return vs cost | ≥ 25% | 12 months |
| BO-02 | Outperform benchmark | Alpha vs VN-Index | ≥ +10% | 12 months |
| BO-03 | Control downside risk | Maximum portfolio drawdown | ≤ 12% | Ongoing |
| BO-04 | Systematic trade discipline | % trades with pre-defined plan | 100% | From day 1 |
| BO-05 | Build quantitative skills | Academic Board KPI rubric | 7/10 on Finance | 12 months |
| BO-06 | Prepare for global markets | Strategy transferability score | n/a | 24 months |

---

## 4. Stakeholder Register

| Stakeholder | Role | Interest | Influence |
|-------------|------|----------|-----------|
| TheCaptain7th | Product Owner / Trader | Primary user, funder | High |
| Academic Board | Advisor / Domain Expert | Education quality, risk controls | High |
| SSI Securities | Data Provider | API availability, data accuracy | Medium |
| GitHub Copilot | Technical Delivery | Implementation accuracy | Medium |

---

## 5. Scope

### 5.1 In Scope

- Portfolio loading, enrichment, and real-time P&L from SSI iBoard
- Technical analysis: RSI, MACD, Bollinger Bands, EMA, ATR, Volume signals
- Scenario planning: Bull / Base / Bear with EV, R:R, Kelly position sizing
- Risk dashboard: VaR, CVaR, correlation matrix, HHI concentration, drawdown
- Signal Digest: daily morning briefing table for all portfolio positions
- Heat Map: visual portfolio P&L treemap by weight and return
- Trade log: manual entry + JSON persistence + snapshot history
- Auto-refresh: configurable live price polling (30–300s intervals) via SSI iBoard
- LO order builder: step-by-step SSI iBoard order placement guide
- Market overview: VNINDEX chart, VN30, alpha vs. index, macro event calendar
- T+2 settlement awareness: tradeable quantity display

### 5.2 Out of Scope (v1.0)

- Automated order placement via SSI API (broker integration)
- Options / derivatives pricing
- WebSocket real-time streaming (polling used instead)
- Multi-account / multi-user support
- Mobile application
- Tax calculation and reporting
- International markets (US, crypto) — Phase 4 roadmap

---

## 6. Business Requirements

### BR-01 — Real-Time Portfolio Visibility
**Priority:** Critical  
The system shall display current market value, unrealised P&L (amount and %), and portfolio weight for every position, updated from SSI iBoard within the user-configurable refresh interval.

**Rationale:** Without real-time P&L, the trader cannot make timely decisions during market hours (09:15–11:30 and 13:00–14:45 HCM time).

---

### BR-02 — Objective Signal Generation
**Priority:** Critical  
The system shall compute a composite technical signal score (−100 to +100) for each position using at least 5 independent indicators, and generate an actionable recommendation (buy more / hold / reduce / exit) without human bias.

**Rationale:** Discretionary "gut feel" trading has zero accountability and cannot be back-tested or improved.

---

### BR-03 — Pre-Trade Scenario Analysis
**Priority:** High  
Before any trade, the system shall present Bull/Base/Bear scenarios with explicit probability inputs, Expected Value (EV), Risk:Reward ratio, and a structured order plan.

**Rationale:** Eliminates impulsive trades. Every entry must have a documented hypothesis.

---

### BR-04 — Portfolio Risk Quantification
**Priority:** High  
The system shall compute and display 95% Historical VaR, CVaR, portfolio concentration (HHI), and correlation matrix, updating at minimum daily.

**Rationale:** Aligns with professional risk management standards. Required for BO-03 (max drawdown ≤ 12%).

---

### BR-05 — Position Sizing Guidance
**Priority:** High  
The system shall compute Kelly Criterion optimal position sizing (full and half-Kelly), compare against current weight, and indicate whether to increase, reduce, or maintain each position.

**Rationale:** Optimal position sizing is the single most impactful factor in long-term compounding. Most retail investors size intuitively, which causes systematic ruin.

---

### BR-06 — Trade Journal & Performance Attribution
**Priority:** Medium  
The system shall persist all trades (manual entry) with date, symbol, side, quantity, price; calculate realized P&L; and compare portfolio return to VN-Index benchmark.

**Rationale:** Without a performance record, there is no feedback loop. All learning in quantitative trading is grounded in systematic measurement.

---

### BR-07 — Data Source Reliability
**Priority:** Critical  
The system shall use SSI iBoard as primary data source with automatic fallback to vnstock (VCI → TCBS → KBS) for historical OHLCV data; confirming SSI is reachable at startup.

**Rationale:** Single-source dependency is unacceptable for a live trading tool. Data gaps cause incorrect signals and potential trading losses.

---

### BR-08 — Daily Morning Briefing
**Priority:** Medium  
The system shall auto-generate a Signal Digest table displaying technical score, RSI, MACD histogram, and recommended action for every portfolio position — readable in under 60 seconds.

**Rationale:** Pre-market preparation is a core discipline of professional trading. The trader must know the plan before the bell rings.

---

## 7. Functional Requirements Summary

> Full technical specifications are in RELEASE_NOTES.md. This section maps business requirements to feature modules.

| BR | Feature Module | File | Status |
|----|---------------|------|--------|
| BR-01 | Live P&L, weight, heat map | `app.py` — Tab 1 | ✅ Released |
| BR-02 | Signal scoring, digest table | `modules/analysis.py`, `app.py` — Tab 1, 2 | ✅ Released |
| BR-03 | Scenario engine, order plan | `modules/scenarios.py`, `app.py` — Tab 2 | ✅ Released |
| BR-04 | VaR, CVaR, correlation matrix | `modules/analysis.py`, `app.py` — Tab 5 | ✅ Released |
| BR-05 | Kelly Criterion table | `app.py` — Tab 5 | ✅ Released |
| BR-06 | Trade log, snapshot, alpha | `modules/portfolio.py`, `app.py` — Tab 4 | ✅ Released |
| BR-07 | SSI iBoard + fallback waterfall | `modules/ssi_fetcher.py`, `modules/data_fetcher.py` | ✅ Released |
| BR-08 | Signal Digest | `app.py` — Tab 1 | ✅ Released |

---

## 8. Non-Functional Requirements

### NFR-01 — Performance
- Live quote refresh: ≤ 5 seconds per portfolio (up to 20 symbols)
- Page initial load: ≤ 10 seconds on standard home broadband
- Historical data fetch (252 days, single symbol): ≤ 8 seconds cold, ≤ 500ms cached

### NFR-02 — Reliability & Availability
- Data source waterfall: minimum 3 fallbacks (SSI → VCI → TCBS → mock)
- No single point of failure for price display
- Graceful degradation: app remains functional even if all external APIs are down (uses cached/mock data)

### NFR-03 — Security
- No credentials stored in source code (environment variables only)
- No user data transmitted to third parties beyond SSI iBoard public API
- OWASP Top 10 compliance: no injection vectors, no hardcoded secrets
- JSON cache files stored locally; no network exposure

### NFR-04 — Usability
- All features operational within 3 clicks from app launch
- Vietnamese language primary; technical indicators labeled bilingually
- Mobile-readable (Streamlit wide layout; treemap/charts scale to screen)

### NFR-05 — Maintainability
- Test coverage: 10+ smoke tests; all must pass before any release
- Modular architecture: data / analysis / portfolio / scenarios as separate modules
- All functions documented with docstrings

### NFR-06 — Compliance (SDLC)
- All features delivered per PMBOK process groups: Initiating → Planning → Executing → Monitoring → Closing
- Requirements traced from BRD → Release Notes → Acceptance Criteria
- No feature ships without passing `test_smoke.py`

---

## 9. Assumptions & Constraints

### Assumptions
- SSI iBoard public API remains available without authentication for OHLCV history
- User trades exclusively on HOSE (T+2, ±7% band) for v1.0
- Python 3.10+ and Streamlit 1.30+ are available in the deployment environment
- Portfolio size: 1–30 positions (performance not tested beyond this)

### Constraints
- **Budget:** Zero — all libraries are open-source; SSI API is public
- **Timeline:** v1.0 MVP delivered within same sprint as BRD
- **Platform:** Windows 10/11 + Python (Microsoft Store); Streamlit local only
- **Data delay:** SSI iBoard polling is not real-time WebSocket; ~15–30 second quote lag acceptable

---

## 10. Dependencies

| Dependency | Type | Version | Purpose |
|------------|------|---------|---------|
| `streamlit` | Framework | ≥ 1.30 | UI framework |
| `pandas` | Library | ≥ 2.0 | Data manipulation |
| `plotly` | Library | ≥ 5.18 | Interactive charts |
| `pandas_ta` | Library | ≥ 0.3.14b | Technical indicator computation |
| `scipy` | Library | ≥ 1.11 | `argrelextrema` for S/R detection |
| `vnstock` | Library | ≥ 3.4 | Fallback OHLCV data source |
| `requests` | Library | ≥ 2.31 | SSI iBoard HTTP calls |
| SSI iBoard API | External API | Public REST | Primary live data source |
| `openpyxl` | Library | ≥ 3.1 | Read SSI Excel portfolio exports |

---

## 11. Risk Register

| ID | Risk | Probability | Impact | Mitigation |
|----|------|-------------|--------|------------|
| R-01 | SSI API rate-limiting or shutdown | Medium | High | 3-tier fallback waterfall (VCI, TCBS, KBS) |
| R-02 | Overfitting technical signals to historical data | High | High | Walk-forward validation required before live trading |
| R-03 | Emotional override of system signals | High | High | Academic Board review requirement for position changes >5% |
| R-04 | VaR model underestimates tail risk (fat tails) | Medium | Medium | Use CVaR (Expected Shortfall) as supplement; monitor via Trade Log |
| R-05 | T+2 settlement miscalculation | Low | High | Automated settlement check in portfolio module; smoke-tested |
| R-06 | Data normalization error (raw VND vs thousands VND) | Low | High | Normalization in both SSI fetcher and vnstock fallback; smoke-tested |

---

## 12. Acceptance Criteria

### AC-01 — Portfolio Dashboard
- [ ] Loads SSI iBoard Excel export within 5 seconds
- [ ] Displays correct market value, P&L amount, P&L % for all positions
- [ ] Heat map renders with correct color (green = gain, red = loss)
- [ ] Signal Digest shows all portfolio symbols with RSI, score, action

### AC-02 — Live Data
- [ ] At least one price per position updates within 60 seconds of market open
- [ ] Source label shows "SSI-iboard" for successful live quotes
- [ ] Auto-refresh countdown visible and functional in sidebar

### AC-03 — Risk Dashboard
- [ ] VaR (95%) displayed per position and at portfolio level
- [ ] Correlation matrix renders for 2+ symbol portfolios
- [ ] Kelly table shows adjustment recommendation for all positions with sufficient history

### AC-04 — Scenario Analysis
- [ ] Bull target always > stop loss (validated by smoke test [06])
- [ ] R:R Bull displayed; must be > 0 for a valid trade
- [ ] All 4 order cards render with correct P&L estimate

### AC-05 — Smoke Tests
- [ ] All 10 smoke tests in `test_smoke.py` pass with `PYTHONIOENCODING=utf-8`
- [ ] No import errors on cold start

---

## 13. Glossary

| Term | Definition |
|------|------------|
| **VaR** | Value-at-Risk: maximum expected loss over a given period at a given confidence level |
| **CVaR** | Conditional VaR (Expected Shortfall): average loss in the worst-case tail beyond VaR |
| **Kelly Criterion** | Formula for optimal bet sizing: f* = (bp – q) / b, where b = payoff ratio, p = win probability |
| **HHI** | Herfindahl-Hirschman Index: sum of squared weights; measures portfolio concentration |
| **MACD** | Moving Average Convergence/Divergence: momentum indicator |
| **R:R** | Risk-to-Reward ratio: potential gain ÷ potential loss |
| **EV** | Expected Value: probability-weighted average outcome across scenarios |
| **T+2** | Settlement: shares transfer 2 business days after trade date; cannot sell until settled |
| **ATR** | Average True Range: volatility measure used for stop-loss sizing |
| **Alpha** | Portfolio return minus benchmark (VN-Index) return |
| **HOSE** | Ho Chi Minh Stock Exchange — primary VN exchange |
| **SSI** | Saigon Securities Incorporation — broker and primary data provider |
| **OHLCV** | Open, High, Low, Close, Volume — standard price data format |

---

*Document prepared under BABOK v3 standards for Business Analysis.*  
*Next review: 2026-06-14 (Q2 review) or on significant scope change.*
