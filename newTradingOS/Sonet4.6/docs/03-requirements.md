# Requirements Traceability Matrix (RTM)
## NewTradingOS v14.0

**PMBOK Knowledge Area:** Scope Management  
**Process Group:** Planning  
**Document Version:** 2.0  
**Date:** 2026-05-30

---

## 1. Functional Requirements

| ID | Requirement | Priority | WBS | Module | Test Case |
|---|---|---|---|---|---|
| FR-001 | System shall fetch OHLCV daily data for any HOSE/HNX ticker from DNSE API with automatic SSI fallback | Must | 1.1.1 | `core/data_fetcher.py` | `test_data_fetcher::test_fetch_ohlcv_dnse` |
| FR-002 | System shall use CafeF HTML as tertiary data fallback when DNSE and SSI both fail | Must | 1.1.1 | `core/data_fetcher.py` | `test_data_fetcher::test_fetch_fallback_chain` |
| FR-003 | System shall fetch data for a batch of tickers in parallel using ThreadPoolExecutor | Must | 1.1.2 | `core/data_fetcher.py` | `test_data_fetcher::test_batch_fetch` |
| FR-004 | System shall compute all 21 technical indicator columns via `compute_all()` | Must | 1.2.8 | `core/indicators.py` | `test_indicators::test_compute_all_columns` |
| FR-005 | `compute_all()` shall produce no all-NaN indicator series for sufficient data (≥ 30 rows) | Must | 1.2.8 | `core/indicators.py` | `test_indicators::test_no_all_nan` |
| FR-006 | Chaikin Money Flow (CMF) shall use (close-low-(high-close))/(high-low) × volume formula | Must | 1.2.6 | `core/indicators.py` | `test_indicators::test_cmf_formula` |
| FR-007 | SuperTrend indicator shall ratchet bands (never widen against prevailing trend direction) | Must | 1.2.6 | `core/indicators.py` | `test_indicators::test_supertrend_ratchet` |
| FR-008 | Ceiling/Floor Streak shall count consecutive ±7% limit days (HoSE threshold with 3% tolerance) | Must | 1.2.6 | `core/indicators.py` | `test_indicators::test_streak_counter` |
| FR-009 | Score shall be a float in [0, 100] for any valid input DataFrame | Must | 1.3 | `core/scoring.py` | `test_scoring::test_score_range` |
| FR-010 | Score breakdown dict values shall sum to ≤ score + 0.5 tolerance | Must | 1.3 | `core/scoring.py` | `test_scoring::test_breakdown_sum` |
| FR-011 | BUY signal shall be downgraded to WATCH when macro regime is BEAR or EXTREME_BEAR | Must | 1.3.9 | `core/scoring.py` | `test_scoring::test_regime_downgrade` |
| FR-012 | STRONG BUY signal shall be downgraded to BUY when manipulation flag is set | Should | 1.3.10 | `core/scoring.py` | `test_scoring::test_manipulation_downgrade` |
| FR-013 | ATR-based stop loss shall be calculated as: entry − (ATR × stop_atr_mult per timeframe) | Must | 1.3.8 | `core/scoring.py` | `test_scoring::test_stop_target_calc` |
| FR-014 | ATR-based target shall be calculated as: entry + (risk_distance × target_rr) | Must | 1.3.8 | `core/scoring.py` | `test_scoring::test_stop_target_calc` |
| FR-015 | `batch_score()` shall accept a list of tickers and return results in ≤ 2s for 60 tickers | Must | 1.3.11 | `core/scoring.py` | `test_scoring::test_batch_performance` |
| FR-016 | Macro score shall aggregate world market performance, VN breadth, and foreign flow | Must | 1.4.4 | `core/macro_data.py` | `test_regime::test_macro_score_range` |
| FR-017 | HMM regime detection shall classify market as one of: bull / sideways / bear | Must | 1.4.5 | `core/regime.py` | `test_regime::test_hmm_labels` |
| FR-018 | ML ensemble shall produce a price forecast for each requested timeframe | Must | 1.5.8 | `ml/ensemble.py` | `test_ensemble::test_forecast_not_nan` |
| FR-019 | Ensemble shall fall back gracefully when LSTM (TensorFlow) is not installed | Must | 1.5.2 | `ml/ensemble.py` | `test_ensemble::test_lstm_fallback` |
| FR-020 | Backtesting engine shall simulate trades using VN cost model (0.30% sell total) | Must | 1.6.2 | `backtest/engine.py` | `test_backtest::test_cost_model` |
| FR-021 | Backtesting engine shall calculate CAGR, Sharpe ratio, Max Drawdown, and Win Rate | Must | 1.6.4 | `backtest/engine.py` | `test_backtest::test_metrics` |
| FR-022 | `open_position()` shall calculate lot size based on capital × risk percentage | Must | 1.7.2 | `portfolio/tracker.py` | `test_portfolio::test_lot_size` |
| FR-023 | `close_position()` shall calculate realised P&L net of all trading costs | Must | 1.7.3 | `portfolio/tracker.py` | `test_portfolio::test_pnl_calc` |
| FR-024 | All position open/close events shall be written to audit JSONL | Must | 1.8.1 | `core/audit.py` | `test_portfolio::test_audit_on_open_close` |
| FR-025 | Audit log shall support filtering by action type, ticker, date range | Should | 1.8.2 | `core/audit.py` | `test_audit::test_filter` |
| FR-026 | Portfolio state shall persist to `data/portfolio.json` between sessions | Must | 1.7.5 | `portfolio/tracker.py` | `test_portfolio::test_persistence` |
| FR-027 | Scanner tab shall cache results per (timeframe, regime, macro_score, data_version) key | Should | 1.9.2 | `ui/scanner_tab.py` | Manual |
| FR-028 | Application shall render all 11 tabs without exception on valid data | Must | 1.9 | `app.py` | Manual + smoke test |
| FR-029 | World market data fetch shall complete within 3 seconds via parallel fetching | Should | 1.1.3 | `core/macro_data.py` | `test_regime::test_world_fetch_speed` |

