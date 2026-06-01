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


# ─────────────────────────────────────────────────────────────
# VN-02 — update_stops() với ngưỡng break-even per timeframe
# ─────────────────────────────────────────────────────────────
class TestUpdateStops:
    """VN-02 regression: break-even stop trigger phải dùng ngưỡng riêng theo TF.

    1W (5 phiên): +7%  — 1 phiên trần HOSE là đủ
    2W (10 phiên): +8%
    1M (20 phiên): +10% — ~2 phiên trần
    3M (60 phiên): +12%
    5M (100 phiên): +15% — giữ nguyên như cũ
    """

    def _open_pos(self, tf: str, entry_price: float = 50_000.0) -> "Position":
        return Position(
            ticker="VCB",
            timeframe=tf,
            entry_date="2026-01-10",
            entry_price=entry_price,
            n_shares=100,
            stop_loss=entry_price * 0.93,
            take_profit=entry_price * 1.20,
            cost_vnd=entry_price * 100,
        )

    def _portfolio_with(self, pos: "Position") -> "Portfolio":
        p = Portfolio(capital=10_000_000)
        p.positions = [pos]
        return p

    # ─── 1W: ngưỡng 7% ────────────────────────────────────────

    def test_1w_triggers_at_7pct(self):
        """1W: giá tăng đúng 7% → stop được nâng lên entry."""
        pos = self._open_pos("1W", 50_000)
        port = self._portfolio_with(pos)
        updated = port.update_stops({"VCB": 53_500})  # +7%
        assert "VCB" in updated
        assert pos.stop_loss == pos.entry_price

    def test_1w_no_trigger_at_6_9pct(self):
        """1W: +6.9% chưa đủ ngưỡng 7% → stop không thay đổi."""
        pos = self._open_pos("1W", 50_000)
        original_stop = pos.stop_loss
        port = self._portfolio_with(pos)
        port.update_stops({"VCB": 53_450})  # +6.9%
        assert pos.stop_loss == original_stop

    # ─── 2W: ngưỡng 8% ────────────────────────────────────────

    def test_2w_triggers_at_8pct(self):
        """2W: +8% → stop nâng lên entry."""
        pos = self._open_pos("2W", 50_000)
        port = self._portfolio_with(pos)
        port.update_stops({"VCB": 54_000})  # +8%
        assert pos.stop_loss == pos.entry_price

    def test_2w_no_trigger_at_7pct(self):
        """2W: +7% chưa đủ ngưỡng 8% (không nhầm với ngưỡng 1W)."""
        pos = self._open_pos("2W", 50_000)
        original_stop = pos.stop_loss
        port = self._portfolio_with(pos)
        port.update_stops({"VCB": 53_500})  # +7%
        assert pos.stop_loss == original_stop

    # ─── 1M: ngưỡng 10% ───────────────────────────────────────

    def test_1m_triggers_at_10pct(self):
        """1M: +10% → stop nâng lên entry."""
        pos = self._open_pos("1M", 50_000)
        port = self._portfolio_with(pos)
        port.update_stops({"VCB": 55_000})  # +10%
        assert pos.stop_loss == pos.entry_price

    def test_1m_no_trigger_at_9pct(self):
        """1M: +9.5% chưa đủ ngưỡng 10%."""
        pos = self._open_pos("1M", 50_000)
        original_stop = pos.stop_loss
        port = self._portfolio_with(pos)
        port.update_stops({"VCB": 54_750})  # +9.5%
        assert pos.stop_loss == original_stop

    # ─── 3M: ngưỡng 12% ───────────────────────────────────────

    def test_3m_triggers_at_12pct(self):
        """3M: +12% → stop nâng lên entry."""
        pos = self._open_pos("3M", 50_000)
        port = self._portfolio_with(pos)
        port.update_stops({"VCB": 56_000})  # +12%
        assert pos.stop_loss == pos.entry_price

    def test_3m_no_trigger_at_11pct(self):
        """3M: +11% chưa đủ ngưỡng 12%."""
        pos = self._open_pos("3M", 50_000)
        original_stop = pos.stop_loss
        port = self._portfolio_with(pos)
        port.update_stops({"VCB": 55_500})  # +11%
        assert pos.stop_loss == original_stop

    # ─── 5M: ngưỡng 15% (regression — không thay đổi) ─────────

    def test_5m_triggers_at_15pct(self):
        """5M: +15% → stop nâng lên entry (regression test)."""
        pos = self._open_pos("5M", 50_000)
        port = self._portfolio_with(pos)
        port.update_stops({"VCB": 57_500})  # +15%
        assert pos.stop_loss == pos.entry_price

    def test_5m_no_trigger_at_14pct(self):
        """5M: +14.9% chưa đủ ngưỡng 15%."""
        pos = self._open_pos("5M", 50_000)
        original_stop = pos.stop_loss
        port = self._portfolio_with(pos)
        port.update_stops({"VCB": 57_450})  # +14.9%
        assert pos.stop_loss == original_stop

    # ─── Guard conditions ─────────────────────────────────────

    def test_stop_already_at_entry_not_reported(self):
        """Stop đã được nâng lên entry trước đó → không báo cáo lần thứ hai."""
        pos = self._open_pos("1M", 50_000)
        pos.stop_loss = pos.entry_price  # đã nâng từ trước
        port = self._portfolio_with(pos)
        updated = port.update_stops({"VCB": 60_000})  # +20%
        assert "VCB" not in updated

    def test_update_stops_returns_empty_on_no_prices(self):
        """Không có giá → trả về list rỗng (không crash)."""
        pos = self._open_pos("1M")
        port = self._portfolio_with(pos)
        assert port.update_stops({}) == []
        assert port.update_stops(None) == []

    def test_threshold_dict_has_all_five_timeframes(self):
        """_BREAKEVEN_THRESHOLD phải có đủ 5 TF."""
        from portfolio.tracker import _BREAKEVEN_THRESHOLD
        for tf in ("1W", "2W", "1M", "3M", "5M"):
            assert tf in _BREAKEVEN_THRESHOLD

    def test_threshold_ordering_shorter_tf_lower_threshold(self):
        """Ngưỡng ngắn hơn phải nhỏ hơn: 1W < 2W < 1M < 3M < 5M."""
        from portfolio.tracker import _BREAKEVEN_THRESHOLD as T
        assert T["1W"] < T["2W"] < T["1M"] < T["3M"] < T["5M"]