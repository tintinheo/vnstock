# Assessment: Captain Seventh QUANT TERMINAL v28.0

**Platform:** Vietnam Stock Exchange (HOSE / HNX / UPCOM)
**File:** quant_app.py — ~10,034 lines, v28.0
**Assessment Date:** March 11, 2026

---

## 1. Executive Summary

The application is a well-engineered multi-source quantitative platform with strong structural design: a resilient 7-source data pipeline, 9 technical indicators, sector-aware fundamental valuation, a 7-model ML ensemble, and bilingual support. However, several analytical algorithms contain mathematical inaccuracies, the ML layer lacks out-of-sample validation, the backtesting methodology has structural flaws, and several VN market–specific nuances are either missing or incorrectly modelled.

---

## 2. Data Pipeline

### ✅ What Works Well
- The 7-source cascade (SSI → DNSE → CafeF → TCBS → VNDirect → yFinance) is pragmatic and resilient for an unofficial-API environment.
- Per-source minimum row guards (`_SRC_MIN`) prevent shallow data from contaminating analysis.
- Exchange-specific routing in `TICKER_EXCHANGE` correctly maps HNX/UPCOM tickers to avoid wrong exchange scraping.
- Price normalisation heuristic (`if median < 500 → ×1000`) handles APIs that return prices in thousands of VND.

### ⚠️ Issues & Inaccuracies

| # | Location | Issue |
|---|----------|-------|
| D-1 | `clean_data()` ~L1470 | The commented IQR multiplier says `1.5 × IQR` as the standard, but the code uses `3 × IQR`. The comment is misleading and the 3× threshold is too wide, allowing genuine split-adjusted outliers or API errors through. |
| D-2 | `scan_one_ticker()` ~L2480 | Only fetches `days=365`. SMA200 requires at least 200 trading days (~280 calendar days). With 365 calendar days, on SSI/DNSE which only cover trading days, the dataset may have only ~250 rows — leaving `SMA200` with `NaN` for the first 50 rows and possibly the last row depending on market calendar. |
| D-3 | `_parse_udf()` ~L837 | The price scale check `if median < 500` could incorrectly rescale genuinely cheap stocks (e.g. VKC, TIG trading at 2,000–4,000 VND). Threshold should be `< 1,000` or applied per-stock from a known price range table. |
| D-4 | Pipeline order | Comments and changelog are contradictory: the module docstring says `DNSE` is primary, but `ENH-33` moved `SSI` to first position, which is correctly reflected in `_PIPELINE`. The documentation should be updated to avoid confusion. |
| D-5 | `_fetch_yfinance()` ~L1270 | `yf.download()` returns adjusted prices by default with `auto_adjust=True`. All other VN sources return **unadjusted** prices. This creates inconsistency when yFinance is triggered for a VN ticker — technical indicators computed on adjusted prices will not match the brokerage chart. |

### 🔧 Recommended Fixes
- **D-1**: Change `3 * IQR` to `2.5 * IQR` and update the comment.
- **D-2**: Change `scan_one_ticker(t, days=365)` to `days=400` (or `530` for full SMA200 coverage from trading days).
- **D-3**: Change median threshold to `< 1_000`.
- **D-5**: For VN tickers via yFinance, set `auto_adjust=False` and use `Close` directly.

---

## 3. Technical Indicators (`calculate_indicators`)

### ✅ What Works Well
- RSI with Wilder's smoothing (`ewm(alpha=1/14, adjust=False)`) is correctly implemented.
- MACD (12,26,9) is standard and correct.
- Bollinger Bands (20, ±2σ) are standard.
- Golden/Death Cross detection logic is correct.
- ADX implementation: the `× 14` factors in `atr14`, `pdm14`, `ndm14` cancel out in division, so the result is numerically correct.

### ⚠️ Issues & Inaccuracies

