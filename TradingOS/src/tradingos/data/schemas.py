"""Pydantic schemas for TradingOS Alpha (SRS §3.4 §3.5 §4.4 §5.2 §7.2 FR-6)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Type aliases ──────────────────────────────────────────────────────────────
ACTION      = str   # NO_ACTION|WATCH|BUY|STRONG_BUY|EXIT|FORCED_EXIT
CONFIDENCE  = str   # HIGH|MEDIUM|LOW|—
HMM_STATE   = str   # STEADY_BULL|TRANSITIONAL|STEADY_BEAR
AMD_PHASE   = str   # ACCUMULATION|MARKUP|DISTRIBUTION|MARKDOWN|RANGING
DATA_SOURCE = str   # TICK_REAL|PARTIAL_PROXY|PROXY_OHLCV
SECTOR_FLOW = str   # INFLOW|NEUTRAL|OUTFLOW
SMS_LABEL   = str   # WHALE_BUYING|WHALE_DISTRIBUTING|MIXED|RETAIL_DRIVEN
WARN_LEVEL  = str   # NONE|WATCH|CAUTION|EXIT|FORCED_EXIT
SIGNAL_MODE = str   # MODE_A|MODE_B|MODE_W|MIXED


# ── Horizon Recommendation ────────────────────────────────────────────────────

class HorizonRecommendation(BaseModel):
    horizon_days        : int
    period_label        : str
    action              : ACTION
    confidence          : CONFIDENCE
    entry_price         : float = 0.0
    entry_window        : str = ""
    stop_loss           : float = 0.0
    sl_pct              : float = 0.0
    tp1                 : float = 0.0
    tp2                 : float = 0.0
    rr_ratio            : float = 0.0
    expected_hold_days  : int = 0
    exit_condition      : str = ""
    sms_contribution    : str = ""
    notes               : str = ""


# ── Profiler Request ──────────────────────────────────────────────────────────

class ProfilerRequest(BaseModel):
    ticker          : str
    mode            : str = "FULL"         # FULL|QUICK|HORIZON_ONLY
    horizons        : Optional[list[int]] = None
    portfolio_value : float = 300_000_000.0


# ── TickerProfile (34 fields, SRS §3.4) ──────────────────────────────────────

class TickerProfile(BaseModel):
    # Identity (1–4)
    ticker          : str
    exchange        : str = "HOSE"
    sector          : str = ""
    last_updated    : str = ""

    # Signal output (5–11)
    action          : ACTION
    confidence      : CONFIDENCE
    signal_mode     : SIGNAL_MODE
    mfpm_score      : int
    mode_w_score    : int
    mc_win_prob     : float

    # Entry / Exit (12–17)
    entry_price     : float
    stop_loss       : float
    sl_pct          : float
    tp1             : float
    tp2             : float
    rr_ratio        : float

    # Traditional indicators (18–26)
    close           : float
    volume          : float
    avg_volume_20d  : float
    sma20           : float
    sma50           : float
    sma200          : float
    rsi14           : float
    atr14           : float
    obv             : float
    macd            : float = 0.0

    # FR-6 money flow (27–33)
    sms_raw         : int
    sms_label       : SMS_LABEL
    mcvd_5d         : float
    mcvd_20d        : float
    mcvd_trend      : str
    stealth_accum   : bool
    stealth_confidence : str = "LOW"
    distribution_warning : WARN_LEVEL

    # Explanation (34+)
    amd_phase       : AMD_PHASE
    hmm_state       : HMM_STATE
    gmo_omega       : float = 0.0       # SRS §3.4 field
    vqs             : float
    amf_decision    : str
    amf_flags       : list[str] = Field(default_factory=list)  # SRS §3.4
    best_pattern    : str
    sector_flow     : str = "NEUTRAL"   # SRS §3.4 field 26
    fol_net_5d      : int = 0           # SRS §3.4 field 27
    whale_pct_vol   : float = 0.0       # SRS §3.4 field 28
    audit_id        : str = ""          # SRS §3.4 field 34

    # Sizing advisory
    sizing_pct      : float
    sizing_shares   : int

    # NLP + advisory
    advisory_text   : str = ""
    entry_window    : str = "—"
    horizons        : list[dict] = Field(default_factory=list)

    # Phase 1 — put-through integration
    pt_net_5d       : float = 0.0
    pt_ratio_5d     : float = 0.0

    # Phase 2 — Macro Regime (macro.py)
    macro_score     : Optional[float] = None   # -100 to +100; None = data unavailable
    macro_regime    : str             = ""     # ACCOMMODATIVE | NEUTRAL | RESTRICTIVE | ""
    macro_confidence: str             = ""     # HIGH | MEDIUM | LOW | ""
    macro_staleness_days: int         = 0      # days since macro data was refreshed

    # Phase 2 — Earnings / BCTC Risk (earnings.py)
    earnings_risk   : str             = "SAFE"  # SAFE | CAUTION | HIGH_RISK
    days_to_earnings: Optional[int]   = None    # calendar days to next pub date
    next_earnings_date: str           = ""      # ISO date string, "" if unknown

    # Phase 3 — Fundamentals (fundamental.py)
    fundamental_score   : Optional[float] = None  # 0-100; None if insufficient data
    eps_growth_yoy      : Optional[float] = None  # net-income YoY %
    revenue_growth_yoy  : Optional[float] = None  # revenue YoY %
    roe                 : Optional[float] = None  # Return on Equity %
    debt_to_equity      : Optional[float] = None  # Leverage ratio


# ── Scanner ───────────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    tickers         : Optional[list[str]] = None
    exchange        : str = "HOSE"
    min_action      : str = "WATCH"
    min_mfpm_score  : int = 50
    min_sms         : int = 0           # SRS §4.4 — Whale Watch mode = 60
    sector_filter   : Optional[list[str]] = None  # SRS §4.4
    stealth_only    : bool = False      # SRS §4.4
    limit           : int = 30
    include_blocked : bool = False


class ScanResultItem(BaseModel):
    ticker          : str
    action          : ACTION
    confidence      : CONFIDENCE
    mfpm_score      : int
    mode_w_score    : int
    sms_raw         : int
    sms_label       : SMS_LABEL = "RETAIL_DRIVEN"   # SRS §4.4
    signal_mode     : SIGNAL_MODE
    stealth_accum   : bool = False                  # SRS §4.4
    close           : float
    entry           : float
    sl              : float
    tp1             : float
    rr              : float
    amf_decision    : str
    best_pattern    : str
    hmm_state       : HMM_STATE
    sector_flow     : str = "NEUTRAL"
    earnings_risk   : str = "SAFE"
    fundamental_score: Optional[float] = None
    macro_regime    : str = ""     # ACCOMMODATIVE | NEUTRAL | RESTRICTIVE | ""
    macro_score     : Optional[float] = None


class ScanResult(BaseModel):
    tickers_scanned : int
    tickers_passed  : int
    results         : list[ScanResultItem]
    scan_ts         : str = ""


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditRecord(BaseModel):
    audit_id        : str = ""
    event_type      : str
    ticker          : str = ""
    timestamp       : Optional[datetime] = None
    action          : str = ""
    mfpm_score      : int = 0
    sms_raw         : int = 0
    confidence      : str = "—"
    payload         : dict[str, Any] = Field(default_factory=dict)


# ── Backtest ──────────────────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    ticker          : str
    start_date      : str = ""    # YYYY-MM-DD
    end_date        : str = ""    # YYYY-MM-DD
    sl_pct          : float = 0.06
    mode            : str = "ALL"


class BacktestTrade(BaseModel):
    ticker          : str
    entry_date      : str
    exit_date       : str
    entry_price     : float
    exit_price      : float
    shares          : int
    mode            : str
    pnl             : float
    pnl_pct         : float
    hold_days       : int
    exit_reason     : str
    matched         : bool = True


class BacktestResult(BaseModel):
    ticker          : str
    mode            : str
    start_date      : str
    end_date        : str
    n_trades        : int
    win_rate        : float
    avg_pnl_pct     : float
    max_drawdown    : float
    sharpe          : float
    total_return    : float
    trades          : list[Any] = Field(default_factory=list)
    walk_forward_windows : list[dict] = Field(default_factory=list)


# ── Distribution Alert ────────────────────────────────────────────────────────

class DistributionAlert(BaseModel):
    ticker          : str
    warning_level   : WARN_LEVEL
    flags           : list[str] = Field(default_factory=list)
    score           : int = 0
    explanation     : str = ""


# ── TradingSignal (26+8=34 canonical fields, SRS §11) ─────────────────────────

class TradingSignal(BaseModel):
    # 1–4: Identity
    signal_id       : str = ""
    ticker          : str
    exchange        : str = "HOSE"
    signal_date     : str = ""

    # 5–8: Core signal
    action          : ACTION
    confidence      : CONFIDENCE
    signal_mode     : SIGNAL_MODE
    mfpm_score      : int

    # 9–12: MFPM breakdown
    mode_a_score    : int = 0
    mode_b_score    : int = 0
    mode_w_score    : int = 0
    sms_raw         : int = 0

    # 13–16: Entry/exit params
    entry_price     : float = 0.0
    stop_loss       : float = 0.0
    tp1             : float = 0.0
    tp2             : float = 0.0

    # 17–20: Risk metrics
    rr_ratio        : float = 0.0
    mc_win_prob     : float = 0.0
    kelly_size_pct  : float = 0.0
    data_source     : DATA_SOURCE = "PROXY_OHLCV"

    # 21–26: Technical context
    hmm_state       : HMM_STATE = "TRANSITIONAL"
    amd_phase       : AMD_PHASE = "RANGING"
    amf_decision    : str = "PASS"
    vqs             : float = 0.0
    best_pattern    : str = "NONE"
    distribution_warning : WARN_LEVEL = "NONE"

    # 27–34: FR-6 money flow
    sms_label       : SMS_LABEL = "RETAIL_DRIVEN"
    mcvd_5d         : float = 0.0
    mcvd_20d        : float = 0.0
    mcvd_trend      : str = "FLAT"
    stealth_accum   : bool = False
    stealth_confidence : str = "LOW"
    sector_flow     : SECTOR_FLOW = "NEUTRAL"
    advisory_text   : str = ""
    # Phase 1 — put-through integration
    pt_net_5d       : float = 0.0
    pt_ratio_5d     : float = 0.0
