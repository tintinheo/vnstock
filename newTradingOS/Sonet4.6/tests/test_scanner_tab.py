from __future__ import annotations

from core.scoring import SignalResult
from ui.scanner_tab import _scanner_review_state


def _make_signal(ticker: str, action: str, score: float) -> SignalResult:
    return SignalResult(
        ticker=ticker,
        timeframe="1M",
        score=score,
        action=action,
        price=50_000.0,
        stop_loss=47_500.0,
        take_profit=56_000.0,
        rr_ratio=2.4,
        atr=1_000.0,
    )


def test_scanner_review_state_prioritises_top_ideas_when_buy_setups_are_strong():
    all_results = [
        _make_signal("AAA", "BUY", 72.0),
        _make_signal("BBB", "STRONG BUY", 84.0),
        _make_signal("CCC", "BUY", 68.0),
        _make_signal("DDD", "WATCH", 38.0),
    ]
    visible_results = [result for result in all_results if result.action in ("BUY", "STRONG BUY")]

    state = _scanner_review_state("Top ideas", visible_results, all_results)

    assert state["tone"] == "success"
    assert "BUY+" in state["primary"]


def test_scanner_review_state_pushes_risk_review_when_focus_is_risk():
    all_results = [
        _make_signal("AAA", "WATCH", 41.0),
        _make_signal("BBB", "SELL", 24.0),
        _make_signal("CCC", "HOLD", 55.0),
    ]
    visible_results = [result for result in all_results if result.action in ("WATCH", "SELL")]

    state = _scanner_review_state("Theo dõi rủi ro", visible_results, all_results)

    assert state["tone"] == "warning"
    assert "rủi ro" in state["primary"]


def test_scanner_review_state_warns_when_focus_returns_no_rows():
    all_results = [_make_signal("AAA", "BUY", 70.0)]

    state = _scanner_review_state("Theo dõi rủi ro", [], all_results)

    assert state["tone"] == "warning"
    assert "Không có mã" in state["primary"]