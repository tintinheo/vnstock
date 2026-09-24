"""Negative tests for point-in-time macro and earnings observations."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from tradingos.core.earnings import EarningsRolloverRisk, compute_earnings_risk
from tradingos.core.macro import compute_macro_regime
from tradingos.data.fetcher import _infer_earnings_calendar, fetch_sbv_omo_net


def test_missing_omo_source_is_not_a_zero_observation():
    observation = fetch_sbv_omo_net()
    result = compute_macro_regime(
        sbv_net_injection_7d=observation["net_7d"],
        sbv_as_of=observation["as_of"],
        sbv_status=observation["status"],
    )
    assert observation["net_7d"] is None
    assert not result.indicators


def test_passed_regulatory_deadline_remains_unconfirmed_estimate():
    today = date(2026, 9, 22)
    rows = _infer_earnings_calendar("VNM", today, 30)
    passed = [row for row in rows if row["expected_publication_date"] <= today]
    assert passed
    assert all(row["confirmed"] is False for row in passed)
    assert all(row["actual_publication_date"] is None for row in passed)
    assert all(row["source_type"] == "REGULATORY_ESTIMATE" for row in passed)


def test_publication_observed_after_signal_is_not_backtest_event():
    signal_time = datetime(2026, 4, 20, 15, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    calendar = pd.DataFrame([{
        "ticker": "VNM",
        "fiscal_quarter": "2026Q1",
        "expected_publication_date": date(2026, 4, 25),
        "actual_publication_date": date(2026, 4, 21),
        "publication_timestamp": signal_time + timedelta(days=1),
        "confirmed": True,
        "event_status": "CONFIRMED",
        "source": "verified exchange filing",
        "source_type": "EXCHANGE_FILING",
    }])
    risk = compute_earnings_risk(
        "VNM", current_date=signal_time.date(), earnings_df=calendar, signal_time=signal_time
    )
    assert risk.rollover_risk is EarningsRolloverRisk.SAFE
    assert risk.next_pub_date is None
