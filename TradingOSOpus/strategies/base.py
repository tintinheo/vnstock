"""strategies/base.py – Signal class and BaseStrategy ABC."""
from abc import ABC, abstractmethod

class Signal:
    BUY = "BUY"; SELL = "SELL"; HOLD = "HOLD"
    def __init__(self, action, confidence, reason, ticker="", horizon=""):
        self.action = action; self.confidence = confidence; self.reason = reason
        self.ticker = ticker; self.horizon = horizon
    def to_dict(self):
        return {"action": self.action, "confidence": self.confidence,
                "reason": self.reason, "ticker": self.ticker, "horizon": self.horizon}

class BaseStrategy(ABC):
    name = "BaseStrategy"; horizon = "N/A"
    @abstractmethod
    def generate_signals(self, df, **kwargs): pass