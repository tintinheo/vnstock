from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Action(str, Enum):
    buy = "BUY"
    weak_buy = "WEAK_BUY"
    hold = "HOLD"
    weak_sell = "WEAK_SELL"
    sell = "SELL"


class Horizon(str, Enum):
    one_week = "1W"
    two_weeks = "2W"
    one_month = "1M"
    three_months = "3M"
    five_months = "5M"


class Regime(str, Enum):
    uptrend = "UPTREND"
    sideway = "SIDEWAY"
    downtrend = "DOWNTREND"
    volatile = "VOLATILE"
    unknown = "UNKNOWN"


class OhlcvBar(BaseModel):
    ticker: str
    exchange: str = "UNKNOWN"
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    value: float | None = None
    source: str
    adjusted: bool = False
    fetched_at: datetime
    unit_rule_applied: str


class DataResponse(BaseModel):
    ticker: str
    exchange: str = "UNKNOWN"
    data_source: str
    is_cached: bool
    latest_date: date | None
    row_count: int
    source_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    data: list[OhlcvBar]


class EntryPlan(BaseModel):
    market: float
    conservative: float
    aggressive: float


class StopLossPlan(BaseModel):
    price: float
    pct: float
    reason: str


class TakeProfitPlan(BaseModel):
    tp1: float
    tp2: float
    tp3: float


class PositionSize(BaseModel):
    shares: int
    lots: int
    value: float
    risk_amount: float
    risk_pct_capital: float
    allocation_pct_capital: float


class SignalResponse(BaseModel):
    ticker: str
    exchange: str
    data_source: str
    is_cached: bool
    latest_date: date
    horizon: Horizon
    regime: Regime
    technical: dict[str, Any]
    strategy_signals: dict[str, Any]
    reasons: list[str]
    warnings: list[str]


class DecisionResponse(BaseModel):
    decision_id: str
    audit_id: str
    ticker: str
    exchange: str
    timestamp: datetime
    horizon: Horizon
    action: Action
    confidence: float = Field(ge=0, le=95)
    regime: Regime
    latest_price: float
    data_source: str
    is_cached: bool
    entry: EntryPlan
    stop_loss: StopLossPlan
    take_profit: TakeProfitPlan
    position_size: PositionSize
    scaling_plan: list[dict[str, Any]]
    indicators: dict[str, Any]
    ml: dict[str, Any] | None = None
    reasons: list[str]
    warnings: list[str]


class BacktestResponse(BaseModel):
    backtest_id: str
    ticker: str
    strategy: Horizon
    date_from: date
    date_to: date
    data_source: str
    assumptions: dict[str, Any]
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    report_url: str | None = None
    warnings: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    id: str
    ts: datetime
    action: str
    ticker: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    status: Literal["success", "failure", "degraded"]
    duration_ms: float
    ip: str | None = None
    data_source: str | None = None
    signal: str | None = None
    confidence: float | None = None
    result_summary: dict[str, Any] | str | None = None

