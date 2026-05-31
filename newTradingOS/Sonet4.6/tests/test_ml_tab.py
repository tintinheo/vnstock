from __future__ import annotations

import pandas as pd

from ml.ensemble import ForecastResult
from ui.ml_tab import _forecast_trust_state, _forecast_usage_policy


def _make_result(
    *,
    model_preds: dict,
    weights_used: dict,
    method_flags: dict,
    current_price: float = 100.0,
) -> ForecastResult:
    return ForecastResult(
        ticker="VCB",
        timeframe="1M",
        n_days=3,
        prices=[100.0, 102.0, 104.0],
        prices_bull=[102.0, 106.0, 111.0],
        prices_bear=[98.0, 99.0, 101.0],
        model_preds=model_preds,
        weights_used=weights_used,
        method_flags=method_flags,
        current_price=current_price,
        target_price=104.0,
        upside_pct=4.0,
    )


def test_forecast_trust_state_flags_holt_only_fallback():
    fc = _make_result(
        model_preds={"holt": [100.0, 101.0, 102.0]},
        weights_used={"holt": 1.0},
        method_flags={"lstm": False, "xgb": False, "rf": False, "mc": False},
    )
    df = pd.DataFrame(index=pd.to_datetime(["2026-05-29"]))

    trust = _forecast_trust_state(fc, "SSI", df, "sideways")

    assert trust["fallback_only"] is True
    assert trust["degraded"] is True
    assert trust["models_used"] == 1
    assert trust["models_expected"] == 1
    assert trust["active_models"] == ["holt"]
    assert trust["as_of"] == "2026-05-29"


def test_forecast_trust_state_marks_missing_runtime_models():
    fc = _make_result(
        model_preds={"rf": [100.0, 101.0, 102.0], "mc": [100.0, 100.5, 101.0]},
        weights_used={"rf": 0.55, "mc": 0.45},
        method_flags={"lstm": True, "xgb": True, "rf": True, "mc": True},
    )
    df = pd.DataFrame(index=pd.to_datetime(["2026-05-30"]))

    trust = _forecast_trust_state(fc, "DNSE", df, "bull")

    assert trust["fallback_only"] is False
    assert trust["degraded"] is True
    assert trust["models_used"] == 2
    assert trust["models_expected"] == 4
    assert trust["inactive_models"] == ["lstm", "xgb"]
    assert trust["source"] == "DNSE"


def test_forecast_trust_state_for_full_runtime_ensemble():
    fc = _make_result(
        model_preds={
            "lstm": [100.0, 101.0, 103.0],
            "rf": [100.0, 101.5, 103.5],
            "mc": [100.0, 101.2, 102.6],
        },
        weights_used={"lstm": 0.4, "rf": 0.35, "mc": 0.25},
        method_flags={"lstm": True, "rf": True, "mc": True},
    )
    df = pd.DataFrame(index=pd.to_datetime(["2026-05-28"]))

    trust = _forecast_trust_state(fc, "DNSE", df, "bull")

    assert trust["fallback_only"] is False
    assert trust["degraded"] is False
    assert trust["models_used"] == 3
    assert trust["models_expected"] == 3
    assert trust["inactive_models"] == []
    assert trust["band_pct"] == 10.0


def test_forecast_usage_policy_marks_fallback_as_informational_only():
    policy = _forecast_usage_policy(
        {
            "fallback_only": True,
            "degraded": True,
            "band_pct": 4.0,
        },
        upside_pct=8.0,
    )

    assert policy["usage"] == "Informational only"
    assert policy["confidence"] == "Low"


def test_forecast_usage_policy_can_mark_clean_signal_as_sizing_review():
    policy = _forecast_usage_policy(
        {
            "fallback_only": False,
            "degraded": False,
            "band_pct": 6.0,
        },
        upside_pct=7.5,
    )

    assert policy["usage"] == "Eligible for sizing review"
    assert policy["tone"] == "success"