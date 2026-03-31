# Implementation Proposal: T+ Swing Trading Feature for F0 Investors

The Academic Board and Technology Management team present a detailed proposal for implementing an EOD (End-of-Day) scanning and T+3 Swing Trading recommendation system, specifically tailored for F0 investors in the Vietnam stock market.

## 1. Strategy and Market Context Analysis

As of 2026, the Vietnamese stock market is characterized by record liquidity and volatility, driven by the FTSE Emerging Market upgrade prospects.

- **Why T+3 Swing Trading for F0?**: Despite the T+2.5 settlement (shares arrive at 11:30-12:30 on T+2), F0 investors often suffer from "panic-selling" as soon as shares arrive due to afternoon liquidity pressure. A T+3 strategy filters out this noise, focusing on 3-5 day trends to optimize returns without requiring constant screen monitoring.
- **Objective**: Scan the entire universe (HOSE, HNX) at the end of each trading day to provide a "Watchlist" for the next day that satisfies technical breakout and fundamental stability criteria.

## 2. SDLC Process aligned with PMBOK & BABOK

We apply a **Hybrid V-Model and Agile** approach to ensure absolute precision and high verification standards.

- **Phase 1: Business Analysis (BABOK)**: Requirements elicitation using SSI historical data to identify market-specific "Breakout points" in Vietnam.
- **Phase 2: System Design**: Microservices architecture. The scanning module runs independently, connecting to SSI FastConnect API via REST and WebSocket for EOD and 30-minute interval data.
- **Phase 3: Development**: Built on Python with quantitative libraries (Pandas, Numpy). All logic is encapsulated into independent functions for modular maintenance.
- **Phase 4: Testing**: Comprehensive backtesting on at least 5 years of SSI data, focusing on Sharpe Ratio, Maximum Drawdown, and Win Rate.

## 3. Algorithm Logic

The system utilizes a hybrid of the **VN-4 Factor Model** (stock selection) and **PSO-Optimized Indicators** (market timing).

### Step 1: Stock Screening (VN-4 Model)

Filters out low-quality/illiquid stocks. Criteria include:

- Mid-to-Large Cap (Size factor).
- Attractive EP (Earnings-to-Price) ratios.
- Stable Turnover (avoiding hyper-speculative "penny" traps).

### Step 2: Signal Generation

Uses RSI and MACD with parameters dynamically optimized via Particle Swarm Optimization (PSO) to adapt to current market volatility.

---

## 4. Implementation Formulas & Code

Core modules for AI Agents to program the system.

### A. SSI FastConnect API Data Ingestion

Fetches EOD OHLCV data to trigger the scanning process.

Python

`import requests
import json

def get_ssi_eod_data(symbol, from_date, to_date, config):
    """
    symbol: Stock ticker (e.g., 'SSI', 'FPT')
    config: Contains ConsumerID, ConsumerSecret, AccessToken 
    """
    url = f"{config['url']}/api/v2/Market/SecuritiesChart"
    headers = {
        'Authorization': f"Bearer {config['access_token']}",
        'Content-Type': 'application/json'
    }
    payload = {
        "symbol": symbol,
        "from_date": from_date,
        "to_date": to_date,
        "resolution": "D" # Daily data for EOD scanning
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    return response.json()['data'] # Returns OHLCV list` 

### B. VN-4 Factor Calculation (Turnover Filter)

Uses the Turnover factor as a speculation risk filter.

Python

`import pandas as pd

def calculate_vn4_turnover_filter(df, window=252):
    """
    df: DataFrame with Volume and Shares_Outstanding
    window: 252 trading days (1 year)
    
    """
    # Calculate daily turnover ratio
    df['daily_turnover'] = df['Volume'] / df
    
    # Calculate 12-month average (VN-4 Factor)
    df['turnover_12m'] = df['daily_turnover'].rolling(window=window).mean()
    
    # VN-4 Rule: Excessively high turnover often predicts lower future returns
    # Filter for stocks within safe turnover ranges (e.g., < 75th percentile)
    threshold = df['turnover_12m'].quantile(0.75)
    return df[df['turnover_12m'] <= threshold]`

### C. Position Sizing (Kelly Criterion)

Optimizes capital allocation to protect F0 accounts.

Python

`def calculate_kelly_position(win_rate, win_loss_ratio, risk_free_rate=0.045):
    """
    win_rate (p): Win rate from backtest
    win_loss_ratio (b): Avg Win / Avg Loss
    
    """
    p = win_rate
    q = 1 - p
    b = win_loss_ratio
    
    # Kelly Formula: f* = (bp - q) / b
    f_star = (b * p - q) / b
    
    # Apply Fractional Kelly (Half-Kelly) for F0 to reduce volatility 
    recommended_size = max(0, f_star * 0.5) 
    return recommended_size`

## 5. Proposed Trading Plan for F0 Investors

The system will broadcast daily alerts at 20:00 (8:00 PM) with the following structure:

1. **Tickers**: Top 3-5 highest-conviction stocks.
2. **Rationale**: Fundamental (VN-4) + Technical (PSO Breakout).
3. **Execution Strategy**: Entry "Buy Zone" for tomorrow's morning session (T+0).
4. **T+3 Roadmap**:
    - **Profit Target**: Nearest resistance or ATR-based target.
    - **Stop-loss**: Support level or max 5-7% of position capital (2% total risk rule) .
    - **T+2 Management**: Assess momentum at 14:00. If the trend is strong, hold through T+3 or longer for trend following.

### 2. Quantitative Stock Scoring System

We propose a scoring model (0-100 points) that combines technical momentum with fundamental stability.

### A. Weighting Criteria

1. **Technical Momentum (40%):** PSO-optimized RSI/MACD and the 13:00 T+2.5 volume spike signal.
2. **Fundamental Health (40%):** ROE (>15%), EPS Growth, and healthy P/E ratios (10-15).
3. **Market Context (20%):** Asset turnover (VN-4 Model) and Herding behavior (CSAD index) to avoid overcrowded speculative trades.

### B. Implementation Code for Scoring Logic

Python

`def calculate_stock_score(tech_data, fund_data, context_data):
    """
    Implementation logic for EOD scanning
    """
    final_score = 0
    
    # 1. Technical Score (Max 40)
    if 30 < tech_data['rsi'] < 70: final_score += 10
    if tech_data['macd_signal'] == 'Bullish': final_score += 15
    if tech_data['vol_relative_to_avg'] > 1.5: final_score += 15
    
    # 2. Fundamental Score (Max 40)
    if fund_data['roe'] > 0.15: final_score += 15
    if fund_data['eps_growth'] > 0.10: final_score += 10
    if 10 < fund_data['pe'] < 15: final_score += 10
    if fund_data['debt_to_equity'] < 1.0: final_score += 5
    
    # 3. Liquidity & Sentiment Score (Max 20)
    # Neutralize Turnover to avoid overheated stocks [2]
    if context_data['turnover_percentile'] < 75: final_score += 10
    if context_data['csad_divergence'] > 0.01: final_score += 10
    
    return final_score

# F0 Strategy: 
# Score > 80: Priority Buy
# Score 60-80: Watchlist
# Score < 60: High Risk / Ignore`