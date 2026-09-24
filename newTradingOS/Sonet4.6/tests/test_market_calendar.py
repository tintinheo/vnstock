from __future__ import annotations

import pandas as pd

from core.market_calendar import (
    annualization_sessions_per_year,
    calendar_basis_summary,
    future_trading_dates,
    is_trading_day,
    trading_sessions_between,
    trading_sessions_in_year,
)


def test_future_trading_dates_skip_vn_public_holiday():
    dates = future_trading_dates(pd.Timestamp("2026-09-01"), 2)

    assert list(dates.strftime("%Y-%m-%d")) == ["2026-09-03", "2026-09-04"]


def test_trading_sessions_between_skips_vn_public_holiday():
    assert trading_sessions_between("2026-09-01", "2026-09-04") == 2


def test_trading_sessions_in_year_reflects_vn_calendar():
    assert trading_sessions_in_year(2023) == 249
    assert trading_sessions_in_year(2024) == 250


def test_annualization_sessions_weight_years_by_observation_count():
    dates = [
        "2023-12-27",
        "2023-12-28",
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
    ]

    assert annualization_sessions_per_year(dates) == 250


def test_is_trading_day_flags_vn_national_day_closed():
    assert is_trading_day("2026-09-02") is False
    assert is_trading_day("2026-09-03") is True


def test_calendar_basis_summary_reports_shared_schedule_by_default():
    label = calendar_basis_summary({"VCB": "HOSE", "PVS": "HNX", "MCH": "UPCOM"})

    assert label == "VN public holidays (shared HOSE/HNX/UPCOM schedule)"