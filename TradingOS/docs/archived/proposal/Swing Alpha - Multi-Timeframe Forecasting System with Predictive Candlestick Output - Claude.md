## Multi-Timeframe Forecasting System with Predictive Candlestick Output


> **📌 Interdisciplinary Academic Board** | Computational Finance · Quantitative Trading · Data Science  
> ** Version:** 3.0 — Technical Architecture & Formula Specification  
> **Date:** 22/03/2026

---

```
╔═══════════════════════════════════════════════════════════════════════╗
║  INPUT: Ticker + Timeframe (Monthly/Weekly/N-Days)                   ║
║         ↓                                                             ║
║  [DATA LAYER] → [FORECAST ENGINE] → [CANDLE BUILDER] → [OUTPUT]     ║
║                                                                       ║
║  OUTPUT: Predicted Candle + Score + Action + Timing + Explanation    ║
╚═══════════════════════════════════════════════════════════════════════╝


# ═══════════════════════════════════════════════════
# 🇬🇧 PART II — ENGLISH VERSION
# ═══════════════════════════════════════════════════

---

## 🟦 1. SYSTEM ARCHITECTURE OVERVIEW

### 1.1 Processing Pipeline

```
┌──────────────────────────────────────────────────────────────────────┐
│                🔷 MULTI-TIMEFRAME FORECAST PIPELINE                  │
├─────────────┬──────────────────┬───────────────────┬────────────────┤
│  LAYER 1    │    LAYER 2       │    LAYER 3        │   LAYER 4      │
│  DATA       │    FEATURES      │    MODELS         │   OUTPUT       │
├─────────────┼──────────────────┼───────────────────┼────────────────┤
│ SSI API     │ Candlestick      │ SARIMA/SARIMAX    │ OHLCV Candle   │
│ TCBS        │ Patterns         │ LSTM/GRU+Attn     │ Direction %    │
│ VNDirect    │ VN-4 Factors     │ Facebook Prophet  │ Action Label   │
│ Vietstock   │ Fourier Decomp   │ Ensemble Voting   │ Entry/Exit     │
│             │ GARCH Volatility │ PSO Calibration   │ Confidence %   │
│             │ HMM Regime Detect│ Walk-Forward Val  │ Explanation    │
└─────────────┴──────────────────┴───────────────────┴────────────────┘
```

### 1.2 Input / Output Contract

| Input Parameter | Type | Example | Description |
|:---|:---:|:---:|:---|
| `ticker` | `str` | `"VIC"` | Stock symbol |
| `timeframe` | `enum` | `"monthly"` | `monthly` / `weekly` / `custom` |
| `n_days` | `int` | `45` | Forecast horizon (custom only) |
| `lookback` | `int` | `252` | Historical sessions for training |
| `confidence_level` | `float` | `0.95` | Prediction interval confidence |

---

## 🟨 2. SIGNAL DECOMPOSITION AND REGIME DETECTION

### 2.1 STL Time Series Decomposition

> The core principle: any price series can be decomposed into Trend + Seasonality + Cycle + Residual (Y(t) = T(t) + S(t) + C(t) + R(t)). Forecasting each component separately and recombining yields more accurate results than treating the series as a black box.

The Python formulas provided in the Vietnamese section above apply verbatim. Key parameters for Vietnam's market:
- `period=20` → monthly seasonality (20 trading sessions/month)
- `period=5`  → weekly seasonality
- `robust=True` → important for Vietnam's volatile retail-driven market

### 2.2 Fourier Cycle Detection

The FFT-based cycle detector identifies hidden price cycles (e.g., 21-day, 63-day quarterly, 252-day annual). These cycles inform the forecast horizon alignment — if a dominant 21-day cycle exists, a 21-day custom forecast is far more reliable than an arbitrary 17 or 30-day horizon.

### 2.3 Hidden Markov Model (HMM) Regime Detection

**3 Hidden States:** Bear (μ<0, high σ), Range (μ≈0, low σ), Bull (μ>0, moderate σ)

The **transition matrix** is the key output — it tells us not just the current regime but the probability of transitioning to each next regime. This directly informs the forecast action:

| Current Regime | Next Regime (highest prob) | Algorithm Stance |
|:---|:---|:---|
| BEAR | BEAR | STRONG SELL / Stay out |
| BEAR | RANGE | Watch — potential reversal forming |
| RANGE | BULL | BUY — regime transition imminent |
| BULL | BULL | HOLD / Scale into position |
| BULL | RANGE | Reduce position |
| RANGE | BEAR | SELL / Short-sell (when available) |

---

## 🟩 3. MULTI-TIMEFRAME FORECASTING MODELS

### 3.1 SARIMA/SARIMAX (Statistical — Monthly/Weekly)

**Model Selection Logic:**
- `monthly` → `SARIMAX(p,d,q)(P,D,Q)[20]` + exogenous: VN-Index return, credit growth monthly
- `weekly`  → `SARIMAX(p,d,q)(P,D,Q)[5]`  + exogenous: weekly sector rotation, margin data
- Auto-ARIMA selects optimal (p,d,q) by minimizing AIC via stepwise search

**SARIMAX Equation (compact form):**
```
Φ_P(B^s) · φ_p(B) · ∇^d · ∇^D_s · y_t = Θ_Q(B^s) · θ_q(B) · ε_t + β·X_t
```

All code provided in Vietnamese section applies directly.

### 3.2 LSTM with Multi-Head Attention (Deep Learning — Custom N Days)

**Architecture Rationale:**
- `LSTM Layer 1` (128 units): captures short-term price momentum
- `LSTM Layer 2` (64 units): captures medium-term trends
- `Multi-Head Attention` (4 heads): identifies which historical sessions are most predictive of the forecast period — particularly important for T+2.5 dynamics where 13:00 sessions create lagged effects
- `Dense Output` (N×5): simultaneously predicts O, H, L, C, V for all N periods

**Custom Directional Loss** (critical for action labels):
```python
Loss = (1-α)·MSE + α·DirectionPenalty
```
This ensures the model optimizes for correct directional calls (up/down), not just price-level accuracy — which is what trading decisions require.

### 3.3 Facebook Prophet (Seasonality — Monthly)

Vietnam-specific seasonality configuration:
- **Tết (Lunar New Year):** Markets typically weaken 2 weeks before, surge 1-2 weeks after
- **30/4 – 2/9 holidays:** Reduced liquidity periods → lower volatility forecasts
- **Quarterly earnings season:** 63-day fourier component captures earnings anticipation
- **Monthly settlement T+2.5:** 20-session component captures settlement-driven volatility

### 3.4 Inverse-Error Weighted Ensemble

The ensemble combines all three model families using weights proportional to their recent walk-forward accuracy:

```
w_i = (1/RMSE_i) / Σ_j(1/RMSE_j)
```

This self-adapts: if SARIMA recently outperforms LSTM (common in trending markets), it automatically receives higher weight.

---

## 🟥 4. PREDICTIVE CANDLESTICK BUILDER

### 4.1 OHLCV Reconstruction from Forecast Close

The central insight: given a predicted Close price, historical Open-High-Low ratios are stable enough to reconstruct a realistic candle. The key formula:

```
Open   = prev_close × (1 + mean_gap%)   — gap between sessions
Body   = Close × mean_body_pct          — adjusted for regime
High   = max(O,C) × (1 + mean_upper_shadow%)
Low    = min(O,C) × (1 - mean_lower_shadow%)
Volume = avg_volume × regime_multiplier
```

Regime multipliers modulate the candle shape:
- **BULL_TREND:** longer bodies, smaller lower shadows → strong bullish candles
- **BEAR_TREND:** longer bodies downward, smaller upper shadows
- **RANGE:** shorter bodies, longer shadows on both sides (indecision candles)

### 4.2 Candlestick Pattern Classification

The `classify_candle_pattern()` function maps the reconstructed OHLC geometry to named patterns:

| Pattern | Body/Range | Shadow Configuration | Trading Signal |
|:---|:---:|:---|:---:|
| Bullish Marubozu | >90% | No shadows | STRONG BUY |
| Bearish Marubozu | >90% | No shadows | STRONG SELL |
| Hammer | <20% | Long lower shadow (>60%) | BUY (bottom reversal) |
| Shooting Star | <20% | Long upper shadow (>60%) | SELL (top reversal) |
| Doji | <5% | Any configuration | WATCH |
| Spinning Top | 10–30% | Moderate both sides | NEUTRAL |

---

## 🟪 5. CONFIDENCE SCORING AND POSITION SIZING

### 5.1 Composite Confidence Score

```
C_score = 0.30·ModelAgreement + 0.20·RegimeConfidence +
          0.15·PatternStrength + 0.25·HistoricalAccuracy - 0.10·HerdingIndex