| # | Location | Issue | Severity |
|---|----------|-------|----------|
| T-1 | `calculate_indicators()` ~L1666 | **RSI NaN fill**: `df["RSI"].fillna(50)` — when `avg_loss = 0` (all gains, no losses), RSI should be **100**, not 50. Filling with 50 misclassifies a purely bullish streak as neutral, suppressing BUY signals. | High |
| T-2 | `calculate_indicators()` ~L1695 | **Stochastic, Williams %R, CCI, OBV** all use Python `for` loops. For a ~250-row array these are slow (~10ms each per ticker). When scanning 200 tickers, this adds ~2–4 seconds of pure computation. These should be vectorised with `pd.Series.rolling()`. | Medium |
| T-3 | `compute_composite_score()` ~L1781 | **BUY scoring only**: Volume spike (`last_vol / avg_vol > 1.5`) adds `+3` only for BUY signals. For SELL signals, volume confirmation is absent — a high-volume breakdown is a more reliable SELL signal than a low-volume RSI reading. | Medium |
| T-4 | `scan_one_ticker()` ~L2509 | **SELL signal has no trend check**: `elif rsi_v > rsi_sell_thresh and c_v > bbu_v: hanh_vi = "BÁN"` during a strong breakout uptrend. A stock in a powerful trend can stay overbought for weeks. The absence of a "NOT in strong trend" guard causes false SELL signals on breakouts. | High |
| T-5 | `scan_one_ticker()` ~L2520 | **Duplicated dead code**: the `if st.session_state.lang == "VI"` and `else` blocks for determining `hanh_vi` are identical. The language has no effect here — it should be removed. | Low |
| T-6 | `compute_composite_score()` | **Score normalisation absent**: The raw score is unbounded. A ticker with 10 confirmations can score 40+ while one with 2 confirmations scores 6. The score is displayed as a percentage-like metric but has no ceiling. Users may misinterpret absolute values. | Medium |
| T-7 | `ADX` calculation ~L1697 | The computation uses `df["DX"].ewm(alpha=1/14, min_periods=14, adjust=False).mean()` directly for ADX. This is correct Wilder smoothing. However, `min_periods=14` for `DX` means ADX itself will be NaN for the first ~28 rows (14 for DX + 14 for ADX). Code should guard against this when reading `ADX` in signal logic. | Low |

### 🔧 Recommended Fixes

**T-1 — RSI NaN fill (critical):**
```python
# Current (wrong):
df["RSI"] = (100 - 100 / (1 + rs)).fillna(50)

# Corrected:
df["RSI"] = (100 - 100 / (1 + rs))
df["RSI"] = df["RSI"].where(avg_loss != 0, 100.0).fillna(50)
```

**T-4 — SELL signal: add ADX guard to avoid false SELL on breakouts:**
```python
# Add: not (adx_v > 30 and trend_ok) as a guard for the sell signal
is_strong_uptrend = (adx_v is not None and adx_v > 30 and trend_ok)
if rsi_v > rsi_sell_thresh and c_v > bbu_v and not is_strong_uptrend:
    hanh_vi = "BÁN"
```

**T-3 — Add volume confirmation to SELL scoring in `compute_composite_score`:**
```python
elif signal_type == "BÁN":
    # ... existing RSI/BB/Stoch checks ...
    if avg_vol and avg_vol > 0 and last_vol / avg_vol > 1.5:
        score += 3; confirms.append(f"KL↑={last_vol/avg_vol:.1f}×")
```

---

## 4. Fundamental Analysis & Valuation

### ✅ What Works Well
- Sector-aware method selection (Banking → P/B+DDM, Cyclicals → normalised EPS) is methodologically sound.
- Negative EPS guard (disabling DCF + PE) is correct.
- Risk scoring across 5 dimensions (debt, liquidity, profitability, growth, valuation) is well-structured.
- Bilingual explanations are detailed and well-calibrated.

### ⚠️ Issues & Inaccuracies

