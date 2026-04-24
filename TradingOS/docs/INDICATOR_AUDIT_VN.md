# Indicator Audit For VN Market

This note audits the main indicators used by TradingOS from a Vietnam-market perspective.
The goal is not to remove classic indicators blindly, but to classify which ones should be:

- primary decision signals
- secondary confirmation signals
- context or risk controls only
- reduced or avoided when used standalone

## Primary Signals To Keep

| Indicator | Current Role In App | Why It Fits VN Better |
|---|---|---|
| MFPM composite | Main action engine | Already aggregates regime, money flow, AMF, pattern, and risk into one decision instead of trusting one noisy signal. |
| SMS / M-CVD | Smart money detection | Captures persistent accumulation-distribution better than raw momentum in markets often driven by domestic operators. |
| Put-through flow | Institutional flow proxy | In Vietnam, block deals often carry more meaning than raw foreign headline numbers, especially for bigger names. |
| AMF decision | Manipulation risk gate | Critical in a market where tape can look technically strong but still be structurally unsafe. |
| T+ verdict / T+ confidence | Execution timing layer | Better aligned with Vietnamese holding behavior and settlement rhythm than generic swing-trading heuristics. |
| Sector flow | Group rotation context | VN names frequently move by sector wave rather than by isolated single-stock discovery. |

## Secondary Signals To Keep But De-Emphasize

| Indicator | Current Role In App | Recommendation |
|---|---|---|
| Adaptive RSI | Context and regime-aware momentum read | Keep as confirmation only. Do not allow RSI alone to trigger BUY/EXIT. Current app already adapts thresholds by regime and sector. |
| HMM state | Market-regime context | Keep as regime filter. Useful for preventing counter-regime entries, but too abstract to be a standalone retail-facing trigger. |
| Pattern detection | Adds structure for Mode A/B | Keep, but only when confirmed by money flow and AMF. VN breakouts are vulnerable to false follow-through when volume is operator-driven. |
| Monte Carlo win probability | Probabilistic confidence | Keep as ranking aid only. Do not let it override weak money-flow or manipulation warnings. |

## Context Or Risk-Only Signals

| Indicator | Why It Is Noisy In VN | Recommendation |
|---|---|---|
| VWAP daily | Daily bars and auction effects can distort the reference, especially near close | Use for context, not trigger logic. |
| ATR | Useful for stop sizing, not direction | Keep for sizing and stop placement only. |
| Reward/Risk ratio | Can look attractive on paper with poor real fill quality | Keep as trade-planning metric, not idea-generation metric. |
| Confidence calibration | Good system-health check but lagging | Keep in Performance view, not trading signal generation. |

## Signals To Reduce Or Avoid As Standalone Triggers

| Indicator | Problem In VN Context | Recommendation |
|---|---|---|
| OBV slope | Easy to distort by concentrated sessions, block flow, or low free-float names | Reduce its interpretive weight; use only as supporting evidence inside broader flow logic. |
| Raw foreign net flow | Can be delayed, neutralized by local operator flow, or misleading in names dominated by domestic speculation | Never use alone; current app already downgrades missing FOL data to neutral. |
| Static RSI 70/30 reading | Too generic for a market with sector-specific speculation cycles | Avoid static thresholds; current app correctly uses adaptive thresholds. |
| Raw volume spike | Can reflect distribution or engineered breakout equally | Require AMF, M-CVD, and pattern confirmation before acting. |

## What TradingOS Already Does Well

- Uses adaptive RSI by regime and sector rather than a fixed 70/30 model.
- Separates proxy whale flow from put-through-enhanced flow.
- Treats missing foreign flow and missing PT flow as neutral instead of false-negative punishment.
- Uses AMF as a hard safety layer instead of letting a technically pretty chart override manipulation risk.
- Aligns scanner and profiler logic so the same ticker is less likely to receive contradictory decisions.

## Suggested Weighting Philosophy Going Forward

- Let MFPM, SMS/M-CVD, PT flow, AMF, and T+ verdict drive decisions.
- Let RSI, HMM, patterns, VWAP, and OBV explain or refine the setup.
- Let ATR, R:R, and calibration guide risk management, not entry conviction.

## Implemented Noise Retunes

- `mode_w_sms_gate` and `mode_w.sms_raw_gate` were raised from `60` to `65` to reduce false positives from proxy-flow names that look strong on ordinary rotation days.
- `whale.proxy_z_vol_min` was raised from `1.5` to `1.8` so moderate volume bursts are less likely to be labeled as whale activity in the VN market.
- The T+ engine now applies only a light `+0.5` T+2.5 confirmation boost instead of `+1.5`, because detector scores already encode much of the same momentum and volume information.

These changes intentionally avoid rewriting the scoring tree. They only tighten the noisiest overlap points while preserving the current app structure and test surface.

## Practical UI Interpretation Rule

When presenting signals to users, the app should communicate them in this order:

1. Safety and structural quality: AMF, distribution warning, sector flow
2. Money flow quality: SMS, M-CVD, PT flow, stealth accumulation
3. Tradeability: MFPM, T+ verdict, confidence, entry/SL/TP
4. Context only: RSI, OBV, VWAP, ATR, pattern labels