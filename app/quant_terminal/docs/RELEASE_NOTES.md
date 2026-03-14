# Release Notes — Captain Seventh Quant Terminal

**Project:** Captain Seventh Quant Terminal  
**Document ID:** QT-RN-001  
**Classification:** Internal  

---

## Version History

| Version | Date | Type | Author | Status |
|---------|------|------|--------|--------|
| 1.0.0 | 2026-03-14 | Initial Release | TheCaptain7th | ✅ Released |
| 0.9.0 | 2026-03-13 | Pre-release / Bug Fix Sprint | TheCaptain7th | Superseded |
| 0.1.0 | 2026-03-08 | Alpha / Prototype | TheCaptain7th | Superseded |

---

## v1.0.0 — Full Portfolio Dashboard Release

**Release Date:** 2026-03-14  
**Release Type:** Feature Release (Sprint 1 Completion)  
**Smoke Test Result:** 10/10 passed ✅  
**Breaking Changes:** None  
**Migration Required:** Clear `.cache/` directory after upgrading from v0.9.x

---

### Summary

v1.0.0 completes the Portfolio Intelligence layer of the Quant Terminal. The primary milestone is the integration of **SSI iBoard as live primary data source** (zero dependency on vnstock for real-time data), combined with a full Risk Dashboard (VaR, CVaR, correlation, Kelly), automated Signal Digest, visual P&L Heat Map, and configurable Auto-Refresh engine.

All 6 previously identified bugs are resolved. All 8 business requirements from BRD v1.0 are satisfied.

---

### New Features

#### F-01 — SSI iBoard Direct Data Pipeline
**Module:** `modules/ssi_fetcher.py` (new)  
**BRD:** BR-07

A standalone HTTP client for SSI iBoard's public REST APIs — zero dependency on `vnstock` for primary data.

**Three-endpoint OHLCV waterfall:**
1. `iboard-api.ssi.com.vn/statistics/charts/history` (primary, TradingView UDF format)
2. `iboard-query.ssi.com.vn/stock/ohlc` (secondary)
3. `fc-data.ssi.com.vn/api/v2/stock/ohlc` (tertiary)

**Real-time quote:** `iboard-query.ssi.com.vn/stock/{symbol}?boardId=MAIN`  
**Connectivity check:** `check_connectivity()` — liveness probe with latency measurement  
**Price normalization:** Auto-detects raw VND (> 500) vs thousands-VND scale and normalizes  
**Response parser:** Handles all 3 SSI response shapes (UDF arrays, nested dict, list-of-dicts)

---

#### F-02 — Auto-Refresh Engine
**Module:** `app.py` — Sidebar + bottom engine  
**BRD:** BR-01

Configurable live price polling with visual countdown:
- **Toggle:** Enable/disable auto-refresh independently
- **Intervals:** 30s / 60s / 120s / 300s (user-selectable)
- **Countdown bar:** Animated progress bar in sidebar shows seconds until next refresh
- **Engine:** `st.rerun()` loop; fires `refresh_quotes()` → SSI iBoard on each interval tick
- **Ticks every second** when auto-refresh is on to keep countdown smooth

---

#### F-03 — P&L Attribution Chart
**Module:** `app.py` — Tab 1 (Danh Mục)  
**BRD:** BR-01, BR-06

Horizontal bar chart ranked by P&L contribution (best to worst):
- Green bars = profitable positions, red = losing
- P&L in absolute VND per position
- Updates automatically on each quote refresh

---

#### F-04 — Portfolio Heat Map (Treemap)
**Module:** `app.py` — Tab 1 (Danh Mục)  
**BRD:** BR-01

Plotly Treemap where:
- **Cell size** = portfolio weight (%)
- **Cell color** = P&L% on a red → grey → green diverging scale
- Hover shows symbol, weight, P&L
- Updates on each quote refresh

---

#### F-05 — Signal Digest Table
**Module:** `app.py` — Tab 1 (Danh Mục)  
**BRD:** BR-02, BR-08

Pre-market briefing table showing for every portfolio position:

| Column | Source |
|--------|--------|
| Mã | Portfolio |
| Giá TT | SSI live quote |
| P&L (%) | Portfolio vs cost |
| RSI | 14-period, last bar |
| MACD Hist | MACD(12,26,9) histogram |
| Score | Composite −100 to +100 |
| Tín hiệu | Label (Mua mạnh / Trung tính / Bán) |
| Hành động | Blended recommendation |