| # | Location | Issue | Severity |
|---|----------|-------|----------|
| F-1 | `compute_dcf_valuation()` ~L3528 | **EPS-based DCF**: The function discounts projected EPS, not Free Cash Flow. A real DCF discounts FCFF or FCFE. Using EPS as a proxy yields a PE-like result, not a true intrinsic value. For capital-intensive sectors (steel, power, real estate), EPS ≠ FCFE due to high capex. | High |
| F-2 | `compute_dcf_valuation()` | **Single-stage model only**: A 5-year single-stage model significantly undervalues high-growth companies (FPT, tech). A two-stage DCF (high-growth → terminal) would be more accurate. | Medium |
| F-3 | `compute_dcf_valuation()` | **Uniform 12% discount rate**: WACC should vary by sector (banks need higher Ke due to leverage; regulated utilities need lower Ke). Currently `Ke=12%` for all, which overvalues defensive stocks and undervalues high-beta cyclicals. | Medium |
| F-4 | `compute_graham_value()` ~L3573 | **Unmodified Graham multiplier of 22.5**: This constant was calibrated by Graham for US markets in 1973 with bond yields at ~6–7%. Vietnam's 10-year bond yield is ~4–4.5% in 2026 (lower = more liberal valuation justified). The multiplier should be adjusted: `22.5 × (4.4_bond_yield / current_VN_10Y_yield)`. | High |
| F-5 | `score_fundamental_risk()` ~L3592 | **D/E risk ignores banking context**: Banks have structural D/E > 10 (deposits = liabilities). The code will assign `risk = 9.0` (maximum) to all banks. The banking sector should use NPL ratio or CAR instead of D/E. | High |
| F-6 | `SECTOR_PE_BENCH` ~L3469 | `"Ngân hàng": 12.0` — the comment says "P/B+DDM preferred; DCF/PE invalid for banks" but a PE benchmark is still defined. If the valuation method guard (`get_valuation_method`) does disable PE for banks, the PE table entry for banks is dead code. If it's not always disabled, the value 12× is used incorrectly. | Low |
| F-7 | `compute_pb_valuation()` | **Uniform CoE=12%**: The ROE/CoE justified P/B model is sound in theory. However, CoE should reflect sector risk. A bank with ROE=20% and CoE=14% (banking beta) gives P/B=1.43, not P/B=1.67 (CoE=12%). | Low |
| F-8 | `compute_composite_fundamental_score()` | **DXY penalty of −5 to −10 pts** is applied for `dxy > 106`. Current DXY is ~104–106 (early 2026). The threshold may be frequently triggered or almost never triggered depending on macro regime. The penalty range is also not tied to the magnitude. | Low |

### 🔧 Recommended Fixes

**F-4 — Graham multiplier calibration:**
```python
# Replace: return round((22.5 * eps_ttm * bvps) ** 0.5, 0)
# With calibrated multiplier based on VN bond yield:
VN_10Y_BOND_YIELD = 0.045  # update periodically
US_BASE_YIELD = 0.044       # Graham's original calibration
multiplier = 22.5 * (US_BASE_YIELD / VN_10Y_BOND_YIELD)
return round((multiplier * eps_ttm * bvps) ** 0.5, 0)
```

**F-5 — Banking D/E exception:**
```python
def score_fundamental_risk(ratio_df, income_df, balance_df, sector=""):
    ...
    # Add banking exemption:
    if sector in _BANKING_SECTOR:
        scores["debt"] = 5.0  # neutral; banking D/E is structural
        explanations["debt"] = {"VI": "Ngân hàng: D/E không có ý nghĩa phân tích (tiền gửi = nợ). Dùng CAR/NPL.",
                                 "EN": "Banking: D/E is not meaningful (deposits = liabilities). Use CAR/NPL."}
```

---

## 5. ML Forecasting

### ✅ What Works Well
- Ensemble approach (7 models) reduces individual model bias.
- Monte Carlo GBM provides uncertainty bands (P10–P90) with appropriate 1.05× sigma inflation.
- Prophet with quarterly seasonality (`period=63`) maps correctly to Vietnam's fiscal quarter structure.
- Forecast audit trail (`save_ml_forecast_audit`) enables historical accuracy tracking.

### ⚠️ Issues & Inaccuracies

