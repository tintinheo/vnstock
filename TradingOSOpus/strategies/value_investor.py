"""strategies/value_investor.py – 5M P/E, ROE, FTSE scoring strategy."""
from strategies.base import BaseStrategy, Signal

class ValueInvestorStrategy(BaseStrategy):
    name = "Value Investor"; horizon = "5M"
    def generate_signals(self, df, ticker="", pe_ratio=15, roe=0.12, eps_growth=0.0,
                         dividend_yield=0.0, is_ftse_candidate=False, **kwargs):
        score = 0
        if pe_ratio < 12: score += 2
        elif pe_ratio < 15: score += 1
        if roe > 0.15: score += 2
        elif roe > 0.10: score += 1
        if eps_growth > 0.15: score += 2
        if dividend_yield > 0.03: score += 1
        if is_ftse_candidate: score += 2
        conf = min(0.4 + score * 0.07, 0.95)
        if score >= 5:
            return [Signal(Signal.BUY, conf, f"Value score={score}/9 PE={pe_ratio} ROE={roe:.0%}", ticker, self.horizon)]
        elif score <= 1:
            return [Signal(Signal.SELL, 0.6, f"Weak fundamentals score={score}/9", ticker, self.horizon)]
        return [Signal(Signal.HOLD, 0.5, f"Moderate value score={score}/9", ticker, self.horizon)]