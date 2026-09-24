import uuid

import numpy as np
import pandas as pd

from app.analytics.indicators import add_indicators
from app.analytics.regime import detect_regime
from app.analytics.strategies import evaluate_strategy
from app.models import BacktestResponse, Horizon


def run_simple_backtest(frame: pd.DataFrame, horizon: Horizon, data_source: str) -> BacktestResponse:
    features = add_indicators(frame).dropna(subset=["sma_20", "atr_14"]).copy()
    if len(features) < 40:
        raise ValueError("not enough historical rows for backtest after indicators")

    holding_days = {
        Horizon.one_week: 5,
        Horizon.two_weeks: 10,
        Horizon.one_month: 21,
        Horizon.three_months: 63,
        Horizon.five_months: 105,
    }[horizon]
    cost_bps = 25
    slippage_bps = 15
    round_trip_cost = 2 * (cost_bps + slippage_bps) / 10_000
    trades: list[dict] = []

    i = 60 if len(features) > 90 else 20
    while i + holding_days < len(features):
        window = features.iloc[: i + 1]
        regime = detect_regime(window)
        signal = evaluate_strategy(window, horizon, regime)
        if signal["action"].value in {"BUY", "WEAK_BUY"}:
            entry = float(features.iloc[i]["close"])
            exit_price = float(features.iloc[i + holding_days]["close"])
            gross = exit_price / entry - 1
            net = gross - round_trip_cost
            trades.append(
                {
                    "entry_date": str(features.iloc[i]["date"]),
                    "exit_date": str(features.iloc[i + holding_days]["date"]),
                    "entry": entry,
                    "exit": exit_price,
                    "gross_return": round(gross, 4),
                    "net_return": round(net, 4),
                    "action": signal["action"].value,
                    "confidence": signal["confidence"],
                }
            )
            i += holding_days
        else:
            i += 1

    returns = np.array([trade["net_return"] for trade in trades], dtype=float)
    if len(returns) == 0:
        metrics = {"trades": 0, "win_rate": 0, "total_return": 0, "profit_factor": 0, "max_drawdown": 0, "sharpe_like": 0}
    else:
        equity = (1 + returns).cumprod()
        drawdown = equity / np.maximum.accumulate(equity) - 1
        wins = returns[returns > 0]
        losses = returns[returns < 0]
        metrics = {
            "trades": int(len(returns)),
            "win_rate": round(float((returns > 0).mean()), 4),
            "total_return": round(float(equity[-1] - 1), 4),
            "profit_factor": round(float(wins.sum() / abs(losses.sum())), 4) if losses.size else None,
            "max_drawdown": round(float(drawdown.min()), 4),
            "sharpe_like": round(float(returns.mean() / returns.std(ddof=1)), 4) if len(returns) > 1 and returns.std(ddof=1) else 0,
        }

    return BacktestResponse(
        backtest_id=str(uuid.uuid4()),
        ticker=str(frame.iloc[-1]["ticker"]),
        strategy=horizon,
        date_from=features.iloc[0]["date"],
        date_to=features.iloc[-1]["date"],
        data_source=data_source,
        assumptions={
            "commission_bps_per_side": cost_bps,
            "slippage_bps_per_side": slippage_bps,
            "lot_size": 100,
            "settlement": "T+2.5 modeled as capital reuse caution; not a broker ledger",
            "daily_limit_non_fill": "warned but not fully event-modeled in MVP",
        },
        metrics=metrics,
        trades=trades[-50:],
        warnings=["MVP_BACKTEST_VECTOR_APPROXIMATION", "VERIFY_COSTS_TAX_AND_SETTLEMENT_BEFORE_USE"],
    )