| # | Location | Issue | Severity |
|---|----------|-------|----------|
| M-1 | `forecast_arima()` ~L2220 | **Fixed ARIMA(2,1,2) order**: This is hardcoded without model selection. ARIMA order should be chosen by AIC/BIC or auto-selection. On trending stocks, ARIMA(1,1,0) may fit better; on range-bound stocks, ARIMA(0,1,1) is often optimal. | High |
| M-2 | `forecast_holt()` ~L2200 | **Poor initial trend estimate**: `T = prices[1] - prices[0]` uses a single observation for initial trend, which is highly sensitive to the first data point. Should use `T = (prices[-1] - prices[0]) / (len(prices) - 1)` for a more stable initialisation. | Medium |
| M-3 | `forecast_sklearn()` ~L2230 | **No technical features**: SVR and RandomForest only use price lags and time index. Adding RSI, MACD, and volume features would substantially improve non-linear pattern detection. Including these is the primary advantage of ML over statistical models. | High |
| M-4 | `MODEL_WEIGHTS` | **Static weights**: All weights are fixed regardless of recent model performance. If ARIMA diverges significantly from DNSE/SSI data, it still receives 15% weight. Dynamic weight adjustment based on recent RMSE would improve ensemble accuracy. | Medium |
| M-5 | `forecast_monte_carlo()` | **GBM assumption breaking conditions**: Vietnam stocks have hard circuit breakers (±7/10/15%). GBM can simulate returns outside those limits, producing physically impossible prices. The simulation should clip single-step returns to the exchange band. | Medium |
| M-6 | `run_prophet_forecast()` | **`changepoint_prior_scale=0.15`** is at the high end of the default prior (Facebook default is 0.05). This makes the model more reactive to recent changes, potentially overfitting to the most recent trend direction. Should be 0.05–0.10 for VN stocks which trend gradually. | Low |
| M-7 | All models | **No out-of-sample validation**: Models are never evaluated against held-out test data. There is no RMSE, MAPE, or directional accuracy metric displayed to the user. Users cannot assess forecast reliability. | High |

### 🔧 Recommended Fixes

**M-2 — Better Holt initialisation:**
```python
def forecast_holt(prices, n_days, alpha=0.25, beta=0.10):
    prices = [float(p) for p in prices]
    if len(prices) < 2: return np.array([prices[-1]] * n_days)
    L = prices[0]
    T = (prices[-1] - prices[0]) / (len(prices) - 1)  # stable regression slope
    ...
```

**M-1 — ARIMA with AIC selection (if available):**
```python
def forecast_arima(prices, n_days):
    orders_to_try = [(1,1,1), (2,1,2), (1,1,0), (0,1,1)]
    best_aic, best_res = np.inf, None
    log_p = np.log(np.array(prices, dtype=float))
    for order in orders_to_try:
        try:
            m = ARIMA(log_p, order=order).fit()
            if m.aic < best_aic:
                best_aic, best_res = m.aic, m
        except Exception:
            continue
    if best_res is None: return None, None
    fc = best_res.forecast(steps=n_days)
    ...
```

**M-5 — Clip Monte Carlo returns to exchange limits:**
```python
# Inside forecast_monte_carlo, after computing log returns:
band_limit = 0.07   # HOSE default; pass as parameter for HNX (0.10) / UPCOM (0.15)
log_r_clipped = np.clip(np.random.normal(mu, sigma, (n_sims, n_days)),
                         -band_limit, band_limit)
sims = last * np.exp(np.cumsum(log_r_clipped, axis=1))
```

---

## 6. Backtesting Engine

### ✅ What Works Well
- Session-based T+2 counting using `i - buy_row_idx` on the actual DataFrame index is correct for trading session semantics.
- Full fee model (buy fee 0.15%, sell fee 0.15%, tax 0.1%, slippage 0.05%) matches real brokerage costs.
- ATR-based stop loss calculation is methodologically sound.

### ⚠️ Issues & Inaccuracies

| # | Location | Issue | Severity |
|---|----------|-------|----------|
| B-1 | `run_backtest()` ~L2140 | **Survivorship bias**: Only currently tracked tickers are backtested. Delisted or compulsorily acquired stocks (FLC, HQC, etc.) are excluded, inflating win rate by removing catastrophic losses. | High |
| B-2 | `run_backtest()` | **Sharpe ratio is per-trade, not time-series**: `sharpe = mean(pnl%) / std(pnl%)` across discrete trades. This is not comparable to industry-standard Sharpe (annualised excess return / annualised volatility of daily returns). | High |
| B-3 | `run_backtest()` | **100% capital allocation per trade**: The engine goes all-in on each signal. In real trading, position sizing (Kelly criterion or % of capital per trade) limits drawdown. The current model produces optimistic Sharpe as it compounds all capital on each trade. | Medium |
| B-4 | `run_backtest()` | **No bid-ask spread**: The slippage of 0.05% is applied uniformly. For illiquid UPCOM stocks, effective spread can be 0.3–0.5%. The model underestimates transaction costs for small-cap stocks. | Medium |
| B-5 | `run_backtest()` | **Market impact not modelled**: For large positions (LOT × price × n_lots), the buy/sell order itself would move the price. No impact model is applied. | Low |

