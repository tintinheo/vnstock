"""strategies/swing_trader.py – 2W SMA breakout + BB + Sentiment strategy."""
from strategies.base import BaseStrategy, Signal
from features.technical import sma, bollinger_bands

class SwingTraderStrategy(BaseStrategy):
    name = "Swing Trader"; horizon = "2W"
    def generate_signals(self, df, ticker="", sentiment_score=0.0, **kwargs):
        sma20 = sma(df["close"], 20); bb = bollinger_bands(df["close"])
        price = df["close"].iloc[-1]; sma_val = sma20.iloc[-1]
        bb_lower = bb["bb_lower"].iloc[-1]; bb_upper = bb["bb_upper"].iloc[-1]
        signals = []
        if price > sma_val and price < bb_lower * 1.02 and sentiment_score > -0.2:
            signals.append(Signal(Signal.BUY, 0.75, f"Price near BB lower + above SMA20 + sentiment OK", ticker, self.horizon))
        elif price < sma_val and price > bb_upper * 0.98:
            signals.append(Signal(Signal.SELL, 0.7, f"Price near BB upper + below SMA20", ticker, self.horizon))
        else:
            action = Signal.BUY if price > sma_val else Signal.HOLD
            signals.append(Signal(action, 0.5, f"Price {'>' if price>sma_val else '<'} SMA20", ticker, self.horizon))
        return signals