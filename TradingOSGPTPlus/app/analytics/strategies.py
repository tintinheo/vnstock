import pandas as pd

from app.models import Action, Horizon, Regime


def evaluate_strategy(features: pd.DataFrame, horizon: Horizon, regime: Regime) -> dict:
    latest = features.iloc[-1]
    previous = features.iloc[-2] if len(features) > 1 else latest
    score = 0
    reasons: list[str] = []
    warnings: list[str] = []

    close = float(latest["close"])
    rsi = latest.get("rsi_14")
    macd_hist = latest.get("macd_hist")
    volume_ratio = latest.get("volume_ratio")
    sma_20 = latest.get("sma_20")
    sma_50 = latest.get("sma_50")
    drawdown_60 = latest.get("drawdown_60")

    if regime == Regime.uptrend:
        score += 15
        reasons.append("REGIME_UPTREND")
    elif regime == Regime.downtrend:
        score -= 20
        reasons.append("REGIME_DOWNTREND")
    elif regime == Regime.volatile:
        score -= 10
        warnings.append("HIGH_VOLATILITY_REGIME")

    if pd.notna(sma_20) and close > float(sma_20):
        score += 12
        reasons.append("CLOSE_ABOVE_SMA20")
    elif pd.notna(sma_20):
        score -= 10
        reasons.append("CLOSE_BELOW_SMA20")

    if pd.notna(sma_50) and close > float(sma_50):
        score += 8
        reasons.append("CLOSE_ABOVE_SMA50")
    elif pd.notna(sma_50):
        score -= 8
        reasons.append("CLOSE_BELOW_SMA50")

    if pd.notna(macd_hist) and pd.notna(previous.get("macd_hist")):
        if float(macd_hist) > 0 and float(macd_hist) > float(previous["macd_hist"]):
            score += 12
            reasons.append("MACD_HIST_POSITIVE_RISING")
        elif float(macd_hist) < 0:
            score -= 10
            reasons.append("MACD_HIST_NEGATIVE")

    if pd.notna(rsi):
        rsi_value = float(rsi)
        if 45 <= rsi_value <= 68:
            score += 10
            reasons.append("RSI_HEALTHY_MOMENTUM")
        elif rsi_value > 78:
            score -= 12
            warnings.append("RSI_OVERBOUGHT")
        elif rsi_value < 35:
            score -= 8
            warnings.append("RSI_WEAK")

    if pd.notna(volume_ratio):
        if float(volume_ratio) >= 1.2:
            score += 8
            reasons.append("VOLUME_CONFIRMATION")
        elif float(volume_ratio) < 0.6:
            score -= 8
            warnings.append("LOW_VOLUME_CONFIRMATION")

    score += _horizon_adjustment(horizon, latest, close, reasons, warnings)

    if pd.notna(drawdown_60) and float(drawdown_60) < -0.25:
        score -= 10
        warnings.append("DEEP_60D_DRAWDOWN")

    confidence = max(0, min(95, 50 + score))
    action = _action_from_score(score)
    return {
        "horizon": horizon,
        "action": action,
        "confidence": confidence,
        "score": score,
        "reasons": reasons,
        "warnings": warnings,
    }


def evaluate_all_horizons(features: pd.DataFrame, regime: Regime) -> dict[str, dict]:
    return {horizon.value: evaluate_strategy(features, horizon, regime) for horizon in Horizon}


def _horizon_adjustment(horizon: Horizon, latest: pd.Series, close: float, reasons: list[str], warnings: list[str]) -> int:
    score = 0
    if horizon in {Horizon.one_week, Horizon.two_weeks}:
        highest_20 = latest.get("highest_20")
        lowest_20 = latest.get("lowest_20")
        if pd.notna(highest_20) and close >= float(highest_20) * 0.98:
            score += 8
            reasons.append("NEAR_20D_BREAKOUT")
        if pd.notna(lowest_20) and close <= float(lowest_20) * 1.03:
            score -= 8
            warnings.append("NEAR_20D_LOW")
    elif horizon == Horizon.one_month:
        sma_20 = latest.get("sma_20")
        sma_50 = latest.get("sma_50")
        if pd.notna(sma_20) and pd.notna(sma_50) and float(sma_20) > float(sma_50):
            score += 8
            reasons.append("SMA20_ABOVE_SMA50")
    else:
        highest_60 = latest.get("highest_60")
        lowest_60 = latest.get("lowest_60")
        if pd.notna(highest_60) and close >= float(highest_60) * 0.9:
            score += 6
            reasons.append("STRONG_60D_RELATIVE_PRICE")
        if pd.notna(lowest_60) and close <= float(lowest_60) * 1.1:
            score -= 6
            warnings.append("WEAK_60D_RELATIVE_PRICE")
    return score


def _action_from_score(score: int) -> Action:
    if score >= 30:
        return Action.buy
    if score >= 12:
        return Action.weak_buy
    if score <= -30:
        return Action.sell
    if score <= -12:
        return Action.weak_sell
    return Action.hold