### 🔧 Recommended Fixes

**B-2 — Annualised Sharpe from equity curve:**
```python
# After building eq array, compute daily return Sharpe:
daily_returns = np.diff(eq) / eq[:-1]
if daily_returns.std() > 0:
    sharpe_annualised = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
else:
    sharpe_annualised = 0
metrics["sharpe"] = round(sharpe_annualised, 2)
```

---

## 7. Vietnam Market–Specific Issues

| # | Issue | Severity |
|---|-------|----------|
| V-1 | **HNX lot size**: `LOT_SIZE = 100` is used globally. HNX has had an **odd-lot market (1 share minimum)** since 2022. Using 100-share lots for HNX understates the number of feasible entry points and distorts position sizing calculations. | Medium |
| V-2 | **`round_price_hose()` applied to HNX/UPCOM**: The function rounds to HoSE tick sizes (100 VNĐ steps for prices >50,000). HNX and UPCOM price ticks are different. Recommended prices for HNX/UPCOM tickers will be slightly wrong. | Low |
| V-3 | **Price limits in signal generation**: `get_price_limits()` calculates ceiling/floor prices but these are only applied in `compute_recommended_prices()`. The Buy signal itself does not check that the recommended entry price is within the trading band for the current session. A generated BUY at a price above the ceiling is physically impossible. | High |
| V-4 | **Dividend adjustment inconsistency**: DNSE and SSI return unadjusted prices; TCBS returns adjusted prices. When TCBS is the fallback source, the price series will have artificial gaps at dividend dates, biasing BB and MA calculations downward. | High |
| V-5 | **Foreign Ownership Limit (FOL)**: FOL is fetched but only shown as metadata. When a stock is at 100% FOL (e.g. VNM at times), foreign investors cannot buy. The BUY signal does not surface this critical blocker. | Medium |
| V-6 | **Banking D/E**: As noted in F-5, banking sector D/E is structurally >10; scoring it at maximum risk is misleading for every bank stock. | High |

### 🔧 Recommended Fixes

**V-3 — Guard BUY entry against trading band:**
```python
# In compute_recommended_prices():
if floor_p > 0 and ceil_p > 0:
    # Final check: recommended buy must be within today's trading band
    rec_buy = max(floor_p, min(rec_buy, ceil_p))
    rec_sell_tp1 = min(rec_sell_tp1, ceil_p)
    rec_sell_tp2 = min(rec_sell_tp2, ceil_p)
```

**V-4 — Flag TCBS adjusted-price source to user:**
```python
# In download_data(), when source = "TCBS", attach a metadata flag:
return df, "TCBS-adj", None  # suffix indicates adjusted prices
# Then in UI, display a warning badge when source contains "-adj"
```

---

## 8. Composite Score & Signal Logic

### ⚠️ Issues

| # | Issue | Severity |
|---|-------|----------|
| S-1 | **Score normalisation absent**: `compute_composite_score` returns raw additive scores (unbounded). The score displayed to users looks like a percentage but has no defined ceiling. A score of 35 vs 18 is meaningful in relative terms but the values carry no absolute interpretation. | Medium |
| S-2 | **`sig_type` bug for WATCH**: `sig_type = "BUY" if hanh_vi == "MUA" else ("BÁN" if hanh_vi == "BÁN" else "BUY")` — when `hanh_vi == "THEO DÕI"`, `sig_type = "BUY"`. This means WATCH tickers are scored using BUY criteria, producing misleading composite scores for neutral signals. | Medium |
| S-3 | **`_IMPORT_HEAVY` defined twice** (lines ~3488 and ~5515). If definitions diverge in a future edit, sector-based macro penalties will inconsistently apply. | Low |

### 🔧 Recommended Fix for S-2
```python
# In scan_one_ticker():
sig_type = "BUY" if hanh_vi == "MUA" else ("BÁN" if hanh_vi == "BÁN" else "WATCH")

# In compute_composite_score(), add a WATCH branch:
elif signal_type in ("THEO DÕI", "WATCH"):
    score = 0.0  # neutral — no directional bias
    confirms = ["Sideway"]
```

