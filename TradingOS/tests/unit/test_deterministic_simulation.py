"""Regression coverage for reproducible decision-snapshot simulations."""
from __future__ import annotations

import numpy as np
import pandas as pd

from tradingos.core.mfpm import compute_mfpm


def _snapshot() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 50_000 * np.cumprod(1 + rng.normal(0.001, 0.012, 100))
    frame = pd.DataFrame({
        "open": close * 0.998,
        "high": close * 1.012,
        "low": close * 0.988,
        "close": close,
        "volume": np.full(100, 1_000_000.0),
    }, index=pd.date_range("2026-01-02", periods=100, freq="B"))
    frame["SMA20"] = frame.close.rolling(20).mean()
    frame["SMA50"] = frame.close.rolling(50).mean()
    frame["RSI14"] = 52.0
    frame["ATR14"] = frame.close * 0.02
    return frame


def test_same_decision_snapshot_has_same_simulation_and_action() -> None:
    kwargs = dict(
        df=_snapshot(),
        sms_result={"sms": 45, "components": {}, "mcvd_detail": {}},
        amf_result={"decision": "PASS", "details": {}},
        pattern_result={"best_pattern": "NONE", "pattern_bonus": 0},
        symbol="FPT",
        effective_session="2026-05-21",
        canonical_data_revision="ssi:2026-05-21T15:00:00Z",
        config_hash="strategy-fixture-v1",
        model_hash="model-fixture-v1",
    )

    first = compute_mfpm(**kwargs)
    second = compute_mfpm(**kwargs)

    assert first["simulation_hit_rate"] == second["simulation_hit_rate"]
    assert first["prediction_interval"] == second["prediction_interval"]
    assert first["action"] == second["action"]
    assert first["forecast_probability"] is None
    assert first["calibration_status"] == "UNCALIBRATED"
    assert first["confidence"] != "HIGH"
