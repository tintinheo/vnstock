# -*- coding: utf-8 -*-
content = open("d:/portfolio/vnstock/TradingOS/docs/SRS/SRS-Alpha-v1.0.md", encoding="utf-8").read()

insert_at = content.find("\n## 9. Non-Functional Requirements")

new_sections = """

---

## 9. FR-7: AMF Wash Sale Directionality - IMPLEMENTED

**Status:** Fully implemented and tested (2026-04-24) - 750 unit tests passing.

FR-7 adds directionality analysis to the AMF: instead of only blocking manipulated signals,
the system now characterises which side (buy or sell) is dominant in the wash activity.
Four cross-validated data streams: TFI (Trade Flow Imbalance), OBI (Order Book Imbalance),
M-CVD (Micro-CVD from TCBS ticks), and amf_foreign_net.

### 9.2 Phase I � Micro-CVD from TCBS Ticks (DONE)

Module: `src/tradingos/data/intraday_collector.py`, `src/tradingos/core/anti_manip.py`

TCBS public API provides field `a` (aggressor): `B` = buy-driven, `S` = sell-driven.
`compute_mcvd(trades)` accumulates signed net volume directly from tick aggressor data �
replacing the inaccurate `close > open` OHLCV heuristic.

New schema fields: `amf_mcvd` (tick net), `amf_tfi`, `amf_obi`, `amf_obi_reconstructed`,
`amf_foreign_net`, `amf_wash_side` (BUY_WASH|SELL_WASH|NEUTRAL_WASH|NONE).

Tests: `test_amf_wash_directionality.py` � 27 tests.

### 9.3 Phase II � ATR-Based Position Sizing (DONE)

Module: `src/tradingos/core/sizing.py`

`compute_atr_position_size()` sizes the position so that 1% of portfolio is at risk
if the ATR-based stop is hit, then lot-rounds to 100 shares.

```
stop_distance       = ATR14 x atr_mult (default 2.0)
max_risk_vnd        = portfolio_value x risk_pct (default 0.01)
position_shares     = floor(max_risk_vnd / stop_distance / 100) x 100
```

AMF gating: BLOCK -> 0 shares; WARN -> shares x 0.5; PASS -> full.

Config: `position_sizing.risk_pct`, `position_sizing.atr_mult`, `position_sizing.warn_size_multiplier`
in `config/strategy.yaml`.

New schema fields (7): `atr_position_shares`, `atr_stop_price`, `atr_stop_distance`,
`atr_position_value`, `atr_risk_amount`, `atr_risk_pct_actual`, `atr_size_pct`.

Tests: `test_atr_position_sizing.py` � 17 tests.

### 9.4 Phase III � GJR-GARCH VaR / CVaR (DONE)

Module: `src/tradingos/core/risk_model.py`

Normal-distribution VaR is dangerous for VN equities (circuit breaker, gap-risk, F0 herding).
GJR-GARCH(1,1,1) with skewed-t captures the asymmetric leverage effect and fat left tails.

Three-tier fallback: GJR_GARCH (>=100 bars) -> HISTORICAL (30-99) -> NONE (<30).

Critical arch 8.0.0 note: `res.conditional_volatility[-1]` (numpy), NOT `.iloc[-1]`.

`calibrate_stop_with_var()` returns `min(atr_stop_price, var99_stop)` � the more conservative stop.

Tail regime: FAT_TAIL if excess kurtosis > 0.5 or skewness < -0.5.

New schema fields (7): `var_95`, `var_99`, `cvar_95`, `tail_regime`, `var_model`,
`var_cond_vol`, `stop_loss_var`.

Tests: `test_garch_var.py` � 24 tests.

### 9.5 Phase IV � VNDirect Orderbook Fallback (DONE)

Module: `src/tradingos/data/intraday_collector.py`

`fetch_vndirect_orderbook(symbol)` calls `api.vndirect.com.vn/v4/stocks` (no credentials,
public endpoint) and returns the same dict format as `fetch_ssi_orderbook()`.

Fallback chain in `fetch_intraday_features()`:
1. Try SSI iBoard (primary)
2. If SSI fails -> try VNDirect (logged at DEBUG level)
3. If both fail -> ob = None -> zero-fill OBI/foreign flow

TCBS tick data (TFI, M-CVD) has its own independent try/except and is unaffected.

Tests: `test_vndirect_fallback.py` � 17 tests.

### 9.6 FR-7 Test Baseline

| Phase | Test file | Tests |
|---|---|---|
| I: M-CVD | test_amf_wash_directionality.py | 27 |
| II: ATR sizing | test_atr_position_sizing.py | 17 |
| III: GJR-GARCH | test_garch_var.py | 24 |
| IV: VNDirect fallback | test_vndirect_fallback.py | 17 |
| **Total FR-7** | | **85** |

Suite baseline: **750 passed, 2 skipped** (2026-04-24).

---

## 10. FR-8: ML and AI Signal Layer � IMPLEMENTED

### 10.1 BiLSTM 10-day Directional Forecast

Module: `src/tradingos/core/bilstm_predictor.py`

Bidirectional LSTM trained on OHLCV + technical indicators for VN stocks.
Predicts price direction 10 calendar days ahead.

- Input: 60-bar sequence x N features
- Output: `signal` (UP|DOWN|FLAT), `up_prob` (0-1), `confidence` (HIGH|MEDIUM|LOW|NONE)
- Fallback: no trained model -> `signal = "NO_MODEL"`, `up_prob = 0.5`

Schema fields: `bilstm_10d_signal`, `bilstm_10d_up_prob`, `bilstm_10d_confidence`

### 10.2 Multi-Horizon Forecast Consensus

Module: `src/tradingos/core/horizon_forecast.py`

Aggregates votes from multiple signals across three horizons:
- Short (T+2-5): RSI trend, MACD, candlestick patterns
- Mid (T+7-10): HMM state, SMA alignment, M-CVD
- Long (T+12-15): Hurst exponent, AMD phase, BiLSTM

Schema fields: `fc_short_vote/conf/reasons`, `fc_mid_vote/conf/reasons`,
`fc_long_vote/conf/reasons`, `fc_overall_vote/conf`

### 10.3 Trend Warning Engine

Module: `src/tradingos/core/trend_warning.py`

Early warning for regime changes. Levels: NONE -> CAUTION -> DANGER.

Schema fields: `trend_warning`, `trend_warning_vi`, `trend_warning_conf`, `trend_warning_reasons`

### 10.4 T+ Setup Recommendation

Module: `src/tradingos/core/t_plus_engine.py`

Identifies optimal entry session and trigger for T+2.5 trading strategy.
Maps to sessions: morning (09:15-11:30), midday (13:00-14:30), afternoon (14:30-14:45).

Schema fields: `tplus_setup/vi`, `tplus_entry_trigger/low/high`, `tplus_target_t25/t5`,
`tplus_stop`, `tplus_rr`, `tplus_verdict/vi`, `tplus_reasons`, `tplus_risks`

### 10.5 Contextual Enrichment Modules

| Module | Purpose | Key schema fields |
|---|---|---|
| `macro.py` | Macro regime (interest rate, FX, commodities) | macro_score, macro_regime, macro_confidence, macro_staleness_days |
| `earnings.py` | Earnings risk window detection | earnings_risk, days_to_earnings, next_earnings_date |
| `fundamental.py` | CAN SLIM fundamentals (EPS, ROE, debt) | fundamental_score, eps_growth_yoy, revenue_growth_yoy, roe, debt_to_equity |
| `gap_vwap.py` | Gap analysis + VWAP daily/intraday | gap_pct, gap_type, vwap_daily_val, vwap_intraday, vwap_intraday_slope |
| `intraday_cvd.py` | CVD from real tick bars (FiinQuant/DNSE/SSI-5m) | cvd_signal, cvd_divergence, cvd_buying_pressure_pct, cvd_data_quality |
| `orderbook.py` | OBI from L3/reconstructed LOB | obi_pct, obi_signal |

---
"""

new_content = content[:insert_at] + new_sections + content[insert_at:]
open("d:/portfolio/vnstock/TradingOS/docs/SRS/SRS-Alpha-v1.0.md", "w", encoding="utf-8").write(new_content)
print("Done, inserted", len(new_sections), "chars at position", insert_at)
