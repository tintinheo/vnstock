import math

import pandas as pd

from app.config import Settings, get_settings
from app.models import EntryPlan, PositionSize, StopLossPlan, TakeProfitPlan


def build_risk_plan(
    features: pd.DataFrame,
    capital: float,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    latest = features.iloc[-1]
    close = float(latest["close"])
    atr = latest.get("atr_14")
    atr_value = float(atr) if pd.notna(atr) and float(atr) > 0 else close * 0.035
    stop_distance = max(2.2 * atr_value, close * 0.05)
    stop_price = max(close - stop_distance, close * 0.5)
    risk_per_share = close - stop_price
    max_risk_amount = capital * settings.max_risk_per_trade
    max_position_value = capital * settings.max_position_pct
    risk_shares = math.floor(max_risk_amount / risk_per_share) if risk_per_share > 0 else 0
    value_shares = math.floor(max_position_value / close) if close > 0 else 0
    raw_shares = min(risk_shares, value_shares)
    shares = max(0, (raw_shares // 100) * 100)
    lots = shares // 100
    value = shares * close
    risk_amount = shares * risk_per_share
    risk_pct = risk_amount / capital if capital > 0 else 0
    allocation_pct = value / capital if capital > 0 else 0

    reward_unit = risk_per_share
    return {
        "entry": EntryPlan(
            market=round(close, 2),
            conservative=round(max(close - 0.5 * atr_value, 0), 2),
            aggressive=round(close + 0.25 * atr_value, 2),
        ),
        "stop_loss": StopLossPlan(
            price=round(stop_price, 2),
            pct=round((stop_price / close - 1) * 100, 2),
            reason="max(2.2*ATR14, 5% price) with Vietnam daily-limit execution caution",
        ),
        "take_profit": TakeProfitPlan(
            tp1=round(close + reward_unit, 2),
            tp2=round(close + 2 * reward_unit, 2),
            tp3=round(close + 3 * reward_unit, 2),
        ),
        "position_size": PositionSize(
            shares=shares,
            lots=lots,
            value=round(value, 2),
            risk_amount=round(risk_amount, 2),
            risk_pct_capital=round(risk_pct, 4),
            allocation_pct_capital=round(allocation_pct, 4),
        ),
        "scaling_plan": [
            {"step": "initial", "pct": 0.5, "shares": (shares * 50 // 100 // 100) * 100},
            {"step": "confirmation", "pct": 0.3, "shares": (shares * 30 // 100 // 100) * 100},
            {"step": "breakout_or_pullback", "pct": 0.2, "shares": (shares * 20 // 100 // 100) * 100},
        ],
    }

