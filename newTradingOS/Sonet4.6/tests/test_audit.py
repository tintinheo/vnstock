from __future__ import annotations

from core.audit import ACTION_CLOSE, ACTION_SCAN, filter_events, get_event_detail_kind
from ui.audit_tab import _apply_audit_preset


def _scan_summary_event(*, legacy: bool = False) -> dict:
    detail = {
        "n_tickers": 12,
        "regime": "bull",
        "macro_score": 6.5,
    }
    if not legacy:
        detail["kind"] = "summary"
    return {
        "ts": "2026-05-31T09:00:00.000",
        "action": ACTION_SCAN,
        "ticker": "",
        "timeframe": "1M",
        "detail": detail,
        "result": "ok",
    }


def _scan_result_event(*, legacy: bool = False) -> dict:
    detail = {
        "score": 82.0,
        "signal_action": "BUY",
    }
    if not legacy:
        detail["kind"] = "result"
    return {
        "ts": "2026-05-31T09:01:00.000",
        "action": ACTION_SCAN,
        "ticker": "VCB",
        "timeframe": "1M",
        "detail": detail,
        "result": "ok",
    }


def test_get_event_detail_kind_reads_explicit_kind():
    assert get_event_detail_kind(_scan_summary_event()) == "summary"
    assert get_event_detail_kind(_scan_result_event()) == "result"


def test_get_event_detail_kind_infers_legacy_scan_shape():
    assert get_event_detail_kind(_scan_summary_event(legacy=True)) == "summary"
    assert get_event_detail_kind(_scan_result_event(legacy=True)) == "result"


def test_filter_events_can_keep_only_scan_summaries():
    events = [
        _scan_summary_event(),
        _scan_result_event(),
        {
            "ts": "2026-05-31T09:02:00.000",
            "action": ACTION_CLOSE,
            "ticker": "VCB",
            "timeframe": "1M",
            "detail": {"reason": "manual"},
            "result": "ok",
        },
    ]

    filtered = filter_events(events, actions=[ACTION_SCAN], detail_kinds=["summary"])

    assert len(filtered) == 1
    assert get_event_detail_kind(filtered[0]) == "summary"


def test_filter_events_can_keep_only_legacy_scan_results():
    events = [
        _scan_summary_event(legacy=True),
        _scan_result_event(legacy=True),
    ]

    filtered = filter_events(events, actions=[ACTION_SCAN], detail_kinds=["result"])

    assert len(filtered) == 1
    assert filtered[0]["ticker"] == "VCB"


def test_audit_tab_dataframe_marks_scan_subtypes():
    from ui.audit_tab import _events_to_df

    df = _events_to_df([
        _scan_summary_event(),
        _scan_result_event(),
    ])

    assert list(df["Phân loại"]) == ["Tổng hợp scan", "Tín hiệu từng mã"]


def test_audit_tab_dataframe_exposes_structured_scan_columns():
    from ui.audit_tab import _events_to_df

    event = _scan_result_event()
    event["detail"].update({
        "source": "DNSE",
        "ff_basis": "CafeF foreign history | 20 sessions",
        "manip_flag": True,
        "regime_ok": False,
        "message": "macro weak",
    })

    df = _events_to_df([event])

    assert df.iloc[0]["Tín hiệu"] == "BUY"
    assert df.iloc[0]["Điểm"] == 82.0
    assert df.iloc[0]["Nguồn"] == "DNSE"
    assert df.iloc[0]["Basis"] == "CafeF foreign history | 20 sessions"
    assert "manip" in df.iloc[0]["Ghi chú"]


def test_apply_audit_preset_can_keep_buy_signals_only():
    buy_event = _scan_result_event()
    sell_event = _scan_result_event()
    sell_event["detail"]["signal_action"] = "SELL"

    filtered = _apply_audit_preset([buy_event, sell_event], "BUY / STRONG BUY")

    assert len(filtered) == 1
    assert filtered[0]["detail"]["signal_action"] == "BUY"