```

Grade thresholds: A+ ≥80%, A ≥65%, B ≥50%, C ≥35%, D <35%

**Rule:** Only issue BUY/SELL recommendations when grade ≥ B (50%). Below B → always output HOLD regardless of signal score.

### 5.2 GARCH(1,1) Volatility Forecasting

The GARCH equation provides period-by-period volatility estimates:
```
σ²(t) = ω + α·ε²(t-1) + β·σ²(t-1)
```

**Practical use in candlestick output:**
- `σ(t) × 1.645` = 95% VaR → sets **Stop Loss** width for each candle
- `σ(t) × 2.326` = 99% VaR → marks "avoid trading" periods
- `persistence = α+β` → if >0.97, declare HIGH VOLATILITY REGIME → tighten Kelly fraction

---

## 🟦 6. TIMING OPTIMIZATION

### 6.1 Intra-Forecast Optimal Entry/Exit

The `find_optimal_timing()` function scans the predicted candle series and identifies:

**Optimal Entry Period:**
1. Candle direction = BULLISH
2. Confidence ≥ 55%
3. Predicted close not yet >2% above current price
4. Pattern signal = BUY or STRONG BUY
5. Not a high-volatility avoid-period (GARCH VaR > 2× median)

**Optimal Exit Period:**
1. First BEARISH candle after entry with confidence ≥ 55%, OR
2. Take-profit price reached: `TP = Entry × (1 + kelly_gain × win_prob)`, OR
3. Confidence drops below 40% (model uncertainty too high)

**T+2.5 Intraday Timing (when custom N_days ≤ 5):**
- Always flag 13:00 sessions of T+2 days
- Apply 1.25× signal amplification during 13:00–13:45 window if volume ratio > 1.3×

---

## 🟧 7. VALIDATION FRAMEWORK

### 7.1 Walk-Forward Metrics

All models are evaluated using walk-forward cross-validation to prevent look-ahead bias:

| Metric | Formula | Target |
|:---|:---|:---:|
| RMSE | √(mean((pred-true)²)) | Minimize |
| MAPE | mean(|pred-true|/true)×100 | < 3% |
| **Directional Accuracy (DA)** | mean(sign(Δpred)==sign(Δtrue)) | **> 58%** |
| Sharpe (fold returns) | mean/std×√252 | > 1.0 |

> **DA > 58% is the minimum threshold for deployment.** Below this, the model is no better than a coin flip for direction — the most critical metric for generating actionable trade signals.

---

## 📋 8. SUMMARY: FORMULA DEPENDENCY MAP

```
Forecast Close
      │
      ├── STL Decomposition → Trend + Seasonal + Residual
      │         └── Fourier → Dominant Cycles → SARIMA seasonal period s
      │
      ├── HMM Regime Detection → Bull/Bear/Range + transition probs
      │         └── ADX/DMI → regime confirmation
      │
      ├── Model Ensemble (SARIMA + LSTM + Prophet)
      │         ├── SARIMA: Φ_P(B^s)·φ_p(B)·∇^d·y_t = ...
      │         ├── LSTM:   seq→LSTM×2→Attention→Dense(N×5)
      │         └── Prophet: y(t) = g(t) + s(t) + h(t) + ε
      │
      ├── GARCH(1,1): σ²(t) = ω + α·ε²(t-1) + β·σ²(t-1)
      │         └── → Stop Loss = Close × (1 - 1.645×σ)
      │             → Take Profit = Close × (1 + kelly_gain×win_prob)
      │
      ├── Candle Builder: OHLCV from hist. ratios × regime multiplier
      │         └── Pattern Classifier → Marubozu/Hammer/Doji/...
      │
      ├── Confidence Score: C = 0.30·MA + 0.20·RC + 0.15·PS + 0.25·HA - 0.10·HI
      │         └── Grade A+ → STRONG BUY/SELL
      │             Grade B  → BUY/HOLD/SELL
      │             Grade C  → HOLD (override all signals)
      │
      ├── Kelly Criterion: f* = [-b ± √(b²-4ac)] / 2a
      │         └── Half-Kelly (F0 investors): position = f*/2
      │
      └── Timing Optimizer → Entry Period + Exit Period + Avoid Periods
