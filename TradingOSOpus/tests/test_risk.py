"""tests/test_risk.py – Test risk management."""
from risk.position_sizing import atr_position_size, kelly_criterion
from risk.stop_loss import StopLossManager
from risk.portfolio import Portfolio

def test_atr_sizing():
    r = atr_position_size(5e8, 1500, 0.02)
    assert r["shares"] > 0 and r["risk_amount"] == 5e8*0.02

def test_kelly():
    assert 0 < kelly_criterion(0.6, 2000, -1000) < 0.25

def test_stop_fixed():
    r = StopLossManager(method="fixed", fixed_pct=0.05).calculate_stop_loss(50000, 46000)
    assert r["is_stopped"]

def test_portfolio_buy_sell():
    pf = Portfolio(1e8)
    assert pf.buy("FPT", 80000, 100, "2026-01-01")["status"] == "filled"
    assert pf.sell("FPT", 85000, date="2026-02-01")["pnl"] > 0
