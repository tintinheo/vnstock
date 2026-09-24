"""strategies/cycle_trader.py – 3M Macro regime + Fundamentals strategy."""
from strategies.base import BaseStrategy, Signal

class CycleTraderStrategy(BaseStrategy):
    name = "Cycle Trader"; horizon = "3M"
    def generate_signals(self, df, ticker="", macro_regime="neutral", pe_ratio=15, eps_growth=0.0, **kwargs):
        signals = []; score = 0
        if macro_regime == "expansion": score += 2
        elif macro_regime == "contraction": score -= 2
        if pe_ratio < 12: score += 1
        elif pe_ratio > 20: score -= 1
        if eps_growth > 0.15: score += 2
        elif eps_growth < 0: score -= 1
        if score >= 3:
            signals.append(Signal(Signal.BUY, min(0.5 + score * 0.1, 0.95),
                f"Macro={macro_regime}, PE={pe_ratio:.1f}, EPS_g={eps_growth:.0%}", ticker, self.horizon))
        elif score <= -2:
            signals.append(Signal(Signal.SELL, min(0.5 + abs(score) * 0.1, 0.9),
                f"Macro={macro_regime}, PE={pe_ratio:.1f}, EPS_g={eps_growth:.0%}", ticker, self.horizon))
        else:
            signals.append(Signal(Signal.HOLD, 0.5, f"Score={score}, mixed signals", ticker, self.horizon))
        return signals