```

---

## ⚠️ 9. LIMITATIONS AND RISK WARNINGS

### 9.1 Known Model Limitations

| Limitation | Impact | Mitigation |
|:---|:---|:---|
| SARIMA assumes stationarity | Misses structural breaks | ADF test + differencing; HMM detects regime changes |
| LSTM overfits on small N | Unreliable for N<5 | Minimum N=5; dropout=0.2; early stopping |
| Prophet ignores microstructure | Smooths intraday patterns | Only use for weekly/monthly forecasts |
| GARCH assumes constant distribution | Underestimates tail risk in crashes | Use skewed-t distribution; add 30% buffer to VaR |
| All models trained on past data | Cannot predict black swans | Half-Kelly, hard stop-loss, max 20% position |

### 9.2 Vietnam Market-Specific Caveats

- **Circuit breaker (±7%):** Price-limit rules can cause forecast gaps; clip all forecast returns to ±6.5% per day
- **80% retail composition:** Herding effects can override model signals for 3-5 consecutive sessions
- **T+2.5 settlement:** Afternoon session volatility spikes create intraday biases; apply 1.25× volatility scaling to 13:00–14:30 period
- **Thin liquidity (small caps):** GARCH models are unreliable for stocks with avg volume < 100,000 shares/day

---

> 🎓 **Academic Board Final Note:**  
> The most important formula in this entire system is not any single mathematical equation — it is the **Kelly Override Rule:**  
> *"If Kelly_Half ≤ 0, the recommendation is always HOLD, regardless of any other signal."*  
> Mathematical models generate signals. Kelly Criterion determines whether those signals have a positive expected value worth acting on. Without this gatekeeper, even a technically sound model can lead to capital destruction.

---

*Báo cáo này được soạn thảo bởi Hội đồng Học thuật Liên ngành.*  
*This report was prepared by the Interdisciplinary Academic Board.*  
*Ngày / Date: 22/03/2026 — Version 3.0 Technical Architecture*
