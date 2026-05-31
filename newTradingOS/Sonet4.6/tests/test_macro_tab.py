from __future__ import annotations

from ui.macro_tab import _macro_component_states, _overall_tf_condition


def _macro_payload(*, stale_fields: list[str] | None = None, ff_net: float = 0.0) -> dict:
    return {
        "dxy_trend": "neutral",
        "vix_level": "normal",
        "foreign_flow": {"net_buy": ff_net, "trend": "N/A"},
        "breadth": {"advance": 100, "decline": 80, "fetch_ok": True},
        "ad_ratio": 0.55,
        "stale_fields": stale_fields or [],
    }


def test_macro_component_states_mark_stale_values_unknown():
    states = _macro_component_states(
        _macro_payload(stale_fields=["DXY (USD Index)", "foreign_flow", "market_breadth"])
    )

    assert states["dxy"] is None
    assert states["foreign"] is None
    assert states["breadth"] is None
    assert states["vix"] is True


def test_overall_tf_condition_uses_missing_data_state():
    overall = _overall_tf_condition(True, None, True, True)
    assert overall == "⚪ Thiếu dữ liệu"


def test_overall_tf_condition_not_favorable_when_all_signals_missing_or_weak():
    bearish = _overall_tf_condition(True, False, False, False)
    assert bearish == "🚫 Rủi ro cao"


def test_macro_component_states_keep_loaded_foreign_flow_signal():
    states = _macro_component_states(_macro_payload(ff_net=2e10))

    assert states["dxy"] is True
    assert states["vix"] is True
    assert states["foreign"] is True
    assert states["breadth"] is True