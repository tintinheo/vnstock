# T+2.5 Quantitative Trading Strategy and Advanced Technical Analysis Report for F0 Investors in the Vietnam Stock Market

## The Nature of Intraday Stock Prices and Modern Economic Theory in the Vietnamese Context

The dynamics of intraday stock prices in the Vietnamese market are not merely reflections of macroeconomic variables but the result of a specific market microstructure. Within the framework of traditional financial economics, Eugene Fama's Efficient Market Hypothesis (EMH) posits that prices always fully reflect all available information. However, empirical studies on the two primary exchanges, HOSE and HNX, indicate that the Vietnamese market aligns more closely with Andrew Lo's Adaptive Market Hypothesis (AMH). Under AMH, market efficiency is a dynamic variable that changes over time and depends on environmental conditions, such as the number of competitors, profit opportunities, and the adaptability of investors to market shocks.

In Vietnam, the nature of intraday prices is heavily dominated by the psychology of individual investors, commonly referred to as F0 investors, who account for over 90% of trading volume. The massive participation of this group creates irrational phenomena such as herding behavior, overconfidence, and overreactions to news. Instead of trading volume leading prices as in informed-trading models in developed markets, Vietnam often exhibits a reverse feedback mechanism where price changes trigger trading volume (momentum chasing). When prices rise, the FOMO effect drives investors to rush in; conversely, when prices fall, panic leads to widespread sell-offs.

Research on the high-frequency dynamics of the VN-Index using 1-minute data from 2022 to early 2025 shows that the intraday volatility pattern in Vietnam does not follow the traditional U-shape. Instead, it exhibits a modified U-shape with a massive volatility spike occurring between 13:00 and 14:00. This spike reflects delayed information assimilation and liquidity constraints typical of an emerging market.

To estimate intraday prices with the highest accuracy, utilizing Realized Volatility measures and Time-Varying Autoregressive (TV-AR) models is essential. Algorithms must calculate the dispersion of returns over small intervals to determine the expected trading range. The Realized Volatility (RV) formula is expressed as follows:

$$RV_t = \sqrt{\sum_{i=1}^{n} r_{i,t}^2}$$

Where $r_{i,t}$ is the logarithmic return at interval $i$ on day $t$.

Python

# 

`import pandas as pd
import numpy as np

def calculate_intraday_volatility(df_1min):
    """
    Calculates Realized Volatility based on 1-minute data.
    Used to estimate intraday price ranges for T+0 Scalping strategies.
    """
    df_1min['log_ret'] = np.log(df_1min['close'] / df_1min['close'].shift(1))
    # Sum of squared returns within the session
    realized_vol = np.sqrt(np.sum(df_1min['log_ret']**2))
    return realized_vol

def estimate_intra_session_targets(current_price, volatility_est):
    """
    Estimates the highest and lowest price targets within the session.
    """
    upper_target = current_price * (1 + volatility_est)
    lower_target = current_price * (1 - volatility_est)
    return upper_target, lower_target`

| **Characteristic** | **Efficient Market Hypothesis (EMH)** | **Adaptive Market Hypothesis (AMH) in VN** |
| --- | --- | --- |
| Information Reflection Speed | Instantaneous and accurate | Delayed due to liquidity constraints |
| Role of Historical Prices | No predictive value | Exhibits serial correlation (Autocorrelation) |
| Investor Behavior | Absolutely rational | Driven by herding behavior |
| Volatility Structure | U-shape (Open/Close) | Peak at 13:00 - 14:00 (T+2.5 effect) |

## Technical Analysis of T+2.5 Settlement Cycle Impact on Afternoon Price Volatility

The shortening of the settlement cycle from T+3 to T+2.5 since August 29, 2022, has created a significant turning point in the operational mechanism of the Vietnam stock market. According to the new regulations, shares and funds are credited to investor accounts at 11:30 AM on day T+2, granting them the right to execute sell orders starting in the afternoon session of the same day. While this increases capital turnover and improves liquidity, it also brings implications for price volatility that F0 investors must carefully note.

The technical impact of T+2.5 is concentrated primarily between 13:00 and 14:30. This is the period when potential supply from T+0 transactions is officially released into the market. Data analysis shows:

1. Immediate Supply Shock: If the market trend over the previous two days (T+0 and T+1) was negative, the T+2 afternoon session often witnesses strong sell-offs immediately upon reopening after the midday break. This is due to the fast stop-loss mentality of F0 investors seeking to protect capital once shares arrive.
2. Delayed Information Assimilation: Since the market rests from 11:30 to 13:00, economic information or global market movements during this time are compressed and react strongly at the start of the afternoon session. When combined with T+2.5 supply, volatility typically peaks at 13:00 - 13:15.
3. Liquidity Imbalance: Investors tend to wait for signals from the morning session and only act in the afternoon. This creates a large disparity in trading volume between the two sessions, making volume-based technical indicators (like OBV or VWAP) noisier unless adjusted for the T+2.5 cycle.

Detailed afternoon session impact table:

| **Timeframe** | **Technical State** | **Impact on Price** | **Recommendation for F0** |
| --- | --- | --- | --- |
| 13:00 - 13:15 | T+2.5 Supply Release | Maximum volatility, high slippage risk | Observe, avoid Market Orders (MP) |
| 13:15 - 14:00 | Supply Absorption | Price tends to form a clearer trend | Confirm trend using Volume (VSA) |
| 14:00 - 14:30 | Institutional Flow | More stable liquidity, less noise | Optimal time for decision making |
| 14:30 - 14:45 | Closing Auction (ATC) | Influenced by portfolio rebalancing | Beware of "push" orders at the end |

## Technical Proposal for Base Breakout and Pivot Detection

To trade successfully in a T+2.5 environment, identifying breakouts from accumulation bases is a core strategy. A valid base is defined when price moves within a narrow range on dry volume, indicating a balance between supply and demand.

The breakout detection algorithm must combine three factors: price breaks, volume confirmation, and pivot points. A Pivot point is usually the highest price of the accumulation base or a local resistance level where selling pressure is fully absorbed.

The Scaled Price formula to determine the relative position within the base:

$$ScaledPrice = \frac{Close - \text{RollingAvg}(Max, Min)}{Max - Min}$$

A $ScaledPrice$ value exceeding 0.5 is an initial signal of a breakout.

Python

# 

`def detect_base_and_pivot(df, window=20, vol_factor=1.5):
    """
    Detects accumulation bases and breakout pivot points.
    window: Period to consider for the base (typically 20-50 sessions).
    vol_factor: Volume spike factor to confirm the breakout.
    """
    df['rolling_max'] = df['high'].rolling(window=window).max()
    df['rolling_min'] = df['low'].rolling(window=window).min()
    df['base_width'] = (df['rolling_max'] - df['rolling_min']) / df['rolling_min']
    
    # Calculate Scaled Price (Carver's Breakout Indicator)
    df['mid_point'] = (df['rolling_max'] + df['rolling_min']) / 2
    df['scaled_price'] = (df['close'] - df['mid_point']) / (df['rolling_max'] - df['rolling_min'])
    
    # Identify Pivot Point (highest in the window)
    df['pivot_point'] = df['high'].rolling(window=window).max().shift(1)
    
    # Breakout signal: Price > Pivot + high volume + tight base (<10% width)
    df['is_breakout'] = (df['close'] > df['pivot_point']) & \
                        (df['volume'] > df['volume'].rolling(window=20).mean() * vol_factor) & \
                        (df['base_width'] < 0.10)
    return df`

## Detecting Pump & Dump Fingerprints in the Vietnamese Market

In the Vietnam stock market, "Pump & Dump" schemes often occur in small-cap (Penny) stocks or stocks with low liquidity. "Sharks" or "market drivers" often use social media groups on Telegram and Facebook to spread false rumors, inflating stock prices irrationally before dumping their holdings.

Key technical signatures (fingerprints) of these schemes include:

1. Pump Phase: Prices hitting limit-up repeatedly on low initial volume, followed by a volume surge when F0 investors jump in due to FOMO.
2. Effort vs. Result Mismatch: Appearance of narrow-bodied candles on extremely high volume, indicating hidden distribution.
3. Noel Tree Pattern: After reaching a peak, the stock price hits limit-down continuously with "zero bid" liquidity, preventing investors from exiting.

To detect these risks early, we utilize the Upthrust signal from VSA (Volume Spread Analysis) and price-volume divergence.

Python

# 