---

## 2. Non-Functional Requirements

| ID | Requirement | Category | Priority | WBS | Acceptance Criterion |
|---|---|---|---|---|---|
| NFR-001 | Scoring 60 tickers shall complete in ≤ 2 seconds | Performance | Must | 1.3.11 | Benchmarked at 1.04s (17.3ms/ticker) |
| NFR-002 | World market fetch shall complete in ≤ 3 seconds | Performance | Must | 1.1.3 | Benchmarked at ~2s (vs 16s sequential) |
| NFR-003 | Application shall start without error on Python 3.10+ | Compatibility | Must | — | `streamlit run app.py` exits 0 |
| NFR-004 | All API calls shall have a 6-second timeout to prevent UI blocking | Reliability | Must | 1.1.1 | Timeout set on all `requests.get()` calls |
| NFR-005 | Audit log shall be append-only and never truncated | Data Integrity | Must | 1.8.1 | File opened with `mode='a'` exclusively |
| NFR-006 | Portfolio JSON shall be atomic-write safe (write temp → rename) | Data Integrity | Should | 1.7.5 | No partial-write corruption on crash |
| NFR-007 | All mathematical computations shall use numpy/pandas vectorised operations | Performance | Must | 1.2 | No Python-level loops in indicator hot paths (except SuperTrend ratchet) |
| NFR-008 | Test suite shall complete in ≤ 10 minutes | Maintainability | Should | 1.11 | Baseline: 159 tests in 330s |
| NFR-009 | No hardcoded API credentials in source code | Security | Must | 1.1 | OWASP A07 compliance |
| NFR-010 | All user inputs (ticker symbols, dates) shall be validated before use in API calls | Security | Must | 1.9 | OWASP A03 — input validation |
| NFR-011 | Indicator logic shall be deterministic (same inputs → same outputs) | Reliability | Must | 1.2 | Enforced by unit tests with fixed seeds |
| NFR-012 | Score explanation (breakdown dict) shall always accompany each score | Usability | Must | 1.3 | `breakdown` key present in all ScoreResult |
| NFR-013 | VN market-specific parameters (7% limit, T+2.5) shall be configurable via `config.py` | Maintainability | Must | 1.10 | Not hardcoded in logic modules |
| NFR-014 | Application shall handle missing/partial API data without crashing | Reliability | Must | 1.1 | Returns `None` or empty DataFrame with logged warning |
| NFR-015 | Code coverage shall be maintained for all `core/` modules | Maintainability | Must | 1.11 | All core module functions have at least one test |

---

## 3. Traceability Summary

| Requirement Group | Count | Test Coverage |
|---|---|---|
| Data layer (FR-001 to FR-003) | 3 | `test_data_fetcher.py` |
| Indicators (FR-004 to FR-008) | 5 | `test_indicators.py` |
| Scoring engine (FR-009 to FR-015) | 7 | `test_scoring.py` |
| Macro / Regime (FR-016 to FR-017) | 2 | `test_regime.py` |
| ML Ensemble (FR-018 to FR-019) | 2 | `test_ensemble.py` |
| Backtesting (FR-020 to FR-021) | 2 | `test_backtest.py` |
| Portfolio (FR-022 to FR-026) | 5 | `test_portfolio.py` |
| UI / Application (FR-027 to FR-029) | 3 | Manual |
| Non-Functional (NFR-001 to NFR-015) | 15 | Various |
| **Total** | **44** | **159 automated tests** |
