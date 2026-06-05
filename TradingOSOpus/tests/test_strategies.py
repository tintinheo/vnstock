"""tests/test_strategies.py – Test all 5 strategies."""
from strategies.weekly_momentum import WeeklyMomentumStrategy
from strategies.swing_trader import SwingTraderStrategy
from strategies.position_trader import PositionTraderStrategy
from strategies.cycle_trader import CycleTraderStrategy
from strategies.value_investor import ValueInvestorStrategy
from strategies.engine import StrategyEngine
from strategies.base import Signal

def test_weekly(sample_ohlcv):
    sigs = WeeklyMomentumStrategy().generate_signals(sample_ohlcv, ticker="T")
    assert all(isinstance(s, Signal) for s in sigs)

def test_swing(sample_ohlcv):
    assert len(SwingTraderStrategy().generate_signals(sample_ohlcv, ticker="T")) >= 1

def test_position(sample_ohlcv):
    assert len(PositionTraderStrategy().generate_signals(sample_ohlcv, ticker="T", ml_prediction=0.7)) >= 1

def test_value(sample_ohlcv):
    sigs = ValueInvestorStrategy().generate_signals(sample_ohlcv, ticker="T", pe_ratio=10, roe=0.18, eps_growth=0.20, is_ftse_candidate=True)
    assert sigs[0].action == Signal.BUY

def test_engine(sample_ohlcv):
    d = StrategyEngine().run(sample_ohlcv, ticker="FPT")
    assert "consensus" in d and len(d["strategies"]) == 5