`def detect_pump_and_dump_risk(df):
    """
    Identifies price manipulation risks via Upthrust and Volatility spikes.
    """
    # 1. Sudden volatility increase
    df['price_std'] = df['close'].pct_change().rolling(window=20).std()
    
    # 2. VSA Upthrust detection
    # Feature: New high but closes at low with ultra-high volume
    df['is_upthrust'] = (df['high'] > df['high'].shift(1)) & \
                        (df['close'] < (df['high'] + df['low'])/2) & \
                        (df['volume'] > df['volume'].rolling(window=20).mean() * 2)
    
    # 3. Negative Divergence between price and Accumulation/Distribution (A/D)
    hl = (df['high'] - df['low']).replace(0, np.nan)
    mfm = ((df['close'] - df['low']) - (df['high'] - df['close'])) / hl
    df['mfv'] = mfm.fillna(0.0) * df['volume']
    df['ad_line'] = df['mfv'].cumsum()
    
    # Warning if price rises but AD Line falls (Divergence)
    df['pump_warning'] = (df['close'] > df['close'].shift(5)) & (df['ad_line'] < df['ad_line'].shift(5))
    return df`

## Analyzing False Breakouts and Confirmation Techniques

One of the most common traps leading to losses for F0 investors is the "False Breakout" (Fakeout). This occurs when the price breaches an important resistance level but lacks the strength to sustain it, reversing back into the base and often resulting in a sharp decline.

The cause of a fakeout is often a lack of volume confirmation or "stop-hunt" activities by institutional investors seeking to sweep stop-loss orders from the short side before an actual reversal. To filter out these noisy signals, investors should apply a two-session confirmation rule or check for agreement between momentum indicators like RSI and MACD.

Criteria for a Real Breakout:

- Trading volume at the breakout must be at least 50-100% higher than the 20-session average.
- The closing price must be at or near the high of the candle (High Relative Close).
- Confirmation from larger timeframes (Multi-timeframe structure).

Python

# 

`def confirm_breakout_validity(df):
    """
    Confirms breakout validity to eliminate Fakeouts.
    """
    # Relative Close Location (RCL)
    df['rcl'] = (df['close'] - df['low']) / (df['high'] - df['low'])
    
    # Volume confirmation
    df['vol_check'] = df['volume'] > df['volume'].rolling(window=20).mean() * 1.5
    
    # RSI Divergence check
    df['rsi_div'] = (df['close'] > df['close'].rolling(20).max().shift(1)) & \
                    (df['rsi'] < df['rsi'].rolling(20).max().shift(1))
    
    # Real Breakout signal: High RCL + Vol check + No RSI Divergence
    df['valid_breakout'] = (df['rcl'] > 0.7) & df['vol_check'] & (~df['rsi_div'])
    return df`

## Candlestick & Momentum Analytics Adjusted for the VN-Index

In the context of the Vietnamese market with high volatility (+/- 7% on HOSE), traditional candlestick patterns and momentum thresholds require recalibration. For instance, RSI often reaches an overbought state at thresholds of 75-80 rather than the standard 70 seen in more stable markets.

High-reliability patterns in Vietnam:

- Hammer at support zones: Has a reversal success rate of up to 72.1% for the VN30 group.
- Bullish/Bearish Engulfing: Particularly effective when the second candle's volume is double the first.
- No Supply Bar: A narrow-bodied candle, closing in the middle or low with ultra-low volume, indicating that selling pressure has dried up.

Python

# 

`def candlestick_momentum_analytics(df):
    """
    Analyzes candlestick patterns and momentum adjusted for the VN market.
    """
    # 1. Hammer Detection
    body = abs(df['close'] - df['open'])
    lower_shade = df[['open', 'close']].min(axis=1) - df['low']
    upper_shade = df['high'] - df[['open', 'close']].max(axis=1)
    df['is_hammer'] = (lower_shade > 2 * body) & (upper_shade < 0.1 * body)
    
    # 2. Adjusted RSI (75/25 thresholds)
    df['overbought_vn'] = df['rsi_vn'] > 75
    df['oversold_vn'] = df['rsi_vn'] < 25
    
    # 3. No Supply Bar (VSA)
    df['no_supply'] = (df['close'] < df['close'].shift(1)) & \
                      (abs(df['high'] - df['low']) < df['high'].rolling(20).std()) & \
                      (df['volume'] < df['volume'].shift(1))
    return df`

## Multi-Factor Scoring (Scoring) and T+ Cycle Optimization

To assist F0 investors in making objective decisions, we propose the VN-4 Multi-Factor Model. This model is based on research into anomalous factors in Vietnam, where Size effects and Earnings-to-Price (EP) ratios play a more decisive role than Book-to-Market indicators.

