PROPOSAL: CANDLESTICK PATTERN INTELLIGENCE & T+ TREND FORECASTING
As the Academic Board, we propose a technical framework for high-precision candlestick recognition and T+ trend forecasting, specifically optimized for the high-volatility Vietnamese retail market.

1. The Core Strategy: Morpho-Volume Integration
Our solution goes beyond basic pattern matching. It validates every candle shape against the VSA (Volume Spread Analysis) principles. A "Hammer" is only valid if it occurs on high volume at a support level, indicating professional accumulation during the 13:00 T+2.5 asset release.

2. Algorithmic Implementation (Python Snippets)
A. Vectorized Pattern Recognition
This module scans all 100+ tickers simultaneously using numpy for speed.

Python
# Identification of Engulfing Patterns (High conviction for T+3)
def detect_engulfing(df):
    """
    Bullish Engulfing: Candle 2 completely covers Candle 1
    """
    df['bullish_engulfing'] = (df['close'] > df['open'].shift(1)) & \
                              (df['open'] < df['close'].shift(1)) & \
                              (df['close'].shift(1) < df['open'].shift(1))
    return df
B. Dynamic Trend Alignment (The "Context" Filter)
Prevents F0 investors from "catching falling knives" by ensuring patterns align with the medium-term trend.

Python
def check_trend_alignment(df, window=20):
    # Calculate EMA Ribbon
    df['ema8'] = df['close'].ewm(span=8).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    
    # Trend is Bullish if EMA8 > EMA21
    df['trend_direction'] = np.where(df['ema8'] > df['ema21'], 1, -1)
    return df
3. Forecasting Logic for T+3 Recommendations
The AI Agent should prioritize signals where the Pattern Score and Volume Delta are both positive:

Strong Buy: Bullish Engulfing + Volume > 1.5x average + Upward Trend Alignment.

Stop-loss: Set at the low of the signal candle (approx. 2-3% risk).