Action logic blends signal score with position P&L:
- Score ≥ 40 → Tích lũy thêm
- Score ≥ 10 → Giữ
- P&L > 8% AND score < 0 → Chốt lời
- Score ≤ −40 OR P&L < −5% → Cắt lỗ / Thoát
- Score ≤ −10 → Giảm tỷ trọng
- Otherwise → Trung tính

**Top Pick / Watch alerts** highlighted below the table.  
**Cache TTL:** 5 minutes per symbol.

---

#### F-06 — Risk Dashboard (New Tab ⚡ Rủi Ro)
**Module:** `app.py` — Tab 5; `modules/analysis.py`  
**BRD:** BR-04, BR-05

##### Section A — VaR Table

New `compute_var(returns, confidence=0.95)` function in `analysis.py`:
- **Historical VaR** at 95% confidence (one-day horizon)
- **CVaR / Expected Shortfall**: average loss in the worst 5% of days
- Uses `dropna()` on daily returns; minimum 20 observations required

Per-position columns: Tỷ trọng, VaR 1D (%), CVaR 1D (%), P&L vs Vốn, DD hiện tại

**Portfolio-level KPIs:**
- Weighted Portfolio VaR (conservative — no diversification discount)
- Riskiest position (lowest VaR)
- **HHI Concentration Index**: sum of squared weights × 100; thresholds: < 20 = diverse, 20–40 = moderate, > 40 = concentrated
- Average P&L vs cost

**Color-coded:** VaR < −3% = red, VaR −1% to −3% = amber, V > 5% P&L = green

**VaR bar chart** per symbol (color-coded by risk level)

##### Section B — Correlation Matrix

Plotly Heatmap (−1 blue → 0 white → +1 red) for all portfolio symbols with ≥ 1yr return history.

**Diversification verdict:**
- avg corr > 0.7 → ⚠️ High concentration — alert-danger
- avg corr > 0.4 → 🔶 Moderate — alert-warn
- avg corr ≤ 0.4 → ✅ Well diversified — alert-ok

**Cache TTL:** 1 hour (returns matrix computation is expensive).

##### Section C — Kelly Criterion Sizing Table

Per-symbol statistics derived from historical daily returns:

| Column | Formula |
|--------|---------|
| Win Rate | % days with positive return |
| Avg Win | Mean of positive daily returns |
| Avg Loss | Mean absolute value of negative returns |
| Payoff (B) | Avg Win / Avg Loss |
| Full Kelly | f* = (b·p − q) / b, capped at 50% |
| ½ Kelly (rec) | Full Kelly × 0.5 (conservative) |
| % Hiện tại | Current portfolio weight |
| Điều chỉnh | ✅ OK / ⬆ Tăng / ⬇ Giảm |

---

### Bug Fixes

| ID | Severity | Component | Description | Fix |
|----|----------|-----------|-------------|-----|
| BUG-01 | Critical | `modules/analysis.py` | MACD histogram and signal columns swapped in pandas_ta path (`iloc[:,1]` = hist, `iloc[:,2]` = signal) | Corrected `iloc` indices |
| BUG-02 | Critical | `modules/analysis.py` | Bollinger upper/lower columns swapped in pandas_ta path (`iloc[:,0]` = BBL, `iloc[:,2]` = BBU) | Corrected `iloc` indices |
| BUG-03 | Critical | `modules/portfolio.py` | `cost_value` column never matched in SSI Excel parser; all positions showed zero cost | Fixed regex with OR conditions: `"giá trị vốn"`, `"cost value"`, `"giá trị cp" AND "vốn"` |
| BUG-04 | High | `app.py` | `st.stop()` inside tab blocks killed ALL subsequent tabs, making tabs 3–4 invisible when a symbol was not selected | Removed both `st.stop()` calls; replaced with conditional rendering |
| BUG-05 | High | `modules/scenarios.py` | Order P&L estimated as `(target - cost) * qty // qty` always returned 0 due to integer division | Replaced with `(target - cost_price) * partial_qty` (no integer division) |
| BUG-06 | Medium | `app.py` | `import json` repeated inline in 3 places causing re-import overhead | Moved to module top level |
| BUG-07 | High | `config.py` | `DATA_SOURCE = "SSI"` — invalid vnstock source, crashed every data fetch | Changed to `"VCI"` (SSI iBoard now used directly) |
| BUG-08 | High | `modules/data_fetcher.py` | `df.to_dict()` on `DatetimeIndex` produced `Timestamp` keys → `json.dump` `TypeError` | Rewrote cache to `records` format: `reset_index().to_dict(orient="records")` with matching restore |
| BUG-09 | Medium | `modules/analysis.py` | `find_support_resistance` used `.round(-2)` (nearest 100 VND) on thousands-VND prices → always 0 | Changed to `.round(2)` (2 decimal places) |
| BUG-10 | Medium | `config.py` / `modules/scenarios.py` | `HOSE_TICK = 100` (raw VND) with `round(price/tick)*tick` computed in raw VND; all tick-rounded prices were 0 in thousands-VND scale | `HOSE_TICK = 0.05` (50 VND in thousands scale); `round_to_tick` returns 2 decimal places |
| BUG-11 | Low | `app.py` | `df.applymap()` deprecated in pandas 2.x | Replaced with `df.map()` |

