"""strategies/engine.py – Strategy orchestrator with STRATEGY_MAP."""
from strategies.weekly_momentum import WeeklyMomentumStrategy
from strategies.swing_trader import SwingTraderStrategy
from strategies.position_trader import PositionTraderStrategy
from strategies.cycle_trader import CycleTraderStrategy
from strategies.value_investor import ValueInvestorStrategy

# ═══ THIS IS THE KEY FIX ═══
STRATEGY_MAP = {
    "1W": WeeklyMomentumStrategy(),
    "2W": SwingTraderStrategy(),
    "1M": PositionTraderStrategy(),
    "3M": CycleTraderStrategy(),
    "5M": ValueInvestorStrategy(),
}

class StrategyEngine:
    def __init__(self):
        self.strategies = dict(STRATEGY_MAP)

    def run(self, df, ticker="", **kwargs):
        results = {}; buy_count = 0; sell_count = 0
        for key, strat in self.strategies.items():
            signals = strat.generate_signals(df, ticker=ticker, **kwargs)
            sig_dicts = [s.to_dict() for s in signals]
            for s in signals:
                if s.action == "BUY": buy_count += 1
                elif s.action == "SELL": sell_count += 1
            results[key] = {"name": strat.name, "horizon": strat.horizon, "signals": sig_dicts}
        consensus = "BUY" if buy_count > sell_count else ("SELL" if sell_count > buy_count else "HOLD")
        return {"ticker": ticker, "strategies": results, "buy_signals": buy_count,
                "sell_signals": sell_count, "consensus": consensus}