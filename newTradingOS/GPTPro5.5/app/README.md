# Vietnam Trading Real Data App with Recommendation Decision Engine

This package scans real Vietnam market snapshot data without using `vnstock`, accepts historical OHLCV CSV uploads, and includes a complete recommendation decision layer.

## Included

- Direct SSI iBoard-style snapshot adapter, no `vnstock`
- Realtime scanner
- Historical CSV ingestion
- Technical indicators
- Market regime
- Sector rotation
- Stock scoring
- Signal generation
- Recommendation Decision Engine
- Risk sizing
- Backtesting
- Streamlit UI

## Final recommendation outputs

The engine outputs:

```text
STRONG_BUY
BUY
WATCH
HOLD
REDUCE
SELL
AVOID
RISK_OFF
```

Each recommendation includes:

- Confidence
- Action
- Suggested position percentage
- Entry zone
- Stop loss
- Take profit levels
- Risk/reward
- Reasons
- Risks
- Invalidation conditions

## Run on Windows 11

```powershell
.\run_windows.bat
```

## Historical CSV schema

```text
symbol,date,open,high,low,close,volume,value,exchange,sector
```

## Disclaimer

Decision-support only. Not financial advice. Validate provider terms, data quality, slippage and backtest results before using real capital.