The Scoring Model includes:

1. Market Factor (Beta): Sensitivity relative to the VN-Index.
2. Size Factor: Preference for high-growth small and mid-cap stocks.
3. Value Factor (EP): Based on the earnings yield.
4. Turnover Factor: This is a market-specific factor. In Vietnam, excessively high turnover is often associated with over-speculation and subsequent price declines. Thus, this factor is weighted negatively.

$$Score_i = w_1 \cdot Z(Quality) + w_2 \cdot Z(Value) + w_3 \cdot Z(Momentum) - w_4 \cdot Z(Turnover)$$

Python

# 

`def calculate_vn4_score(df_metrics):
    """
    VN-4 Scoring system optimized for retail investors in Vietnam.
    Weights are calibrated to prioritize safety and liquidity.
    """
    from scipy.stats import zscore
    
    # Data standardization
    df_metrics['z_ep'] = zscore(df_metrics['ep_ratio'].fillna(0))
    df_metrics['z_roe'] = zscore(df_metrics['roe'].fillna(0))
    df_metrics['z_mom'] = zscore(df_metrics['momentum_6m'].fillna(0))
    df_metrics['z_turnover'] = zscore(df_metrics['turnover_12m'].fillna(0))
    
    # Composite score calculation (Negative weight on Turnover to avoid 'junk' stocks)
    df_metrics['final_score'] = (0.3 * df_metrics['z_ep'] + 
                                0.3 * df_metrics['z_roe'] + 
                                0.3 * df_metrics['z_mom'] - 
                                0.1 * df_metrics['z_turnover'])
    return df_metrics`

## Trading Action Recommendations and Optimal Exit Strategies

Based on technical analysis and T+2.5 cycle specifics, the Academic Board proposes specific action strategies for various holding periods, suited to different F0 risk profiles.

### T+3 Strategy: Momentum Scalping

Focuses on capturing short-term breakouts. Investors buy on T+0 morning when price clears a Pivot point on high confirmation volume.

- Buy Point: Price > Pivot + 2% and volume > 50% of 20-session average within the first hour.
- Sell Point: Exit entirely or partially in the T+2 afternoon session to lock in quick gains (Target: 5-7%).
- Risk Management: Stop loss immediately if price closes below the Pivot on day T+0 or T+1 (-3%).

### T+5 Strategy: Sector Trend Trading

Investors capitalize on sectoral capital rotations (e.g., Banking, Securities, Steel).

- Buy Point: When the sector leader triggers a Base Breakout.
- Sell Point: After 5 sessions when RSI touches 75 or an Upthrust candle appears.
- Risk Management: Maximum stop-loss threshold at -5%.

### T+7 and T+10 Strategies: Short-term Cycle Investment

Designed for VN30 stocks or Midcaps with strong fundamentals.

- Buy Point: Accumulate at support levels or on No Supply candles during corrections within an uptrend.
- Sell Point: Take profits at 10-15% or when price breaks the MA20 moving average.
- Exit Tactic: Utilize the "Counter-trend Exit" - sell during strong upward sessions with high liquidity to minimize slippage losses.

| **Cycle** | **Profit Target** | **Stop-Loss** | **Allocation (%)** | **Primary Tools** |
| --- | --- | --- | --- | --- |
| **T+3** | 5% - 7% | -3% | 20% | Pivot, VSA, T+2.5 Volume |
| **T+5** | 8% - 10% | -5% | 30% | RSI (75/25), Sector Rotation |
| **T+7** | 10% - 12% | -6% | 25% | MA20, Volume Patterns |
| **T+10** | > 15% | -8% | 25% | VN-4 Scoring, MACD |

## Conclusion and Implementation Roadmap for F0 Investors

Participating in the Vietnam stock market in the T+2.5 era requires F0 investors to possess not only technical knowledge but also a deep understanding of behavioral psychology and domestic capital flow structures. The proposed algorithmic system and screening criteria aim to eliminate emotional factors—the greatest enemy of new investors.

For application implementation, we recommend direct integration with SSI's Fast Connect API to ensure data inputs are accurate and real-time. The process involves registering an API Key on iBoard, setting up a Data Scanner based on the provided Python formulas, and finally executing trades via FC Trading. Investors must always remember that in a highly adaptive market like Vietnam, stop-loss discipline and cash/stock ratio management are the only keys to survival and sustainable growth.