---

## 9. Performance & Security

| # | Issue | Recommendation |
|---|-------|----------------|
| P-1 | Sequential scan of 200+ tickers with 7 API attempts each is O(n×m) and can take 15–30 minutes worst case. | Implement `concurrent.futures.ThreadPoolExecutor` for parallel ticker scanning (max 10 threads). |
| P-2 | Python for-loops in `calculate_indicators` for ATR, Stochastic, OBV, Williams %R are ~10× slower than vectorised equivalents. | Replace with `df.rolling().apply()` or `numpy` stride tricks. |
| SEC-1 | Ticker input is passed directly to API URL strings and file system paths (`ML_AUDIT_PATH/{symbol}.json`) without sanitisation. A malformed ticker like `../../etc/passwd` or `; rm -rf` could cause path traversal or unexpected behaviour. | Validate ticker with a regex: `if not re.fullmatch(r'[A-Z0-9]{2,10}', symbol.strip().upper()): raise ValueError(...)` before any API call or file operation. |
| SEC-2 | News items from VNDirect contain a `url` field rendered as `[title](url)` in Markdown. An API returning a `javascript:` URI could cause XSS in the Streamlit UI. | Validate URLs with `urllib.parse.urlparse()` to ensure scheme is `http` or `https` before rendering. |

---

## 10. Summary Priority Table

| Priority | ID | Description | Impact |
|----------|----|-------------|--------|
| 🔴 Critical | T-1 | RSI NaN → 50 (should be 100) | BUY signal suppressed in uptrends |
| 🔴 Critical | T-4 | SELL signal fires on breakouts | False negatives on momentum stocks |
| 🔴 Critical | F-5 | Banking D/E = max risk | All bank BUY signals penalised |
| 🔴 Critical | V-3 | Entry not bounded by trading band | Unexecutable recommended prices |
| 🔴 Critical | V-4 | TCBS adjusted vs unadjusted price mix | BB/MA bias at dividend dates |
| 🟠 High | F-1 | EPS-based DCF (not FCFE) | Overvalues capital-light, undervalues capital-heavy |
| 🟠 High | F-4 | Graham multiplier 22.5 not VN-calibrated | Overestimates intrinsic value for VN rate environment |
| 🟠 High | M-1 | Fixed ARIMA(2,1,2) | Forecast accuracy suboptimal |
| 🟠 High | M-7 | No out-of-sample validation for ML | Users cannot assess forecast reliability |
| 🟠 High | B-1 | Survivorship bias in backtest | Win rate inflated by 10–20 pp estimate |
| 🟠 High | B-2 | Per-trade Sharpe, not annualised | Sharpe is not comparable to industry standard |
| 🟡 Medium | M-2 | Poor Holt trend initialisation | Short-horizon forecasts biased |
| 🟡 Medium | M-3 | No technical features in SVR/RF | ML advantage not realised |
| 🟡 Medium | S-2 | WATCH scored as BUY | Misleading composite score for neutral signals |
| 🟡 Medium | D-2 | Only 365 calendar days pulled | SMA200 NaN on recent rows |
| 🟡 Medium | SEC-1 | No ticker input sanitisation | Path traversal vulnerability |

---

## 11. What the Application Does Well

1. **Data resilience** — 7-source cascade is production-quality for an unofficial API environment.
2. **Sector awareness** — Method switching (Banking → DDM, Cyclicals → normalised EPS) is aligned with CFA/VCSC analyst practice.
3. **Vietnam market context** — Price limit bands, exchange routing, T+2 session counting, VND price rounding are correctly implemented.
4. **Auditability** — Both the ML forecast audit trail and the structured JSON audit log provide traceable, reproducible signal history.
5. **Bilingual UX** — Complete VI/EN coverage with contextually correct financial terminology.
6. **Manipulation detection** (`detect_doi_lai`) — Heuristics for pump-and-dump, wash trading, and smart money accumulation are practically useful for retail investors in the VN market, which has documented pump activity.
7. **Composite signal divergence explanation** — The explicit acknowledgement that Technical (T+2) and Fundamental (6–24M) signals can conflict and how to interpret that is a significant UX strength.