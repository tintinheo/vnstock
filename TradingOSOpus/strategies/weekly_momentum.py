"""strategies/weekly_momentum.py – 1W RSI + MACD + Volume strategy."""
from strategies.base import BaseStrategy, Signal
from features.technical import rsi, macd, volume_ratio

class WeeklyMomentumStrategy(BaseStrategy):
    name = "Weekly Momentum"; horizon = "1W"
    def generate_signals(self, df, ticker="", **kwargs):
        r = rsi(df["close"]); m = macd(df["close"]); vr = volume_ratio(df)
        last_rsi = r.iloc[-1]; last_macd = m["macd_histogram"].iloc[-1]; last_vr = vr.iloc[-1]
        signals = []
        if last_rsi < 30 and last_macd > 0 and last_vr > 1.5:
            signals.append(Signal(Signal.BUY, 0.8, f"RSI={last_rsi:.0f}<30 + MACD bullish + Vol spike", ticker, self.horizon))
        elif last_rsi > 70 and last_macd < 0:
            signals.append(Signal(Signal.SELL, 0.75, f"RSI={last_rsi:.0f}>70 + MACD bearish", ticker, self.horizon))
        else:
            conf = 0.5 + (0.3 if last_macd > 0 else -0.1) + (0.1 if last_rsi < 50 else -0.1)
            action = Signal.BUY if conf > 0.5 else (Signal.SELL if conf < 0.35 else Signal.HOLD)
            signals.append(Signal(action, round(min(max(conf, 0.1), 0.95), 2),
                f"RSI={last_rsi:.0f}, MACD={'+'if last_macd>0 else '-'}, Vol={last_vr:.1f}x", ticker, self.horizon))
        return signals