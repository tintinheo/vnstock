"""
tests/test_portfolio_tracker.py
Regression tests for portfolio.tracker position disambiguation.
"""
from __future__ import annotations

from portfolio.tracker import Portfolio, Position


def _pos(ticker: str, timeframe: str, entry_date: str, entry_price: float = 50_000.0) -> Position:
    n_shares = 100
    return Position(
        ticker=ticker,
        timeframe=timeframe,
        entry_date=entry_date,
        entry_price=entry_price,
        n_shares=n_shares,
        stop_loss=47_500.0,
        take_profit=57_500.0,
        cost_vnd=entry_price * n_shares,
    )


class TestClosePositionDisambiguation:
    def test_close_position_uses_timeframe_when_same_ticker_exists_twice(self):
        portfolio = Portfolio(capital=200_000_000)
        pos_1m = _pos("VCB", "1M", "2026-01-10")
        pos_3m = _pos("VCB", "3M", "2026-01-11")
        portfolio.positions = [pos_1m, pos_3m]

        closed = portfolio.close_position(
            "VCB",
            exit_price=55_000.0,
            exit_date="2026-02-01",
            reason="manual",
            timeframe="3M",
        )

        assert closed is not None
        assert closed.timeframe == "3M"
        assert len(portfolio.open_positions) == 1
        assert portfolio.open_positions[0].timeframe == "1M"

    def test_close_position_uses_entry_date_when_same_ticker_and_timeframe_repeat(self):
        portfolio = Portfolio(capital=200_000_000)
        older = _pos("MBB", "1M", "2026-01-10")
        newer = _pos("MBB", "1M", "2026-01-20")
        portfolio.positions = [older, newer]

        closed = portfolio.close_position(
            "MBB",
            exit_price=54_000.0,
            exit_date="2026-02-05",
            reason="manual",
            timeframe="1M",
            entry_date="2026-01-20",
        )

        assert closed is not None
        assert closed.entry_date == "2026-01-20"
        assert len(portfolio.open_positions) == 1
        assert portfolio.open_positions[0].entry_date == "2026-01-10"

    def test_close_position_without_filters_remains_backward_compatible(self):
        portfolio = Portfolio(capital=200_000_000)
        first = _pos("FPT", "1M", "2026-01-05")
        second = _pos("FPT", "3M", "2026-01-08")
        portfolio.positions = [first, second]

        closed = portfolio.close_position(
            "FPT",
            exit_price=56_000.0,
            exit_date="2026-02-01",
            reason="manual",
        )

        assert closed is not None
        assert closed.entry_date == "2026-01-05"
        assert len(portfolio.open_positions) == 1
        assert portfolio.open_positions[0].entry_date == "2026-01-08"