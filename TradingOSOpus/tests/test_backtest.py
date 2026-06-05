"""tests/test_backtest.py – Test backtesting engine."""
from backtest.engine import BacktestEngine
from backtest.metrics import calculate_metrics
import pandas as pd, numpy as np

def test_backtest_runs(sample_ohlcv):
    r = BacktestEngine().run(sample_ohlcv, ticker="T", strategy_key="1W")
    assert "metrics" in r and "trades" in r

def test_metrics():
    eq = pd.Series(np.linspace(1e8, 1.2e8, 252))
    m = calculate_metrics(eq, [{"pnl":1e6},{"pnl":-5e5},{"pnl":8e5}])
    assert m["total_return_pct"] > 0 and m["sharpe_ratio"] > 0
