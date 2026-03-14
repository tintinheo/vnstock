# Fix Stock Profiler Tab — DNSE Integration & Recommendation Engine
## Problem Statement
The 🧬 Stock Profile & Deep Analysis tab produces no recommendations because:
1. **DNSE endpoint is dead**: Code uses `services.entrade.com.vn` which returns empty data. The working endpoint is `api.dnse.com.vn/chart-api/v2/ohlcs/stock` (confirmed with 247 rows for FCN)
2. **TCBS tcanalysis API is down**: All 4 endpoints (overview, income, balance, ratios) return 404
3. **VNDirect API times out**: `finfo-api.vndirect.com.vn` connection refused
4. **No fallback**: When TCBS+VNDirect both fail, the profiler shows "No data" with default risk scores (all 5/5), producing a meaningless HOLD recommendation
## Current State
* `_fetch_dnse()` at line 472: uses dead `services.entrade.com.vn`, resolution `D`
* `fetch_tcbs_overview/financials/ratio()` at lines 2291-2356: All return empty (404)
* `render_stock_profiler_tab()` at line 2694: Falls through to VNDirect which also fails
* Recommendation tab S6 (line 3232): Displays default scores with no real data
## Proposed Changes
### 1. Fix DNSE endpoint (line 482)
Change `services.entrade.com.vn` → `api.dnse.com.vn` and resolution `D` → `1D`. This fixes the entire data pipeline (Scanner, Backtest, ML, etc.) since DNSE is P1.
### 2. Add DNSE OHLC-based technical analysis for profiler
Add a new function `fetch_dnse_ohlc_analysis(ticker)` that:
* Fetches 3 years of OHLC from the working DNSE API
* Computes key technical indicators (RSI, MACD, Bollinger, ADX, SMA trends)
* Derives price trends, support/resistance levels, momentum signals
* Returns a structured dict used by the recommendation engine
### 3. Enhance recommendation engine with DNSE data
Modify `render_stock_profiler_tab()` to:
* Call `fetch_dnse_ohlc_analysis(ticker)` as the primary data source when TCBS/VNDirect fail
* Use OHLC data to derive: current price, price change %, 52-week range, volume trends
* Compute technical-analysis-based risk scores when fundamental data is unavailable
* Generate meaningful BUY/HOLD/SELL recommendations based on technical signals
### 4. Add DNSE-powered valuation fallback
When TCBS ratios are empty, estimate EPS/P/E from OHLC price action:
* Use sector average P/E to back-calculate implied EPS
* Use 52-week high/low for P/B range estimation
* Weight technical signals more heavily when fundamentals are unavailable
### 5. Enhance recommendation rationale
Add DNSE OHLC-derived insights to the investment thesis:
* Price trend analysis (SMA20/50/200 crossovers)
* RSI regime (oversold/neutral/overbought)
* Volume momentum (accumulation vs distribution)
* Bollinger Band position and squeeze detection
* MACD momentum direction
## Files Modified
* `quant_app_v13.py` — All changes in this single file
