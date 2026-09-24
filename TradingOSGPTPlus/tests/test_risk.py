from datetime import date, datetime, timezone

import pandas as pd

from app.analytics.indicators import add_indicators
from app.analytics.risk import build_risk_plan


def test_risk_plan_rounds_to_100_share_lot():
    rows = []
    for i in range(80):
        price = 100_000 + i * 100
        rows.append(
            {
                "ticker": "FPT",
                "exchange": "HOSE",
                "date": date(2026, 1, 1) + pd.Timedelta(days=i),
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 100_000,
                "value": None,
                "source": "test",
                "adjusted": False,
                "fetched_at": datetime.now(timezone.utc),
                "unit_rule_applied": "actual_vnd",
            }
        )
    features = add_indicators(pd.DataFrame(rows))
    plan = build_risk_plan(features, capital=500_000_000)
    assert plan["position_size"].shares % 100 == 0
    assert plan["position_size"].risk_pct_capital <= 0.0201
    assert plan["position_size"].allocation_pct_capital <= 0.2001