---

### Architecture Changes

#### New Module: `modules/ssi_fetcher.py`

```
modules/
├── analysis.py         (modified: compute_var added, S/R rounding fixed, MACD/BB fixed)
├── data_fetcher.py     (modified: SSI primary, records cache, fallback waterfall)
├── portfolio.py        (modified: cost_value regex fixed)
├── scenarios.py        (modified: round_to_tick fixed, order P&L fixed)
└── ssi_fetcher.py      ← NEW: direct SSI iBoard REST client
```

#### Data Flow (v1.0.0)

```
SSI iBoard API (3 endpoints)
        ↓ fetch_history() / fetch_quote()
    ssi_fetcher.py
        ↓ (on failure)
    data_fetcher.py → vnstock [VCI → TCBS → KBS → mock]
        ↓
    JSON cache (~/.cache/)
        ↓ (TTL: quotes 30s, history 1hr)
    app.py [Streamlit UI]
        ↓
    analysis.py [indicators + VaR]     scenarios.py [Bull/Base/Bear]
        ↓                                        ↓
    Tab 1 (Digest, Heatmap)          Tab 2 (Stock Analysis)
    Tab 5 (Risk Dashboard)
```

---

### Test Coverage

**File:** `test_smoke.py`  
**Run command:** `PYTHONIOENCODING=utf-8 python test_smoke.py`

| Test | Description | Result |
|------|-------------|--------|
| [01] | All imports OK | ✅ |
| [02] | `get_history` TCH: 50+ rows, correct price scale | ✅ |
| [03] | BB sanity: upper > lower | ✅ |
| [04] | MACD histogram = MACD − Signal | ✅ |
| [05] | Signal score CII in [−100, +100] | ✅ |
| [06] | Scenarios TCH: bull_target > stop_loss, R:R > 0, P&Ls non-zero | ✅ |
| [07] | T+2 settlement logic correct | ✅ |
| [08] | LO builder: price, fee, 7+ steps | ✅ |
| [09] | S/R resistance above current price HPG | ✅ |
| [10] | Quote HPG: price > 0, source = SSI-iboard | ✅ |

---

### Known Limitations (v1.0.0)

| ID | Limitation | Planned Resolution |
|----|-----------|-------------------|
| L-01 | Quote polling latency ~15–30s; not true real-time | WebSocket integration (v2.0 backlog) |
| L-02 | Backtesting engine not yet implemented | Sprint 2 |
| L-03 | Automated trade alerts (Telegram/email) not available | Sprint 3 |
| L-04 | VaR assumes i.i.d. returns (fat tails not modelled) | Monte Carlo / GARCH (Sprint 3) |
| L-05 | Sector rotation dashboard not implemented | Sprint 2 |
| L-06 | Auto-refresh `time.sleep(1)` tick may slow UI on < 4GB RAM machines | Optimize in v1.1 |

---

### Upgrade Instructions

#### From v0.9.x

```bash
# 1. Clear stale cache (format changed to records-based)
Remove-Item -Recurse -Force "$HOME\Documents\quant_terminal\.cache\*"

# 2. Pull latest app files
# (or copy app.py, config.py, modules/ from release archive)

# 3. Confirm all tests pass
cd quant_terminal
$env:PYTHONIOENCODING = "utf-8"
python test_smoke.py
```

#### Fresh Install

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
streamlit run app.py
```

---

### Dependencies (requirements.txt)

```
streamlit>=1.30
pandas>=2.0
numpy>=1.26
plotly>=5.18
pandas-ta>=0.3.14b
scipy>=1.11
openpyxl>=3.1
requests>=2.31
vnstock>=3.4
```

---

*Release approved by: TheCaptain7th (Product Owner) · 2026-03-14*  
*Next planned release: v1.1 — Backtesting Engine + Automated Alerts*
