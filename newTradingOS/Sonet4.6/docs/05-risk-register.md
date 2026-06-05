# Risk Register
## NewTradingOS v14.0

**PMBOK Knowledge Area:** Risk Management  
**Process Group:** Planning → Monitoring & Controlling  
**Document Version:** 3.0  
**Date:** 2026-05-30

---

## 1. Risk Rating Scale

| Probability | Score |
|---|---|
| High (> 60% likely) | 3 |
| Medium (30–60%) | 2 |
| Low (< 30%) | 1 |

| Impact | Score |
|---|---|
| High (blocks core function) | 3 |
| Medium (degrades quality/performance) | 2 |
| Low (minor inconvenience) | 1 |

**Risk Score = Probability × Impact. Threshold: ≥ 6 = Critical, 4–5 = High, 2–3 = Medium, 1 = Low**

---

## 2. Risk Register

### 2.1 Technical Risks

| ID | Risk Description | Category | Prob | Impact | Score | Level | Response Strategy | Owner | Status |
|---|---|---|---|---|---|---|---|---|---|
| RT-001 | DNSE API URL changes or adds authentication, breaking primary data fetch | Technical / API | 2 | 3 | 6 | Critical | Maintain 2-level fallback chain (DNSE → SSI); monitor API responses for HTTP 401/403; add automated health check test | Dev | Open |
| RT-002 | KBS IIS snapshot endpoint or payload contract changes, breaking breadth / foreign-flow ingestion | Technical / API | 3 | 2 | 6 | Critical | Keep snapshot-contract tests, surface stale warnings in UI, and isolate KBS parsing in `core/macro_data.py` for fast remediation if the payload changes | Dev | Open |
| RT-003 | Yahoo Finance API rate-limiting causes world market data failure | Technical / API | 2 | 2 | 4 | High | Cache last-successful world market result for ≤ 30 min; `get_macro_score()` returns `stale_fields` list; UI shows stale-data warning banner when fields are missing | Dev | **Mitigated** |
| RT-004 | ThreadPoolExecutor thread leaks under abnormal process termination | Technical | 1 | 2 | 2 | Medium | Use `with ThreadPoolExecutor() as ex:` pattern throughout; validated in current codebase | Dev | Mitigated |
| RT-005 | SuperTrend iterative ratchet introduces subtle off-by-one across different pandas versions | Technical | 2 | 2 | 4 | High | Pinned unit test with known dataset; runs in CI | Dev | Open |
| RT-006 | ML model returns NaN forecast for tickers with insufficient history | Technical / ML | 2 | 2 | 4 | High | All models guard against < 30 rows; fallback to heuristic forecast; unit tested | Dev | Mitigated |
| RT-007 | TensorFlow version conflict with Python 3.13 on Windows | Technical / ML | 3 | 1 | 3 | Medium | LSTM already has Holt's fallback; TF optional; documented in requirements | Dev | Mitigated |
| RT-008 | Streamlit version upgrade breaks session_state API or tab API | Technical / UI | 2 | 2 | 4 | High | Pin Streamlit version in requirements.txt (1.55.0); test before upgrading | Dev | Open |
| RT-009 | Concurrent Streamlit sessions cause portfolio.json race condition | Technical | 1 | 3 | 3 | Medium | Single-user deployment mitigates; add atomic file write (temp → rename) as hardening | Dev | Open |
| RT-010 | Large HOSE_LIST scan (110 tickers) exceeds browser timeout with slow internet | Technical / Performance | 2 | 2 | 4 | High | Batch download has 6s timeout per ticker; UI shows progress; reduce MARKET_SCAN_LIST if needed | Dev | Open |

---

### 2.2 Market / Data Risks

