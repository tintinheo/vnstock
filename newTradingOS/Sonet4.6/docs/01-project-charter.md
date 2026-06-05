# Project Charter
## NewTradingOS v14.0 — Vietnam Multi-Timeframe Trading Platform

**PMBOK Knowledge Area:** Integration Management  
**Process Group:** Initiating  
**Document Version:** 2.0  
**Date:** 2026-05-31  
**Status:** Approved

---

## 1. Project Purpose and Justification

Vietnamese retail investors lack institutional-grade, locally-adapted analytical tooling. The overwhelming majority of trading platforms available to Vietnamese investors either:
- Rely on generic international indicators not calibrated for VN market constraints (±7% daily price limits, T+2 settlement, ~90% retail composition), or
- Lack integration of multi-timeframe signal scoring, ML forecasting, and portfolio tracking in a single, self-hosted interface.

**NewTradingOS** was initiated to close this gap by delivering a fully integrated, research-backed trading decision support platform purpose-built for the Vietnam Stock Exchange (HOSE / HNX / UPCoM).

---

## 2. Project Objectives

| # | Objective | Measurable Success Criterion |
|---|---|---|
| O1 | Provide multi-timeframe scanning (1W / 2W / 1M / 3M / 5M) for entire HOSE+HNX universe | All 5 timeframe scanners operational; scan 130+ tickers in < 5s |
| O2 | Implement VN-specific scoring model calibrated against 10-year market data | Score model incorporates CMF, SuperTrend, Ceiling/Floor streak; 407 automated tests pass |
| O3 | Integrate ML ensemble forecasting | 6-model ensemble (LSTM, XGBoost, RF, Prophet, ARIMA, Monte Carlo) operational per timeframe |
| O4 | Deliver in-app portfolio tracking with T+2 settlement awareness | Open/close positions, P&L, stop/target management; audit log persisted |
| O5 | Provide macro regime detection linked to scanner filtering | VN-Index breadth + foreign flow + world market correlations feeding regime labels |
| O6 | Maintain software quality through automated testing | ≥ 95% test pass rate; all core modules covered |

---

## 3. High-Level Scope

### 3.1 In Scope

- Streamlit-based single-page web application, self-hosted
- Market data ingestion from DNSE and SSI for OHLCV, plus Yahoo chart API and KBS snapshot API for macro context (no paid data subscriptions)
- Technical indicator computation (21 indicators including VN-specific additions)
- Multi-component signal scoring engine (7 components, 100-point scale)
- Five-timeframe parallel scanner with session-state caching
- ML ensemble forecaster (6 models per ticker per timeframe)
- Historical backtesting engine with VN-specific cost model
- Portfolio tracker (open/close/P&L) persisted to local JSON
- Audit log (append-only JSONL) for all business events
- Macro Pulse dashboard (world markets, VN breadth, foreign flow)
- Vietnamese and English UI labels

### 3.2 Out of Scope

- Automated order execution / broker API integration
- Real-time tick data (intraday data is not used)
- Mobile application
- Multi-user / cloud deployment (single-user, local deployment only)
- Paid market data feeds
- Options / derivatives analysis

---

## 4. Deliverables

| Deliverable | Description | Status |
|---|---|---|
| D1 | `app.py` — Main Streamlit application | Complete |
| D2 | `core/` — Indicators, scoring, data, macro, regime, audit modules | Complete |
| D3 | `ml/` — Ensemble forecasting engine | Complete |
| D4 | `backtest/` — Backtesting engine | Complete |
| D5 | `portfolio/tracker.py` — Portfolio state manager | Complete |
| D6 | `ui/` — All tab UI components (8 tabs + audit + guide) | Complete |
| D7 | `tests/` — Automated test suite (407 tests) | Complete |
| D8 | `docs/` — PMBOK project documentation | Complete |
| D9 | `GUIDE.md` — End-user installation and usage guide | Complete |

---

## 5. Key Milestones

| Milestone | Target Date | Status |
|---|---|---|
| M1 — Core scoring engine operational | 2025-Q2 | ✅ Done |
| M2 — All 5 scanner tabs live | 2025-Q3 | ✅ Done |
| M3 — ML ensemble integrated | 2025-Q4 | ✅ Done |
| M4 — Portfolio + backtest complete | 2026-Q1 | ✅ Done |
| M5 — Audit log + performance optimisation | 2026-Q2 | ✅ Done |
| M6 — VN market indicator research & recalibration | 2026-05-29 | ✅ Done |
| M7 — PMBOK documentation | 2026-05-30 | ✅ Done |

---

## 6. Budget and Resources

| Resource | Detail |
|---|---|
| Development | 1 developer (Captain Seventh) + Claude Sonnet 4.6 AI pair |
| Infrastructure | Local workstation; no cloud costs |
| Data | Free public APIs (DNSE, SSI, Yahoo chart API, KBS snapshot API) |
| Libraries | Open-source Python ecosystem (see `requirements.txt`) |
| Estimated compute cost | ~0 VND recurring (self-hosted) |

---

## 7. Constraints

| ID | Constraint |
|---|---|
| C1 | Data source limited to publicly available APIs; no proprietary data feeds |
| C2 | T+2 settlement rule (transitioning to T+1 per SSC roadmap) — affects portfolio close timing |
| C3 | HoSE ±7% daily price limit — affects stop-loss placement and indicator behaviour |
| C4 | Python GIL — parallelism implemented via ThreadPoolExecutor with numpy's C-level GIL release |
| C5 | Streamlit session model — all state must be managed via `st.session_state` |
| C6 | No real-time data — all analysis based on end-of-day OHLCV |

---

## 8. Assumptions

| ID | Assumption |
|---|---|
| A1 | User has Python 3.10+ installed and internet access |
| A2 | DNSE and SSI APIs remain publicly accessible without authentication |
| A3 | VN market continues to operate on ±7% HoSE daily limit (the primary scoring calibration basis) |
| A4 | Historical data sufficient for all configured lookback periods is available via APIs |
| A5 | The user understands that signals are decision-support only, not guaranteed recommendations |

---

## 9. Risks (Summary — detail in Risk Register)

| ID | Risk | Level |
|---|---|---|
| R1 | API rate limiting or URL changes breaking data ingestion | Medium |
| R2 | VN market microstructure changes (T+1 migration) invalidating ATR-based stop tuning | Low-Medium |
| R3 | ML model drift over extended time without retraining | Medium |
| R4 | Browser WebSocket timeout during long batch downloads | Low (mitigated) |

---

## 10. Project Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| Project Sponsor / Owner | Captain Seventh | *(electronic)* | 2026-05-30 |
| Technical Lead | Captain Seventh | *(electronic)* | 2026-05-30 |
| AI Development Partner | Claude Sonnet 4.6 | *(electronic)* | 2026-05-30 |
