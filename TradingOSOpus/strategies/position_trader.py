"""strategies/position_trader.py – 1M ML Ensemble + Golden Cross strategy."""
from strategies.base import BaseStrategy, Signal
from features.technical import sma

class PositionTraderStrategy(BaseStrategy):
    name = "Position Trader"; horizon = "1M"
    def generate_signals(self, df, ticker="", ml_prediction=0.5, **kwargs):
        sma50 = sma(df["close"], 50); sma100 = sma(df["close"], 100)
        golden = sma50.iloc[-1] > sma100.iloc[-1]
        signals = []
        if ml_prediction > 0.6 and golden:
            signals.append(Signal(Signal.BUY, round(ml_prediction, 2),
                f"ML pred={ml_prediction:.2f} + Golden Cross", ticker, self.horizon))
        elif ml_prediction < 0.4 and not golden:
            signals.append(Signal(Signal.SELL, round(1 - ml_prediction, 2),
                f"ML pred={ml_prediction:.2f} + Death Cross", ticker, self.horizon))
        else:
            signals.append(Signal(Signal.HOLD, 0.5, f"ML={ml_prediction:.2f}, GC={'Y' if golden else 'N'}", ticker, self.horizon))
        return signals