| ID | Risk Description | Category | Prob | Impact | Score | Level | Response Strategy | Owner | Status |
|---|---|---|---|---|---|---|---|---|---|
| RM-001 | SSC moves HoSE to T+1 settlement, making current T+2 close-readiness logic stale | Market / Regulatory | 3 | 2 | 6 | Critical | Portfolio and backtest settlement rules currently use business-day session counting for T+2 readiness. Review these helpers and update the settlement threshold when the market rule changes. | Dev | Open |
| RM-002 | HoSE raises daily price limit from ±7% to ±10% (trial announced) | Market / Regulatory | 2 | 2 | 4 | High | All limit references use per-exchange constants in `config.EXCHANGE_PRICE_LIMIT` (HOSE=0.07, HNX=0.10, UPCoM=0.15); `ceiling_floor_streak()` accepts `limit_pct` param; `compute_all(exchange=)` routes per ticker; `batch_score(exchange_map=)` and `render_scanner_tab(exchange_map=)` wire exchange data end-to-end | Dev | **Mitigated** |
| RM-003 | Scoring model trained on 2015–2025 data becomes less accurate in structural regime shifts (e.g. post-pandemic) | Market | 2 | 2 | 4 | High | Periodic backtesting review; compare win rate vs benchmark; ML ensemble provides model-diverse forecasts | Dev | Open |
| RM-004 | Thin liquidity tickers (HNX small-cap) produce misleading signals due to low volume | Market | 3 | 2 | 6 | Critical | Minimum volume filter applied before scoring; flagged in UI; review thresholds quarterly | Dev | Open |
| RM-005 | Foreign flow data is currently limited to a KBS intraday session snapshot, so multi-session institutional flow trends are unavailable and score component 5 may be less stable than intended | Market / Data | 2 | 2 | 4 | High | Contract is now explicit: `fetch_foreign_flow_ticker()` exposes session-only flow, UI labels it as `KBS snapshot | session net only`, and `batch_score()` ignores proxy `net_20d` values. A reliable multi-session source is still needed for full mitigation. | Dev | **Partially Mitigated** |
| RM-006 | Stop-loss / take-profit at invalid VN prices rejected by broker OMS | Market / Operational | 3 | 2 | 6 | Critical | `round_to_tick()` in `config.py` enforces HOSE 10/50/100 VND tick bands and HNX/UPCOM 100 VND; applied to all stop/target calculations in `scoring.py`; safety guard ensures stop < price < target after rounding | Dev | **Mitigated** |
| RM-007 | Backtest P&L overstated due to fractional-share position sizing (VN requires 100-share lots) | Backtest / Simulation | 3 | 2 | 6 | Critical | `backtest/engine.py` uses `position_size_vnd()` to floor shares to nearest 100-lot; `BacktestTrade.n_shares` exposes lot-aligned count; P&L uses `_vnd_committed` not `capital × pos_pct` | Dev | **Mitigated** |
| RM-008 | RSI/ATR using SMA instead of Wilder EWM gives less responsive signals, missing VN limit-hit extremes | Model Accuracy | 2 | 2 | 4 | High | RSI and ATR now use `_wilder_smooth(series, period)` — EWM alpha=1/period as per Wilder (1978); consistent with ADX; RSI handles loss=0 edge case by returning 100.0 | Dev | **Mitigated** |
| RM-009 | Macro score blind to S&P 500 / CSI 300 movements — major VN-Index drivers unmodelled | Model Accuracy | 2 | 2 | 4 | High | `get_macro_score()` now adds ±0.25–0.75 pts for S&P 500 5-day return and ±0.25–0.50 pts for CSI 300 5-day return; asymmetric downside penalty for crash events; score still capped at 10 | Dev | **Mitigated** |

---

### 2.3 ML / Model Risks

