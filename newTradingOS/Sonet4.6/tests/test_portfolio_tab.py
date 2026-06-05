from __future__ import annotations

from portfolio.tracker import Position
from ui.portfolio_tab import _close_preview, _portfolio_review_state


def test_portfolio_review_state_goes_defensive_when_risk_is_high():
    state = _portfolio_review_state(
        capital=100_000_000,
        cash=20_000_000,
        risk_budget_pct=7.2,
        open_positions=3,
        ready_to_close=1,
    )

    assert state["stance"] == "Phòng thủ"
    assert "giảm risk" in state["next_action"]


def test_portfolio_review_state_ready_when_no_open_positions():
    state = _portfolio_review_state(
        capital=100_000_000,
        cash=100_000_000,
        risk_budget_pct=0.0,
        open_positions=0,
        ready_to_close=0,
    )

    assert state["stance"] == "Sẵn sàng giải ngân"


def test_close_preview_reports_pnl_and_settlement_state():
    pos = Position(
        ticker="VCB",
        timeframe="1M",
        entry_date="2026-01-06",
        entry_price=50_000,
        n_shares=100,
        stop_loss=47_500,
        take_profit=57_500,
        cost_vnd=50_000 * 100 * 1.002,
    )

    preview = _close_preview(pos, 55_000, "2026-01-08")

    assert preview["settlement_ready"] is True
    assert preview["sessions_held"] == 2
    assert preview["pnl_vnd"] > 0
    assert preview["pnl_pct"] > 0