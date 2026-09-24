import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.analytics.indicators import add_indicators
from app.analytics.regime import detect_regime
from app.analytics.risk import build_risk_plan
from app.analytics.strategies import evaluate_all_horizons, evaluate_strategy
from app.config import Settings, get_settings
from app.data.clients import MarketDataClient
from app.models import DataResponse, DecisionResponse, Horizon, SignalResponse
from app.utils import json_safe


class DecisionService:
    def __init__(self, data_client: MarketDataClient | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.data_client = data_client or MarketDataClient(self.settings)

    def get_data(self, ticker: str) -> DataResponse:
        frame, metadata = self.data_client.get_history(ticker)
        return DataResponse(
            ticker=str(frame.iloc[-1]["ticker"]),
            exchange=str(frame.iloc[-1]["exchange"]),
            data_source=str(metadata.get("source", frame.iloc[-1]["source"])),
            is_cached=bool(metadata.get("is_cached", False)),
            latest_date=frame.iloc[-1]["date"],
            row_count=len(frame),
            source_errors=list(metadata.get("source_errors", [])),
            warnings=_data_warnings(frame, metadata),
            data=frame.to_dict(orient="records"),
        )

    def get_signals(self, ticker: str, horizon: Horizon) -> SignalResponse:
        frame, metadata = self.data_client.get_history(ticker)
        features = add_indicators(frame)
        regime = detect_regime(features)
        all_signals = evaluate_all_horizons(features, regime)
        selected = all_signals[horizon.value]
        latest = features.iloc[-1]
        return SignalResponse(
            ticker=str(latest["ticker"]),
            exchange=str(latest["exchange"]),
            data_source=str(metadata.get("source", latest["source"])),
            is_cached=bool(metadata.get("is_cached", False)),
            latest_date=latest["date"],
            horizon=horizon,
            regime=regime,
            technical=_latest_technical(latest),
            strategy_signals=json_safe(all_signals),
            reasons=selected["reasons"],
            warnings=_data_warnings(frame, metadata) + selected["warnings"],
        )

    def get_decision(self, ticker: str, capital: float, horizon: Horizon, audit_id: str) -> DecisionResponse:
        frame, metadata = self.data_client.get_history(ticker)
        features = add_indicators(frame)
        regime = detect_regime(features)
        signal = evaluate_strategy(features, horizon, regime)
        risk_plan = build_risk_plan(features, capital, self.settings)
        latest = features.iloc[-1]
        warnings = _data_warnings(frame, metadata) + signal["warnings"]
        if risk_plan["position_size"].shares == 0:
            warnings.append("POSITION_SIZE_ZERO_AFTER_RISK_AND_LOT_RULES")
        return DecisionResponse(
            decision_id=str(uuid.uuid4()),
            audit_id=audit_id,
            ticker=str(latest["ticker"]),
            exchange=str(latest["exchange"]),
            timestamp=datetime.now(timezone.utc),
            horizon=horizon,
            action=signal["action"],
            confidence=float(signal["confidence"]),
            regime=regime,
            latest_price=float(latest["close"]),
            data_source=str(metadata.get("source", latest["source"])),
            is_cached=bool(metadata.get("is_cached", False)),
            entry=risk_plan["entry"],
            stop_loss=risk_plan["stop_loss"],
            take_profit=risk_plan["take_profit"],
            position_size=risk_plan["position_size"],
            scaling_plan=risk_plan["scaling_plan"],
            indicators=_latest_technical(latest),
            ml={"enabled": False, "reason": "ML pipeline is reserved for Phase 2 walk-forward validation"},
            reasons=signal["reasons"],
            warnings=warnings,
        )


def _latest_technical(latest: pd.Series) -> dict[str, Any]:
    keys = [
        "close",
        "return_1d",
        "sma_10",
        "sma_20",
        "sma_50",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_hist",
        "atr_14",
        "bb_upper",
        "bb_lower",
        "volume_ratio",
        "adx_14",
        "volatility_20",
        "drawdown_60",
    ]
    return json_safe({key: latest.get(key) for key in keys})


def _data_warnings(frame: pd.DataFrame, metadata: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if metadata.get("is_cached"):
        warnings.append("USING_VALID_CACHE_AFTER_LIVE_SOURCES_FAILED")
    if len(frame) < 60:
        warnings.append("LESS_THAN_60_TRADING_DAYS_AVAILABLE")
    latest = frame.iloc[-1]
    if int(latest.get("volume", 0)) == 0:
        warnings.append("LATEST_VOLUME_ZERO_OR_SUSPENDED")
    return warnings