| ID | Risk Description | Category | Prob | Impact | Score | Level | Response Strategy | Owner | Status |
|---|---|---|---|---|---|---|---|---|---|
| RML-001 | ML models overfit to 2020–2022 bull run patterns | ML | 2 | 3 | 6 | Critical | RF now uses 80/20 walk-forward train/test split; `_walk_forward_mape()` reports out-of-sample MAPE; ensemble diversity reduces single-model overfit | Dev | **Mitigated** |
| RML-002 | Prophet model fails on tickers with public holidays creating gaps | ML | 2 | 1 | 2 | Medium | Prophet handles missing dates natively; `fill_holes=True` set in training config | Dev | Mitigated |
| RML-003 | Monte Carlo simulation uses Gaussian returns (fat tails underestimated in VN market) | ML | 3 | 2 | 6 | Critical | Confidence intervals are advisory only, not position sizing input; document this limitation in Guide | Dev | Open |
| RML-004 | XGBoost feature set grows stale as new indicators added but retraining not triggered | ML | 2 | 2 | 4 | High | Document retraining procedure; version model artifacts; alert when indicator set changes | Dev | Open |

---

### 2.4 Security Risks

| ID | Risk Description | Category | Prob | Impact | Score | Level | Response Strategy | Owner | Status |
|---|---|---|---|---|---|---|---|---|---|
| RS-001 | User-supplied ticker input used unsanitised in API URL construction | Security (OWASP A03) | 1 | 3 | 3 | Medium | Validate ticker against known universe whitelist before constructing API URL | Dev | Open |
| RS-002 | `audit.jsonl` contains business-sensitive position data (entry prices, capital) | Security | 1 | 2 | 2 | Medium | File stored locally; application is single-user; document that data/ folder should not be committed to public git | Dev | Open |
| RS-003 | `portfolio.json` persists to disk; risk of sensitive data exposure in shared environments | Security | 1 | 2 | 2 | Medium | Add `data/` to `.gitignore`; document data privacy in Guide | Dev | Mitigated |

---

### 2.5 Performance Risks

| ID | Risk Description | Category | Prob | Impact | Score | Level | Response Strategy | Owner | Status |
|---|---|---|---|---|---|---|---|---|---|
| RP-001 | Streamlit re-runs entire script on every widget interaction, causing redundant recalculations | Performance | 3 | 2 | 6 | Critical | Session-state scan cache keyed on (tf, regime, macro_score, data_version); data loaded once per session | Dev | Mitigated |
| RP-002 | Adding new tickers to MARKET_SCAN_LIST increases scan time linearly | Performance | 2 | 2 | 4 | High | Monitor scan time benchmark; maintain ThreadPoolExecutor(6); cap MARKET_SCAN_LIST at 150 | Dev | Open |

---

## 3. Risk Summary

| Level | Count | IDs |
|---|---|---|
| Critical (≥ 6) | 8 | RT-001, RT-002, RM-001, RM-004, RML-001, RML-003, RP-001, RM-002* |
| High (4–5) | 8 | RT-003, RT-005, RT-006, RT-008, RT-010, RM-003, RML-004, RP-002 |
| Medium (2–3) | 8 | RT-004, RT-007, RT-009, RM-005, RML-002, RS-001, RS-002, RS-003 |
| Mitigated | 6 | RT-004, RT-006, RT-007, RML-002, RS-003, RP-001 |

*RM-002 rated Critical because limit_pct is a parameter default, not an environment config — requires code update.

---

## 4. Risk Response Actions (Open Critical Risks)

| Risk | Action | Due |
|---|---|---|
| RT-001 | Add nightly API health check script | Next release |
| RT-002 | Add payload snapshot fixtures for KBS breadth / foreign-flow contract | Next release |
| RM-001 | Verify T+1 SSC announcement dates; update `SETTLEMENT_T_PLUS = 1.0` when live | Q3 2026 |
| RM-004 | Add minimum volume filter (e.g. 3-day avg > 100K shares) to scanner | Next release |
| RML-001 | Run backtesting comparison report quarterly | Quarterly |
| RML-003 | Add disclaimer banner to ML Forecast tab | Next release |
| RS-001 | Add ticker whitelist validation in `data_fetcher.py` | Next release |
