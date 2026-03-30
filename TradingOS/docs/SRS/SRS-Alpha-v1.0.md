# TradingOS Alpha — Software Requirements Specification (SRS) v1.0

> **Version:** 1.0 | **Date:** 2026-03-30 | **Status:** Approved for Implementation
> **Based on:** `TradingOS-Alpha-Proposal-v1.0.md` (Round-5 audit + v5 Merge)
> **Scope:** HOSE + HNX | Swing Trading T+2 → T+15

---

## MỤC LỤC

1. [Giới Thiệu](#1-giới-thiệu)
2. [Tổng Quan Hệ Thống](#2-tổng-quan-hệ-thống)
3. [FR-1: Stock Profiler](#3-fr-1-stock-profiler)
4. [FR-2: Market Scanner](#4-fr-2-market-scanner-tìm-mã-để-mua)
5. [FR-3: Audit Trail](#5-fr-3-audit-trail)
6. [FR-4: Performance Optimization](#6-fr-4-performance-optimization)
7. [FR-5: Backtesting Engine](#7-fr-5-backtesting-engine)
8. [FR-6: Dòng Tiền Lớn — Large Money Flow](#8-fr-6-dòng-tiền-lớn--large-money-flow)
9. [Non-Functional Requirements](#9-non-functional-requirements)
10. [Data Models & DuckDB Schema](#10-data-models--duckdb-schema)
11. [API Specification](#11-api-specification)
12. [UI/UX Specification](#12-uiux-specification)
13. [Implementation Plan (17 tuần)](#13-implementation-plan-17-tuần)
14. [Risk Register](#14-risk-register)

---

## 1. Giới Thiệu

### 1.1 Mục Đích

Tài liệu này mô tả đầy đủ Software Requirements Specification cho **TradingOS Alpha** — hệ thống phân tích định lượng VN tập trung swing trading T+2.5 tích hợp: Wyckoff, CAN SLIM, MFPM, HMM, Monte Carlo, Anti-Manipulation (AMD+VSA+CVD), và **Large Money Flow detection & follow strategy** (dòng tiền lớn).

### 1.2 Gap Analysis — Dòng Tiền Lớn

Proposal v1.0 đã có CVD/whale tracking **ở mức phòng thủ** (block manipulation, confirm entry). Phần **tấn công** — dùng dòng tiền làm *tín hiệu chủ động* để vào lệnh — còn thiếu.

| Thành phần | Trong Proposal v1.0 | Trạng thái SRS này |
|---|---|---|
| CVD intraday whale_net (1 phiên) | ✅ Module 2.10.3 | Giữ nguyên |
| VQS — xác nhận institutional buying | ✅ Module 2.9.2 | Giữ nguyên |
| FOL — foreign net buy/sell (single-day) | ✅ Module 2.6 | Giữ nguyên |
| AMF — chặn signal bị thao túng (phòng thủ) | ✅ Module 2.9 | Giữ nguyên |
| **Multi-day whale accumulation tracking** | ❌ Chưa có | ✅ FR-6.1 mới |
| **Composite Smart Money Score (SMS)** | ❌ Riêng lẻ | ✅ FR-6.2 mới |
| **Stealth Accumulation Detection** | ❌ Chưa có | ✅ FR-6.3 mới |
| **Sector-level money flow rotation** | ❌ Chưa có | ✅ FR-6.4 mới |
| **Follow-the-Whale signal mode** | ❌ Chưa có | ✅ FR-6.5 mới |
| **Whale Distribution early warning** | Chỉ delta_divergence 1 phiên | ✅ FR-6.6 mới |

### 1.3 Definitions

| Term | Definition |
|---|---|
| T+N | N ngày giao dịch từ ngày mua |
| MFPM | Multi-Factor Pullback & Momentum scoring engine |
| Mode A | Pullback entry (RSI cross-up từ vùng ≤50) |
| Mode B | Breakout entry (Close > Pivot high + Volume surge) |
| Mode W | **Follow-the-Whale** — entry basis SMS ≥ 60 (NEW) |
| STRONG_BUY | MFPM score ≥ 70 hoặc SMS ≥ 75 |
| VQS | Volume Quality Score |
| CVD | Cumulative Volume Delta (intraday whale tracker) |
| M-CVD | Multi-day Rolling CVD (new) |
| SMS | Smart Money Score — composite dòng tiền tổng hợp (new) |
| AMD | Accumulation→Markup→Distribution cycle |
| AMF | Anti-Manipulation Filter (4-layer pipeline, phòng thủ) |
| DTL | Dòng Tiền Lớn — Large Money Flow module (tấn công) |

---

## 2. Tổng Quan Hệ Thống

### 2.1 Kiến Trúc

```
┌───────────────────────────────────────────────────────────────────────┐
│                       STREAMLIT UI LAYER                              │
│  [Profiler] [Scanner] [Money Flow] [Backtest] [Audit] [Settings]     │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────┴────────────────────────────────────────┐
│                        SERVICE LAYER                                  │
│  ProfilerService │ ScannerService │ MoneyFlowService │ BacktestService│
│  AuditService    │ AlertService   │ PortfolioService │ SectorService  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────┴────────────────────────────────────────┐
│                       CORE ENGINE LAYER                               │
│  gmo.py        │ indicators.py  │ anti_manip.py  │ patterns.py       │
│  mfpm.py       │ sizing.py      │ t25_engine.py  │ exit_engine.py    │
│  nlp.py        │ backtest.py    │ universe.py    │ atc_router.py     │
│  money_flow.py ← NEW: SMS, M-CVD, Stealth Accum, Sector Rotation    │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────┴────────────────────────────────────────┐
│                         DATA LAYER                                    │
│  fetcher.py (SSI EP-1..14 async + DNSE fallback)                     │
│  cache.py (DuckDB TTL-managed)  │  normalizer.py (ex-div, tick round)│
│  schemas.py (Pydantic)          │  audit_db.py                       │
└───────────────────────────────────────────────────────────────────────┘
```

### 2.2 Luồng Dữ Liệu Chính

```
User input (ticker / scan / money-flow)
  └─► build_universe() + sector_map           [Scanner / DTL mode]
       └─► fetch_ohlcv() ──► DuckDB cache (TTL)
            └─► IndicatorEngine.compute_all()  [SMA/RSI/OBV/VWAP-intraday(5m)/TP-daily/Hurst]
                 └─► MoneyFlowEngine.score()   [M-CVD, SMS, Stealth, Sector]
                      └─► PatternEngine.detect_all()
                           └─► AntiManipFilter.run()  [AMF — phòng thủ]
                                └─► MFPMEngine.score() [Mode A / B / W]
                                     └─► HorizonEngine.project(T+2..T+15)
                                          └─► NLPEngine.advisory()
                                               └─► AuditService.log()
                                                    └─► UI render
```

---

## 3. FR-1: Stock Profiler

### 3.1 Tổng Quan

Input 1 hoặc danh sách tickers → chạy full pipeline → trả khuyến nghị T+2..T+15 theo 3 nhóm ngắn/trung/dài hạn + NLP explanation.

### 3.2 Use Cases

| UC | Description |
|---|---|
| UC-01 | Nhập 1 mã (HPG) → full analysis report |
| UC-02 | Nhập list mã (HPG, VCB, FPT) → analysis từng mã |
| UC-03 | Chọn horizon (T+5 only) → focused view |
| UC-04 | Xem SHAP + SMS explanation → lý do khuyến nghị |
| UC-05 | Export report → PDF / JSON / CSV |

### 3.3 Input

```python
class ProfilerRequest:
    tickers           : list[str]      # ["HPG"] or ["HPG","VCB","FPT"]
    horizons          : list[int]      # default [2,3,4,5,7,10,15]
    mode              : str            # "FULL" | "QUICK" | "HORIZON_ONLY"
    as_of_date        : date | None    # None = today
    include_chart_data: bool           # True = return OHLCV + indicator series
    include_money_flow: bool           # True = compute M-CVD + SMS (default True)
```

### 3.4 Output Schema

```python
class TickerProfile:
    ticker          : str
    exchange        : str
    as_of_date      : date
    current_price   : float

    # Signal summary
    overall_signal  : str           # STRONG_BUY|BUY|WATCH|NO_SIGNAL|SELL_SIGNAL
    signal_mode     : str           # MODE_A|MODE_B|MODE_W|MIXED
    mfpm_score      : int
    hmm_state       : str           # STEADY_BULL|TRANSITIONAL|STEADY_BEAR
    gmo_omega       : float
    amd_phase       : str

    # Traditional flow (existing)
    vqs_score       : float
    cvd_whale_net   : int | None    # intraday only
    amf_decision    : str           # PASS|WARN|BLOCK
    amf_flags       : list[str]
    canslim_score   : int
    hurst_exp       : float
    mc_win_prob     : float

    # Large Money Flow (NEW in FR-6)
    sms             : int           # Smart Money Score 0–100
    sms_label       : str           # WHALE_BUYING|WHALE_DISTRIBUTING|MIXED|RETAIL_DRIVEN
    mcvd_5d         : int           # Multi-day CVD 5 sessions (shares net)
    mcvd_trend      : str           # UP|DOWN|FLAT
    stealth_accum   : bool          # Silent accumulation detected
    sector_flow     : str           # INFLOW|NEUTRAL|OUTFLOW for this ticker's sector
    fol_net_5d      : int           # Foreign net buy/sell rolling 5 days
    whale_pct_vol   : float         # % of daily volume from whale ticks

    # Explanation
    horizons        : list[HorizonRecommendation]
    shap_top5       : list[str]
    advisory_vn     : str
    advisory_en     : str
    chart_data      : ChartPayload | None
    audit_id        : str
```

### 3.5 Horizon Recommendation Schema

```python
class HorizonRecommendation:
    horizon_days       : int        # 2,3,4,5,7,10,15
    period_label       : str        # "Ngắn hạn (T+2–T+5)" | "Trung hạn" | "Dài hạn"
    action             : str        # BUY|HOLD|SELL|NO_ACTION
    confidence         : str        # HIGH|MEDIUM|LOW
    entry_price        : float | None
    entry_window       : str | None # "09:30–10:00"|"14:05–14:20"|"ATC 14:43"
    stop_loss          : float | None
    sl_pct             : float | None
    tp1                : float | None
    tp1_pct            : float | None
    tp2                : float | None
    tp2_pct            : float | None
    rr_ratio           : float | None
    expected_hold_days : int | None
    exit_condition     : str
    sms_contribution   : str        # "SMS=82 → LOW_THRESHOLD_ACTIVE" (NEW)
    notes              : str
```

### 3.6 Horizon Mapping

| Horizon | Label | Chiến thuật | Priority Mode |
|---|---|---|---|
| T+2–T+3 | Siêu ngắn hạn | T+2.5 exit window; ATC router chiều T+2 | Mode A hoặc W |
| T+4–T+5 | Ngắn hạn | Full swing: TP1 tại Fib 1.618 hoặc RSI > 65 | Mode A, B, hoặc W |
| T+7–T+10 | Trung hạn | Progressive exit 40+40+20%; trailing stop | Mode B hoặc W |
| T+12–T+15 | Dài hạn | Trailing; H ≥ 0.60 + SMS ≥ 60 bắt buộc | Mode W + Cup&Handle |

### 3.7 Confidence Mapping (Updated for SMS)

| Điều kiện | Confidence |
|---|---|
| MFPM ≥ 70 + AMF=PASS + MC ≥ 0.60 + HMM=STEADY_BULL | HIGH |
| MFPM 50–69 + AMF≠BLOCK + MC ≥ 0.50 | MEDIUM |
| MFPM 35–49 nhưng SMS ≥ 75 + AMF=PASS | MEDIUM (Mode W override) |
| MFPM 35–49 hoặc AMF=WARN | LOW |
| AMF=BLOCK hoặc MFPM < 35 + SMS < 50 | — (NO_ACTION) |

### 3.8 Advisory Template

```
"[TICKER] ([EXCHANGE]) @ [PRICE]:

📊 Dòng tiền: [SMS_LABEL] | SMS=[SMS] | Cá voi [WHALE_PCT]% khối lượng
[AMD_PHASE_DESC]. [PATTERN_DESC]. M-CVD 5 phiên: [MCVD_5D] cổ ([MCVD_TREND]).
[FOREIGN_FLOW_DESC]. Ngành [SECTOR]: [SECTOR_FLOW].
HMM: [HMM_STATE] | Ω=[OMEGA].

→ Khuyến nghị [ACTION] [MODE]: Vào [ENTRY] | SL [SL] (-[SL_PCT]%)
→ TP1 [TP1] (+[TP1_PCT]%) ~ T+[T1] | TP2 [TP2] (+[TP2_PCT]%) ~ T+[T2]
→ R/R = [RR] | MFPM: [SCORE]/120 | MC win: [MCPROB]%
→ Vì sao? [SHAP_TOP3]"

Ví dụ:
"HPG (HOSE) @ 28,500:

📊 Dòng tiền: WHALE_BUYING | SMS=82 | Cá voi 38% khối lượng
AMD: Tích lũy 45 phiên. Wyckoff Spring + 2 nhịp VCP. M-CVD 5 phiên: +1.2M cổ (UP).
NN mua ròng +125K cổ/ngày 5 phiên. Ngành STEEL: INFLOW (dẫn đầu sector).
HMM: STEADY_BULL | Ω=0.55.

→ Khuyến nghị MUA Mode W: Vào 28,500 (14:05–14:20) | SL 26,790 (-6.0%)
→ TP1 31,200 (+9.5%) ~ T+4 | TP2 33,500 (+17.5%) ~ T+10
→ R/R = 2.59 | MFPM: 94/120 | MC win: 63%
→ Vì sao? ✅ SMS whale_net +15 | ✅ M-CVD UP +15 | ✅ Spring Wyckoff +15"
```

---

## 4. FR-2: Market Scanner ("Tìm Mã Để Mua")

### 4.1 Tổng Quan

Scan toàn HOSE + HNX (~830 mã), lọc universe → CAN SLIM → AMF → MFPM, trả danh sách xếp hạng. Scanner có thêm **Money Flow filter** từ FR-6.

### 4.2 Use Cases

| UC | Description |
|---|---|
| UC-11 | Daily Scan → top 10–20 STRONG_BUY trong ngày |
| UC-12 | Filter theo sector + SMS ≥ 60 (chỉ mã có dòng tiền mạnh) |
| UC-13 | Custom filter: MFPM ≥ 60, AMD=ACCUMULATION, stealth_accum=True |
| UC-14 | Scan + compare với existing watchlist |
| UC-15 | "Whale Watch" scan: chỉ mã Mode W (SMS top tier) |

### 4.3 Scanner Pipeline (Updated)

```
Stage 1: Universe Build      ~830 → 200–280 (liquidity + price + data quality)
Stage 2: CAN SLIM Filter     200–280 → 60–80 watchlist
Stage 3: Money Flow Pre-filter  60–80 → ~40–60 (sms ≥ 30, sector_flow ≠ OUTFLOW)
Stage 4: AMF Pre-conditions  40–60 → ~30–50 (HMM≠BEAR, AMF≠BLOCK)
Stage 5: MFPM Scoring        30–50 → ranked list
Stage 6: Horizon Projection  Top 20 → full HorizonRecommendation per ticker
Stage 7: Risk-Adj Ranking    risk_adjusted_weights() → final order
```

### 4.4 ScanRequest / ScanResult

```python
class ScanRequest:
    date            : date | None
    sector_filter   : list[str] | None   # ["BANK","STEEL","REALESTATE"]
    min_mfpm        : int                # default 50
    min_sms         : int                # NEW: default 30; set 60 for Whale Watch
    amd_phases      : list[str]          # default ["ACCUMULATION","MARKUP"]
    stealth_only    : bool               # NEW: True = only stealth_accum=True tickers
    max_results     : int                # default 20
    include_profiles: bool

class ScanItem:
    rank            : int
    ticker          : str
    mfpm_score      : int
    sms             : int                # NEW
    sms_label       : str                # NEW
    overall_signal  : str
    signal_mode     : str                # NEW: MODE_A|MODE_B|MODE_W
    amd_phase       : str
    stealth_accum   : bool               # NEW
    key_triggers    : list[str]
    entry_price     : float
    sl              : float
    tp1             : float
    rr              : float
    one_line_reason : str
    profile         : TickerProfile | None
```

### 4.5 Performance Targets

| Stage | Target |
|---|---|
| Universe + CAN SLIM (Stage 1–2) | ≤ 5s |
| Full scan Stage 1–6 (200 mã) | ≤ 75s (+ 15s so với trước do Stage 3 money flow) |
| Top-20 full profiles | ≤ 90s |
| Watchlist rescan 60 mã | ≤ 25s |

### 4.6 Scheduled Scans

| Time | Mode |
|---|---|
| 08:30 | Pre-market: close T-1 + overnight news + M-CVD overnight estimate |
| 09:30 | Post-ATO + gap analysis + sector flow update |
| 14:00 | Afternoon: intraday CVD update → refresh SMS |
| 15:00 | Post-close: end-of-day M-CVD update; prepare T+1 watchlist |

---

## 5. FR-3: Audit Trail

### 5.1 Event Types

```python
class AuditEventType(Enum):
    # Signal lifecycle
    SIGNAL_GENERATED, SIGNAL_REJECTED, SIGNAL_EXPIRED
    SIGNAL_UPGRADED, SIGNAL_DOWNGRADED

    # Money flow events (NEW)
    WHALE_ACCUMULATION_DETECTED  = "dtl.whale_accum"
    WHALE_DISTRIBUTION_WARNING   = "dtl.whale_dist"
    STEALTH_ACCUM_DETECTED       = "dtl.stealth"
    SECTOR_ROTATION_DETECTED     = "dtl.sector_rotation"
    SMS_THRESHOLD_CROSSED        = "dtl.sms_threshold"

    # Data events
    DATA_FETCHED, DATA_CACHE_HIT, DATA_CACHE_MISS
    DATA_STALE_DETECTED, DATA_FETCH_FAILED

    # Manipulation events
    AMF_BLOCK, AMF_WARN, AMF_PASS

    # Backtest
    BACKTEST_STARTED, BACKTEST_COMPLETED, BACKTEST_TRADE

    # Scanner
    SCAN_STARTED, SCAN_COMPLETED, SCAN_STAGE_RESULT

    # User actions
    USER_PROFILER_RUN, USER_SCANNER_RUN, USER_MONEYFLOW_RUN
    USER_EXPORT, USER_WATCHLIST_ADD

    # System
    HMM_REFIT, THRESHOLD_CALIBRATE, CONFIG_CHANGE
    MCVD_DAILY_UPDATE           = "system.mcvd_update"
```

### 5.2 AuditRecord Schema

```python
class AuditRecord:
    audit_id         : str           # UUID v4
    event_type       : AuditEventType
    timestamp        : datetime      # UTC+7
    session_id       : str
    ticker           : str | None
    exchange         : str | None
    inputs           : dict          # full inputs snapshot
    outputs          : dict          # full outputs snapshot
    decision_path    : list[str]     # ["PRE_COND_OK","AMF_PASS","SMS=82","MODE_W","STRONG_BUY"]
    rejection_reason : str | None
    duration_ms      : int
    data_sources     : list[str]
    cache_hits       : int
    api_calls        : int
```

### 5.3 Audit UI Features

| Feature | Description |
|---|---|
| Timeline view | Chronological filter: date range, event type, ticker |
| Signal drill-down | Full input state, MFPM + SMS breakdown, AMF flags |
| Money flow trace | Click → xem M-CVD history, SMS components, sector flow |
| Rejection Pareto | Top reasons signals bị reject (bar chart) |
| Performance correlation | Signal vs actual price T+5, T+10 |
| Export | CSV / JSON / Excel |

### 5.4 Retention Policy

```
Hot   (DuckDB):  30 ngày — full detail, queryable
Warm  (Parquet): 6 tháng — compressed
Cold  (zip):     2 năm  — monthly archive
```

---

## 6. FR-4: Performance Optimization

### 6.1 Async Data Fetching

```python
async def fetch_batch_ohlcv(
    tickers: list[str], resolution: str = "D"
) -> dict[str, pd.DataFrame]:
    """Max 10 concurrent requests (SSI rate limit)."""
    semaphore = asyncio.Semaphore(10)
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_single_with_cache(t, resolution, session, semaphore)
                 for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return {t: r for t, r in zip(tickers, results) if not isinstance(r, Exception)}
```

### 6.2 DuckDB TTL Policy

| Table | TTL |
|---|---|
| `ohlcv_daily` | 4h intraday / 24h after 15:30 |
| `ohlcv_5m` | 5 minutes |
| `indicators_daily` | 4h |
| `money_flow_daily` | 24h (update post-close) |
| `mcvd_history` | Permanent (append-only) |
| `sector_flow` | 24h |
| `canslim_scores` | 24h |
| `scan_results` | 30 minutes |
| `signal_history` | Permanent |
| `order_book_snapshot` | 10 seconds |
| `audit_log` | Rolling 30-day hot |

### 6.3 Parallel MFPM Scoring

```python
from concurrent.futures import ProcessPoolExecutor, as_completed

def parallel_mfpm_score(tickers: list[str], df_map: dict) -> list[dict]:
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(score_single_ticker, t, df_map[t]): t
                   for t in tickers}
        results = []
        for future in as_completed(futures):
            try:
                results.append(future.result(timeout=5))
            except Exception as e:
                audit_log(SIGNAL_REJECTED, ticker=futures[future], reason=str(e))
    return sorted(results, key=lambda x: x["mfpm_score"], reverse=True)
```

### 6.4 Computation Deferral

- **Full CVD (tick-level):** deferred; computed only on user-opened full profile
- **M-CVD 5d:** computed post-close (15:30) and cached until next close  
- **Sector flow:** batch compute once per daily scan; cached 24h
- **Hurst + MC:** memoized per session with input hash
- **SMS:** computed incrementally when any input component changes

### 6.5 Performance SLAs

| Operation | P50 | P95 | P99 |
|---|---|---|---|
| Single ticker full profile (with SMS) | 3s | 6s | 12s |
| Single ticker quick profile | 0.5s | 1.5s | 3s |
| Daily scan 200 mã | 35s | 75s | 100s |
| Watchlist scan 60 mã | 10s | 25s | 35s |
| Money flow dashboard refresh | 5s | 12s | 20s |
| Backtest 1 ticker × 3 years | 5s | 15s | 30s |
| Audit query 30 days | 0.3s | 1s | 2s |
| **Data ingestion: network hop** (SSI → Rust daemon) | ≤ 3.9 ms | 8 ms | 20 ms |
| **Data ingestion: end-to-end** (SSI response → DuckDB write) | < 100 ms | 200 ms | 500 ms |

---

## 7. FR-5: Backtesting Engine

### 7.1 Use Cases

| UC | Description |
|---|---|
| UC-31 | Backtest 1 mã × 3 năm → P&L, win rate, drawdown |
| UC-32 | Walk-forward (2Y train / 6M test) → OOS metrics |
| UC-33 | Portfolio backtest Top-10 watchlist |
| UC-34 | Parameter sensitivity (MFPM threshold / SMS threshold) |
| UC-35 | Mode A vs Mode B vs Mode W performance comparison |
| UC-36 | Stress test: 2022 crash scenario (VNI -50%) |

### 7.2 BacktestRequest / BacktestResult

```python
class BacktestRequest:
    tickers          : list[str]
    start_date, end_date: date
    initial_capital  : float             # default 1,000,000,000 VND
    mode             : str               # "SINGLE"|"PORTFOLIO"|"WALK_FORWARD"
    train_years      : int               # default 2
    test_months      : int               # default 6
    mfpm_threshold   : int               # default 50
    sms_threshold    : int               # NEW: default 0 (disabled); 60 = Mode W only
    entry_modes      : list[str]         # ["MODE_A","MODE_B","MODE_W"]
    enable_amf       : bool
    kelly_enabled    : bool
    max_positions    : int               # default 5

class BacktestResult:
    total_return_pct, annualized_return
    win_rate         : float             # target ≥ 55%
    avg_rr_ratio     : float             # target ≥ 2.0
    max_drawdown_pct : float             # target ≤ 25%
    sharpe_ratio     : float             # target ≥ 1.2
    calmar_ratio, sortino_ratio
    total_trades, winning_trades, losing_trades
    avg_hold_days, avg_win_pct, avg_loss_pct
    max_consecutive_loss : int

    # Mode breakdown (NEW)
    mode_a_trades, mode_a_win_rate : int, float
    mode_b_trades, mode_b_win_rate : int, float
    mode_w_trades, mode_w_win_rate : int, float  # Follow-the-Whale performance

    # VN-specific
    t25_forced_exits, lock_san_hits, circuit_breaker_hits : int
    mc_rejected_signals, amf_blocked_signals : int

    # Walk-forward
    is_win_rate, oos_win_rate : float
    overfitting_flag : bool              # True if OOS < IS × 0.85

    trades           : list[BacktestTrade]

class BacktestTrade:
    ticker, entry_date, entry_price, entry_mode, qty
    sl, tp1, tp2, exit_date, exit_price
    exit_reason      : str               # "TP1"|"TP2"|"SL"|"T25_FORCED"|"TRAILING"
    pnl_vnd, pnl_pct, hold_days
    mfpm_at_entry    : int
    sms_at_entry     : int               # NEW
    amf_at_entry     : str
    triggers_at_entry: list[str]
```

### 7.3 Simulation Fidelity

| Requirement | Spec |
|---|---|
| T+2.5 constraint | Sell only from 13:00 day T+2; danger window 12:45–13:15 |
| Lot size | Round down to 100-share lots; reject qty < 100 |
| Commission | Buy 0.15%, Sell 0.25%, min 1,000 VND; Sell tax 0.1% |
| Slippage | VN30 0.1% / Midcap 0.3% / Smallcap 0.7% |
| Lock sàn | 2% probability on close = floor price |
| Point-in-time | EPS available only after `report_date + 45d` |
| Ex-dividend | Price adjusted via EP-11 corporate actions |
| Circuit breaker | Close ≥ ceiling×0.99 → reject buy |
| M-CVD backtest | Proxy from daily OBV trend (full tick data not available historically) |
| **MTL partial fill** | Khi lệnh MTL không fill đủ quantity: phần còn lại tự động chuyển thành LO tại giá khớp cuối; không tái-submit; log `PARTIAL_FILL` + tính slippage trên phần filled only |
| **PCA stocks** | Tickers đang trong Periodic Continuous Auction (KRX) bị loại khỏi auto-signal generation; giá khớp theo từng round auction 15 phút; hiển thị nhãn `[PCA]` trong UI |
| **KRX auction priority** | ATO/ATC chạy trong auction phase riêng biệt — không cạnh tranh time-priority với LO continuous. Trong continuous session: earlier LO at same price takes priority (standard price-time). |

### 7.4 Output Visualizations

1. Equity curve vs VNI benchmark (all modes overlaid)
2. Drawdown chart (highlight max period)
3. Monthly returns heatmap
4. Mode A / B / W comparison bar chart (win rate, avg PnL)  ← NEW
5. Walk-forward IS vs OOS bar chart
6. Parameter sensitivity heatmap (MFPM threshold × SMS threshold)  ← NEW

---

## 8. FR-6: Dòng Tiền Lớn — Large Money Flow

> **Triết lý:** *"Data có thể bị bịa, nhưng dòng tiền thật không thể giả mãi. Tay to phải mua thật, bán thật — để lại dấu vết trong microstructure. TradingOS đọc dấu vết đó và TRADE THEO."*
> — TradingOS-Alpha-Proposal-v1.0.md, line 750

### 8.1 Tổng Quan

FR-6 chuyển dòng tiền từ vai trò **phòng thủ** (AMF block manipulation) sang vai trò **tấn công**: tạo tín hiệu giao dịch chủ động dựa trên việc phát hiện và đi theo dòng tiền tổ chức.

**Hai chế độ của DTL module:**

| Chế độ | Mô tả | Khi nào dùng |
|---|---|---|
| **Confirm mode** | SMS xác nhận thêm vào MFPM Mode A/B | Mặc định, luôn bật |
| **Drive mode (Mode W)** | SMS đủ mạnh để TỰ TẠO signal, không cần MFPM ≥ 50 | Khi SMS ≥ 70 + AMF=PASS + HMM≠BEAR |

### 8.2 FR-6.1 — Multi-Day CVD Tracking (M-CVD)

**Vấn đề:** CVD hiện tại trong proposal chỉ là intraday (1 phiên tick data). Tổ chức tích lũy thường diễn ra over **nhiều tuần**, không thể thấy qua 1 phiên.

**Giải pháp:** `compute_multiday_whale_flow()` tổng tích lũy whale_net theo ngày.

```python
def compute_multiday_whale_flow(
    daily_flow_df: pd.DataFrame,
    lookback_days: int = 20,
) -> dict:
    """
    Tổng tích lũy whale_net qua N phiên.

    Inputs:
      daily_flow_df: DataFrame có cột ['date','whale_net','fol_net','obv','close']
      — Nếu có tick data: whale_net từ compute_cvd()
      — Nếu không có tick data: proxy = OBV delta × (close_pct_rank > 0.5)

    Returns:
      mcvd_5d   : int   — tổng net whale 5 phiên gần nhất (cổ)
      mcvd_20d  : int   — tổng net whale 20 phiên
      mcvd_slope: float — linear regression slope của whale_net series (tăng = accumulating)
      mcvd_trend: str   — "UP" | "DOWN" | "FLAT" (|slope| < threshold → FLAT)
      mcvd_vs_price: str — "CONFIRM" (cùng chiều) | "DIVERGE_BULLISH" | "DIVERGE_BEARISH"
      consistency : float — % phiên có whale_net > 0 trong lookback (0–1)
    """
    if len(daily_flow_df) < lookback_days:
        return {"mcvd_5d": 0, "mcvd_20d": 0, "mcvd_trend": "FLAT",
                "mcvd_vs_price": "UNKNOWN", "consistency": 0.5}

    recent = daily_flow_df.tail(lookback_days)
    whale_series = recent['whale_net'].fillna(0)

    mcvd_5d   = int(whale_series.tail(5).sum())
    mcvd_20d  = int(whale_series.sum())

    # Linear regression slope of whale_net over lookback
    x = np.arange(len(whale_series))
    slope, _ = np.polyfit(x, whale_series.values, 1)
    avg_daily_vol = recent['close'].mean() * 500_000   # rough avg turnover
    slope_normalized = slope / max(avg_daily_vol / lookback_days, 1)

    if slope_normalized > 0.01:
        mcvd_trend = "UP"
    elif slope_normalized < -0.01:
        mcvd_trend = "DOWN"
    else:
        mcvd_trend = "FLAT"

    # Price-CVD agreement
    price_slope = recent['close'].iloc[-1] / recent['close'].iloc[0] - 1
    if (mcvd_trend == "UP" and price_slope > 0) or (mcvd_trend == "DOWN" and price_slope < 0):
        mcvd_vs_price = "CONFIRM"
    elif mcvd_trend == "UP" and price_slope < 0:
        mcvd_vs_price = "DIVERGE_BULLISH"   # accumulation phase — whale mua nhưng giá còn xuống
    elif mcvd_trend == "DOWN" and price_slope > 0:
        mcvd_vs_price = "DIVERGE_BEARISH"   # distribution: whale bán nhưng giá còn tăng → cảnh báo
    else:
        mcvd_vs_price = "UNKNOWN"

    consistency = float((whale_series > 0).sum() / len(whale_series))

    return {
        "mcvd_5d"       : mcvd_5d,
        "mcvd_20d"      : mcvd_20d,
        "mcvd_slope"    : round(slope_normalized, 4),
        "mcvd_trend"    : mcvd_trend,
        "mcvd_vs_price" : mcvd_vs_price,
        "consistency"   : round(consistency, 2),
    }
```

**Proxy khi không có tick data (Phase 1–2):**

```python
def proxy_whale_net_from_daily(df: pd.DataFrame) -> pd.Series:
    """
    Estimate whale_net từ OHLCV daily (không cần tick data).
    Logic: ngày volume cao + giá tăng + close ở top range = whale buy proxy.
    """
    c = df.copy()
    c['range_pct'] = (c['close'] - c['low']) / (c['high'] - c['low'] + 1e-9)
    c['z_vol'] = (c['volume'] - c['volume'].rolling(20).mean()) / \
                 (c['volume'].rolling(20).std() + 1e-9)
    # Proxy: nếu z_vol cao + giá đóng ở phần trên range → buy volume
    c['whale_net_proxy'] = c.apply(
        lambda r: int(r['volume'] * 0.3 * np.sign(r['range_pct'] - 0.5))
        if r['z_vol'] > 0.5 else 0,
        axis=1,
    )
    return c['whale_net_proxy']
```

### 8.3 FR-6.2 — Smart Money Score (SMS)

**Mục tiêu:** Tổng hợp tất cả dòng tiền signals vào **1 số duy nhất 0–100** để ranking và quyết định Mode W.

```python
def compute_smart_money_score(
    ticker: str,
    df: pd.DataFrame,
    daily_flow_df: pd.DataFrame,
    order_book: dict | None,
    quote: dict,
) -> dict:
    """
    Composite Smart Money Score (SMS) 0–100.

    Components:
      1. M-CVD Trend (0–25):    multi-day whale accumulation
      2. VQS Score   (0–20):    volume quality (OFI + OBV + Price-Vol)
      3. FOL Net     (0–20):    foreign investor 5-day rolling net
      4. OBV Slope   (0–15):    on-balance volume momentum
      5. AMD Confirm (0–10):    phase alignment (ACCUMULATION/MARKUP = bonus)
      6. Intraday CVD(0–10):    today's intraday whale buying (if tick data available)
    Total max = 100

    Returns:
      sms          : int 0–100
      sms_label    : WHALE_BUYING|WHALE_DISTRIBUTING|RETAIL_DRIVEN|MIXED
      components   : dict (each component score, for SHAP-like explanation)
    """
    comps = {}

    # --- Component 1: M-CVD Trend (0–25) ---
    mcvd = compute_multiday_whale_flow(daily_flow_df, lookback_days=20)
    if mcvd["mcvd_trend"] == "UP" and mcvd["consistency"] >= 0.60:
        comps["mcvd"] = 25
    elif mcvd["mcvd_trend"] == "UP":
        comps["mcvd"] = 15
    elif mcvd["mcvd_trend"] == "FLAT":
        comps["mcvd"] = 5
    elif mcvd["mcvd_trend"] == "DOWN" and mcvd["mcvd_vs_price"] == "DIVERGE_BEARISH":
        comps["mcvd"] = 0   # distribution warning
    else:
        comps["mcvd"] = 0

    # --- Component 2: VQS (0–20) ---
    vqs_result = volume_quality_score(df, order_book or {})
    vqs = vqs_result["vqs_score"]
    comps["vqs"] = max(0, int((vqs + 1) / 2 * 20))   # [-1,+1] → [0,20]

    # --- Component 3: FOL Net 5-day (0–20) ---
    fol_net_5d = daily_flow_df['fol_net'].tail(5).sum() if 'fol_net' in daily_flow_df else 0
    avg_vol = df['volume'].tail(20).mean()
    fol_ratio = fol_net_5d / max(avg_vol * 5, 1)  # normalize by 5-day trading vol
    if fol_ratio > 0.05:
        comps["fol"] = 20
    elif fol_ratio > 0.02:
        comps["fol"] = 12
    elif fol_ratio > 0:
        comps["fol"] = 6
    elif fol_ratio < -0.02:
        comps["fol"] = 0    # foreign selling
    else:
        comps["fol"] = 4    # neutral

    # --- Component 4: OBV Slope (0–15) ---
    if len(df) >= 10:
        obv_slope = (df['OBV'].iloc[-1] - df['OBV'].iloc[-10]) / max(abs(df['OBV'].iloc[-10]), 1)
        if obv_slope > 0.05:
            comps["obv"] = 15
        elif obv_slope > 0.01:
            comps["obv"] = 8
        elif obv_slope < -0.05:
            comps["obv"] = 0
        else:
            comps["obv"] = 4
    else:
        comps["obv"] = 4

    # --- Component 5: AMD Phase Alignment (0–10) ---
    amd_phase = daily_flow_df.get('amd_phase', ["RANGING"])[-1] \
                if hasattr(daily_flow_df, 'get') else "RANGING"
    amd_bonus = {"ACCUMULATION": 10, "MARKUP": 8, "RANGING": 4,
                 "DISTRIBUTION": 0, "MARKDOWN": 0}
    comps["amd"] = amd_bonus.get(amd_phase, 4)

    # --- Component 6: Intraday CVD (0–10) ---
    cvd_today = daily_flow_df.get('cvd_today', None)
    if cvd_today is not None:
        comps["cvd_today"] = 10 if cvd_today > 0 else (5 if cvd_today == 0 else 0)
    else:
        comps["cvd_today"] = 5  # unknown → neutral

    sms = sum(comps.values())
    sms = max(0, min(100, sms))

    # Label
    if sms >= 70 and comps["mcvd"] >= 20:
        label = "WHALE_BUYING"
    elif sms <= 25 or (mcvd["mcvd_vs_price"] == "DIVERGE_BEARISH" and comps["mcvd"] == 0):
        label = "WHALE_DISTRIBUTING"
    elif comps["vqs"] >= 15 and comps["obv"] >= 8:
        label = "MIXED"
    else:
        label = "RETAIL_DRIVEN"

    return {
        "sms"        : sms,
        "sms_label"  : label,
        "components" : comps,
        "mcvd_detail": mcvd,
    }
```

**SMS Integration vào MFPM scoring:**

| SMS Range | Label | MFPM Adjustment |
|---|---|---|
| SMS ≥ 75 + MCVD=UP | WHALE_BUYING | +20 |
| SMS 60–74 | STRONG FLOW | +12 |
| SMS 40–59 | MODERATE FLOW | +5 |
| SMS 20–39 | WEAK FLOW | 0 |
| SMS < 20 | RETAIL/DIST | -10 |
| `mcvd_vs_price = DIVERGE_BEARISH` | DISTRIBUTION | -25 (BLOCK candidate) |

### 8.4 FR-6.3 — Stealth Accumulation Detection

**Định nghĩa:** Tổ chức tích lũy bí mật — mua từng ngày nhỏ để không tạo breakout giả, trong khi giá đứng yên hoặc giảm nhẹ. Đây là **pre-spring phase**, thường đi trước Spring 5–15 phiên.

```python
def detect_stealth_accumulation(
    df: pd.DataFrame,
    daily_flow_df: pd.DataFrame,
    lookback: int = 15,
) -> dict:
    """
    Phát hiện tích lũy bí mật.

    Điều kiện đồng thời:
      1. Giá: trong biên độ hẹp (ATR/Price < 1.5% trong lookback phiên)
      2. M-CVD: trend UP hoặc DIVERGE_BULLISH (whale mua, giá chưa phản ánh)
      3. OBV: tăng ≥ 3% trong lookback
      4. Volume distribution: volume trung bình không bất thường (Z_vol < 1.0)
         — tránh nhầm với bơm nhanh
      5. AMD phase: ACCUMULATION hoặc RANGING (không áp dụng trong MARKUP)

    Returns:
      detected    : bool
      confidence  : str — HIGH|MEDIUM|LOW
      days_active : int — bao nhiêu phiên đã tích lũy
      est_target  : float | None — ước tính vùng giá breakout
      signal_text : str — mô tả ngắn
    """
    if len(df) < lookback:
        return {"detected": False, "confidence": "LOW", "days_active": 0}

    recent = df.tail(lookback)

    # Cond 1: Price trong biên độ hẹp
    atr_avg = recent['ATR14'].mean() if 'ATR14' in recent else (
        (recent['high'] - recent['low']).mean()
    )
    price_range_pct = atr_avg / recent['close'].mean()
    tight_range = price_range_pct < 0.015

    # Cond 2: M-CVD trend
    mcvd = compute_multiday_whale_flow(daily_flow_df, lookback_days=lookback)
    whale_accumulating = mcvd["mcvd_trend"] in ("UP",) or \
                         mcvd["mcvd_vs_price"] == "DIVERGE_BULLISH"

    # Cond 3: OBV rising
    obv_change = (recent['OBV'].iloc[-1] - recent['OBV'].iloc[0]) / \
                 max(abs(recent['OBV'].iloc[0]), 1)
    obv_rising = obv_change > 0.03

    # Cond 4: No volume spike = no pump
    z_vol_max = recent['Z_vol'].max() if 'Z_vol' in recent.columns else 1.0
    no_spike = z_vol_max < 1.5

    # Cond 5: AMD phase
    amd_ok = daily_flow_df.get('amd_phase', ["RANGING"])[-1] \
             in ("ACCUMULATION", "RANGING") \
             if hasattr(daily_flow_df, 'get') else True

    detected = tight_range and whale_accumulating and obv_rising and amd_ok

    if detected:
        score = sum([tight_range, whale_accumulating, obv_rising, no_spike, amd_ok])
        confidence = "HIGH" if score == 5 else ("MEDIUM" if score >= 3 else "LOW")

        # Rough target: previous swing high or ATR × 8 projection
        est_target = df['high'].tail(60).max() if len(df) >= 60 else None

        # Count active days
        days_active = 0
        for i in range(len(df) - 1, -1, -1):
            row = df.iloc[i]
            if 'Z_vol' in df.columns and df['Z_vol'].iloc[i] < 1.5:
                days_active += 1
            else:
                break

        sig = (f"Tích lũy bí mật {days_active} phiên: OBV +{obv_change*100:.1f}%, "
               f"M-CVD {mcvd['mcvd_trend']}, giá hẹp {price_range_pct*100:.1f}%ATR")
        return {"detected": True, "confidence": confidence,
                "days_active": days_active, "est_target": est_target,
                "signal_text": sig, "mcvd_detail": mcvd}

    return {"detected": False, "confidence": "LOW", "days_active": 0}
```

**Stealth Accum trong MFPM:**

| Signal | MFPM Adj |
|---|---|
| `stealth_accum=True, confidence=HIGH` | +15 (bonus ACCUMULATION pre-signal) |
| `stealth_accum=True, confidence=MEDIUM` | +8 |
| `stealth_accum=False` | 0 |

### 8.5 FR-6.4 — Sector Money Flow Rotation

**Mục tiêu:** Xác định ngành nào đang nhận dòng tiền tổ chức → ưu tiên scan mã trong ngành đó.

```python
def detect_sector_rotation(
    sector_ohlcv_map: dict[str, pd.DataFrame],   # sector_name → index/ETF OHLCV
    sector_sms_map: dict[str, list[float]],       # sector → list of ticker SMS
    lookback: int = 10,
) -> dict:
    """
    Phân tích sector rotation.

    Inputs:
      sector_ohlcv_map: sector ETF/index data (VD: VNFin, VNEstate, VNSteel...)
      sector_sms_map  : average SMS của top-10 tickers trong mỗi ngành

    Returns:
      rankings: list[dict] — sorted by inflow_score desc
        {sector, inflow_score, sms_avg, momentum_5d, flow_status}
      hot_sectors   : list[str]  — top 3 ngành nhận inflow
      cold_sectors  : list[str]  — đáy 3 ngành outflow
      rotation_phase: str — "RISK_ON"|"RISK_OFF"|"ROTATION"|"MIXED"
    """
    rankings = []
    for sector, df in sector_ohlcv_map.items():
        if len(df) < lookback:
            continue

        # Sector price momentum
        mom_5d = df['close'].iloc[-1] / df['close'].iloc[-5] - 1

        # Sector OBV slope
        obv_slope = (df['OBV'].iloc[-1] - df['OBV'].iloc[-10]) / \
                    max(abs(df['OBV'].iloc[-10]), 1) if len(df) >= 10 else 0

        # Average SMS of tickers in sector
        sms_scores = sector_sms_map.get(sector, [50])
        sms_avg = sum(sms_scores) / len(sms_scores)

        inflow_score = (mom_5d * 40) + (obv_slope * 30) + ((sms_avg - 50) / 50 * 30)
        inflow_score = max(-100, min(100, inflow_score * 100))

        if inflow_score >= 20:
            flow_status = "INFLOW"
        elif inflow_score <= -20:
            flow_status = "OUTFLOW"
        else:
            flow_status = "NEUTRAL"

        rankings.append({
            "sector": sector, "inflow_score": round(inflow_score, 1),
            "sms_avg": round(sms_avg, 1), "momentum_5d": round(mom_5d * 100, 2),
            "flow_status": flow_status,
        })

    rankings.sort(key=lambda x: x["inflow_score"], reverse=True)
    hot_sectors  = [r["sector"] for r in rankings[:3] if r["flow_status"] == "INFLOW"]
    cold_sectors = [r["sector"] for r in rankings[-3:] if r["flow_status"] == "OUTFLOW"]

    # Classify rotation phase
    inflow_count  = sum(1 for r in rankings if r["flow_status"] == "INFLOW")
    outflow_count = sum(1 for r in rankings if r["flow_status"] == "OUTFLOW")
    if inflow_count >= len(rankings) * 0.6:
        rotation_phase = "RISK_ON"
    elif outflow_count >= len(rankings) * 0.6:
        rotation_phase = "RISK_OFF"
    elif hot_sectors and cold_sectors:
        rotation_phase = "ROTATION"
    else:
        rotation_phase = "MIXED"

    return {
        "rankings"      : rankings,
        "hot_sectors"   : hot_sectors,
        "cold_sectors"  : cold_sectors,
        "rotation_phase": rotation_phase,
    }
```

**Sector Flow Integration vào Scanner:**

- Scanner Stage 3 mới: nếu `sector_flow = OUTFLOW` → bỏ qua toàn bộ mã trong ngành đó
- Nếu `sector_flow = INFLOW` → cộng +5 vào MFPM tiền final ranking
- Market Context Banner trên UI hiển thị sector rotation heatmap

### 8.6 FR-6.5 — Follow-the-Whale Strategy (Mode W)

**Mode W** là chiến lược entry hoàn toàn dựa trên dòng tiền tổ chức — không cần MFPM ≥ 50 nếu SMS đủ mạnh.

#### Pre-conditions Mode W (thay thế Mode A/B pre-conditions)

| Cond | Condition | Bắt buộc? |
|---|---|---|
| W-1 | SMS ≥ 70 | ✅ |
| W-2 | M-CVD trend = UP + consistency ≥ 0.55 | ✅ |
| W-3 | AMF decision = PASS (không được BLOCK) | ✅ |
| W-4 | HMM state ≠ STEADY_BEAR | ✅ |
| W-5 | AMD phase = ACCUMULATION hoặc MARKUP | ✅ |
| W-6 | Stealth accum OR intraday CVD whale_net > 0 | ✅ (ít nhất 1) |
| W-7 | Sector flow ≠ OUTFLOW | ✅ |
| W-8 | Circuit breaker: FOL status ≠ ROOM_DAY | Khuyến nghị |

#### Mode W Scoring Table

| Factor | Max | Logic |
|---|---|---|
| SMS component 1: M-CVD score | 25 | Từ `sms_components["mcvd"]` |
| SMS component 2: VQS | 20 | Từ `sms_components["vqs"]` |
| SMS component 3: FOL net 5d | 20 | Từ `sms_components["fol"]` |
| SMS component 4: OBV slope | 15 | Từ `sms_components["obv"]` |
| SMS component 5: AMD align | 10 | Từ `sms_components["amd"]` |
| SMS component 6: Intraday CVD | 10 | Từ `sms_components["cvd_today"]` |
| Stealth Accum HIGH | +10 bonus | nếu `stealth_accum=True, confidence=HIGH` |
| Sector INFLOW | +5 bonus | nếu `sector_flow=INFLOW` |
| Delta Divergence (BEARISH) | -30 veto | `mcvd_vs_price=DIVERGE_BEARISH` → block |
| **TOTAL MAX** | **115** | — |

**Threshold Mode W:**

| Score | Signal |
|---|---|
| ≥ 85 | STRONG_BUY (Mode W) |
| 70–84 | BUY (Mode W) |
| 55–69 | WATCH (Mode W candidate, thêm 1 phiên xác nhận) |
| < 55 | NO_ACTION trong Mode W |

#### Entry/SL/TP trong Mode W

```python
def mode_w_entry_params(df: pd.DataFrame, sms_result: dict) -> dict:
    """
    Entry params cho Mode W (Follow-the-Whale).
    Entry: vào gần support gần nhất + SL dưới swing low gần nhất.
    TP: dựa trên stealth_accum est_target hoặc ATR × 8.
    """
    c = df.iloc[-1]
    atr = c.get('ATR14', (df['high'] - df['low']).tail(14).mean())

    # Entry: giá hiện tại hoặc limit tại EMA9 nếu giá đang trên EMA9
    entry = float(c['close'])
    ema9  = c.get('EMA9', entry)
    if entry > ema9 * 1.01:  # giá đang cao, chờ pullback nhẹ
        entry = round(ema9 * 1.005, -1)  # round to 100

    sl    = round(entry - atr * 1.5, -1)  # 1.5 ATR stop
    sl_pct = (sl - entry) / entry * 100

    # TP based on est_target if stealth detected
    stealth = sms_result.get("stealth_detail", {})
    est_target = stealth.get("est_target", None)
    if est_target and est_target > entry * 1.05:
        tp1 = round(entry + (est_target - entry) * 0.5, -1)
        tp2 = round(est_target, -1)
    else:
        tp1 = round(entry + atr * 4, -1)
        tp2 = round(entry + atr * 8, -1)

    rr = abs((tp1 - entry) / (sl - entry)) if sl != entry else 0

    return {"entry": entry, "sl": sl, "sl_pct": round(sl_pct, 2),
            "tp1": tp1, "tp2": tp2, "rr": round(rr, 2)}
```

### 8.7 FR-6.6 — Whale Distribution Early Warning

**Mục tiêu:** Cảnh báo sớm khi tổ chức bắt đầu **xả hàng** — trước khi giá drop mạnh.

```python
def detect_whale_distribution(
    df: pd.DataFrame,
    daily_flow_df: pd.DataFrame,
    lookback: int = 10,
) -> dict:
    """
    Phát hiện phân phối của tay to.

    Signals:
      1. M-CVD DIVERGE_BEARISH: price UP nhưng whale_net tổng < 0
      2. OBV turning negative: OBV slope đổi từ dương sang âm
      3. VSA: no_demand bars (volume thấp khi test breakout)
      4. AMD phase = DISTRIBUTION
      5. FOL 5d: foreign net sell > -2% daily volume

    Returns:
      warning_level: str — NONE|WATCH|CAUTION|SELL_SIGNAL
      flags        : list[str]
      explanation  : str
    """
    flags = []
    score = 0

    mcvd = compute_multiday_whale_flow(daily_flow_df, lookback_days=lookback)

    if mcvd["mcvd_vs_price"] == "DIVERGE_BEARISH":
        flags.append("DELTA_DIVERGE_BEARISH")
        score += 3

    obv_now  = df['OBV'].iloc[-1]
    obv_prev = df['OBV'].iloc[-5] if len(df) >= 5 else obv_now
    if obv_prev > 0 and (obv_now - obv_prev) / abs(obv_prev) < -0.03:
        flags.append("OBV_NEGATIVE_TURN")
        score += 2

    amd_phase = daily_flow_df.get('amd_phase', ["RANGING"])[-1] \
                if hasattr(daily_flow_df, 'get') else "RANGING"
    if amd_phase == "DISTRIBUTION":
        flags.append("AMD_DISTRIBUTION")
        score += 2

    fol_net_5d = daily_flow_df['fol_net'].tail(5).sum() \
                 if 'fol_net' in daily_flow_df else 0
    avg_vol = df['volume'].tail(20).mean()
    if fol_net_5d < -avg_vol * 0.02 * 5:
        flags.append("FOREIGN_NET_SELL_5D")
        score += 1

    if score >= 5:
        level = "SELL_SIGNAL"
    elif score >= 3:
        level = "CAUTION"
    elif score >= 1:
        level = "WATCH"
    else:
        level = "NONE"

    explanation = ""
    if level != "NONE":
        explanation = (f"⚠️ Cảnh báo phân phối: {', '.join(flags)}. "
                       f"Cân nhắc thu hẹp position hoặc dời SL lên breakeven.")

    return {"warning_level": level, "flags": flags, "explanation": explanation,
            "score": score}
```

**Distribution Warning Integration:**

- Nếu `warning_level=SELL_SIGNAL` → override tất cả BUY signals → hiện **SELL/EXIT ALERT** trên UI
- Nếu `warning_level=CAUTION` → downgrade STRONG_BUY → BUY; hiển thị banner cảnh báo
- Nếu `warning_level=WATCH` → thêm vào advisory note

### 8.8 FR-6.7 — Money Flow Dashboard (UI)

**Màn hình riêng** hiển thị toàn bộ dòng tiền thị trường theo real-time:

```
┌─────────────────────────────────────────────────────────────────┐
│  DÒNG TIỀN LỚN — LARGE MONEY FLOW DASHBOARD                    │
│  Cập nhật: 14:32:15 | [Refresh] [Export]                       │
│                                                                 │
│  SECTOR ROTATION MAP ─────────────────────────────────────────  │
│  🟢 NGÂN HÀNG    +82 INFLOW  │ 🟢 THÉP      +65 INFLOW         │
│  🟡 BẤT ĐỘNG SẢN +15 NEUTRAL │ 🔴 DẦU KHÍ  -40 OUTFLOW        │
│  Phase: ROTATION (Bank & Steel replace Oil & Gas)               │
│                                                                 │
│  TOP 10 MÃ CÁ VOI ĐANG GOM ─────────────────────────────────── │
│  # │ Ticker │ SMS │ M-CVD 5d    │ Stealth │ Mode  │ Signal     │
│  1 │  HPG   │  82 │ +1.2M cổ ↑ │   ✅    │   W   │ STRONG_BUY │
│  2 │  VCB   │  78 │ +0.8M cổ ↑ │   ✅    │   W   │ STRONG_BUY │
│  3 │  FPT   │  71 │ +0.5M cổ ↑ │   ❌    │   W   │    BUY     │
│                                                                 │
│  CẢNH BÁO PHÂN PHỐI ─────────────────────────────────────────  │
│  ⚠️  PDR: CAUTION — DELTA_DIVERGE_BEARISH + OBV_NEGATIVE_TURN  │
│  ⚠️  NVL: WATCH   — FOREIGN_NET_SELL_5D                        │
│                                                                 │
│  DÒNG TIỀN NGOẠI (FOL NET 5D) ───────────────────────────────  │
│  Mua ròng Top: BID +42B | VCB +38B | HPG +31B                  │
│  Bán ròng Top: PDR -28B | NVL -22B | DXG -18B                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.9 FR-6.8 — Updated Signal Schema (22 → 30 Fields)

```python
class TradingSignal:
    # == Original 22 fields (unchanged) ==
    signal_id       : str
    timestamp       : datetime
    ticker          : str
    exchange        : str
    action          : str            # STRONG_BUY|BUY|WATCH|NO_SIGNAL|SELL_SIGNAL
    mode            : str            # MODE_A|MODE_B|MODE_W  ← updated
    entry_price     : float
    stop_loss       : float
    tp1             : float
    tp2             : float
    rr_ratio        : float
    mfpm_score      : int
    canslim_score   : int
    hurst_exponent  : float
    hmm_state       : str
    gmo_omega       : float
    fol_status      : str
    fol_room_pct    : float
    triggers        : list[str]
    circuit_breaker : bool
    mc_win_prob     : float
    amd_phase       : str
    vsa_signal      : str
    cvd_whale_net   : int            # intraday
    order_block     : dict | None
    cup_with_handle : dict | None
    phobert_sentiment: float
    shap_top5       : list[str]
    qty_suggested   : int
    position_pct    : float
    exposure_mode   : str
    advisory_vn     : str
    advisory_en     : str

    # == NEW 8 fields (FR-6) ==
    sms             : int            # Smart Money Score 0–100
    sms_label       : str            # WHALE_BUYING|WHALE_DISTRIBUTING|MIXED|RETAIL_DRIVEN
    mcvd_5d         : int            # Multi-day CVD 5 sessions (shares net)
    mcvd_trend      : str            # UP|DOWN|FLAT
    stealth_accum   : bool           # Stealth accumulation detected
    sector_flow     : str            # INFLOW|NEUTRAL|OUTFLOW
    whale_dist_warning: str          # NONE|WATCH|CAUTION|SELL_SIGNAL
    sms_components  : dict           # {mcvd:int, vqs:int, fol:int, obv:int, amd:int}
```

---

## 9. Non-Functional Requirements

### 9.1 Reliability

| NFR | Target |
|---|---|
| Uptime | 99% (local app) |
| SSI fallback | DNSE trong 30 giây nếu SSI down |
| Error isolation | Exception trong 1 ticker không crash toàn scan |
| M-CVD continuity | Nếu tick data gián đoạn → proxy từ daily OHLCV, ghi log |
| KRX compliance | Order type = MTL (not MP) on HOSE; PCA stocks flagged and excluded from auto-signals; audit log ghi nhận mọi partial fill |

### 9.2 Security & Compliance

| NFR | Implementation |
|---|---|
| Credentials | `.env` file; không hard-code; không commit |
| Device-ID | UUID4 random; rotation khi bị block |
| Audit | Không lưu personal data |
| No telemetry | Xử lý 100% local |
| Audit retention | ≥ 24 tháng: hot 30d (DuckDB) + 6 tháng (Parquet) + cold zip per month — tuân thủ Nghị định 53/2022/NĐ-CP về an ninh mạng và lưu trú dữ liệu tài chính tại VN |
| NPF flag | Nếu tổ chức NN fail-to-settle: FOL_FOREIGN_BUY signal penalized -10 MFPM trong 7 phiên (Circular 08/2026/TT-BTC — *pending final regulatory verification*) |

### 9.3 Maintainability

| NFR | Target |
|---|---|
| Test coverage | Core engines ≥ 80%; money_flow.py ≥ 75% |
| Type hints | 100% public functions |
| Config external | Tất cả thresholds trong `config/strategy.yaml` |

### 9.4 `config/strategy.yaml` (Excerpt — Money Flow Section)

```yaml
money_flow:
  # M-CVD
  mcvd_lookback_days: 20
  mcvd_slope_threshold: 0.01      # |slope| < this → FLAT
  mcvd_consistency_high: 0.60     # ≥ 60% phiên whale positive = consistent UP
  whale_tick_threshold: 50000     # shares per tick = WHALE (≥50K = 50 tỷ @ 10k)
  mid_tick_threshold: 5000        # MID size

  # SMS thresholds
  sms_strong_buy: 70
  sms_buy: 55
  sms_watch: 40
  sms_distribution_veto: 20      # SMS < 20 overrides to WATCH regardless of MFPM

  # Mode W entry
  mode_w_min_sms: 70
  mode_w_min_consistency: 0.55
  mode_w_sl_atr_multiplier: 1.5
  mode_w_tp_atr_multiplier: 8    # default TP2 if no est_target

  # Stealth accumulation
  stealth_tight_range_atr_pct: 0.015
  stealth_obv_change_min: 0.03
  stealth_z_vol_max: 1.5

  # Sector rotation
  sector_inflow_threshold: 20
  sector_outflow_threshold: -20

  # Distribution warning
  dist_fol_net_5d_threshold: -0.02  # % daily vol
  dist_obv_slope_negative: -0.03

  # Proxy (khi không có tick data)
  proxy_z_vol_threshold: 0.5
  proxy_range_pct_threshold: 0.5  # close > 50% of range = buy proxy
```

---

## 9.5 Regulatory & Architecture Scope Decisions

### 9.5.1 Accepted — KRX Technical Standards

| Decision | Spec | Source |
|---|---|---|
| Order type on HOSE | **MTL** (Market-to-Limit) — MP orders deprecated under KRX. Remainder after partial fill converts to LO at last matched price. | KRX rollout |
| Restricted stock trading | **PCA** (Periodic Continuous Auction): 15 rounds × 15 min. Auto-signals blocked during active PCA rounds; cancellation/edit blocked in final 5 min of each round. | KRX/HOSE rules |
| ATO/ATC session isolation | ATO/ATC run in **separate auction phases** — do not compete with LO time-priority in continuous session. | KRX matching spec |
| Audit retention | **≥ 24 months** — Nghị định 53/2022/NĐ-CP cybersecurity + financial data localization. | VN Decree 53/2022 |
| NPF settlement flag | Foreign institutional fail-to-settle triggers 7-day FOL signal penalty. Circular 08/2026/TT-BTC — *verify before production*. | TT 08/2026 (pending) |
| XBRL fundamental data | SSC IDS XBRL-formatted filings as supplementary input for NLP/fundamental accuracy. **Phase 3+** — requires SSC portal API access. | SSC disclosure portal |
| **Rust + io_uring** data ingestion daemon | Separate Rust binary (`data/collector_daemon/`) handles SSI market data polling → DuckDB hot path. Linux: io_uring zero-copy recv (kernel ≥ 5.1); Windows dev: Tokio IOCP fallback. Tách biệt hoàn toàn khỏi Python analytics layer. | Board Eval F-07 (re-scoped) |
| **≤ 3.9 ms** network hop (SSI → daemon) | P50 target for market data round-trip: SSI API server → Rust daemon buffer. io_uring zero-copy recv path. Applies to data ingestion layer only. | Board Eval F-08 (re-scoped) |
| **< 100 ms** end-to-end data refresh | SSI API response → DuckDB write ≤ 100 ms during market hours. Includes JSON deserialize + INSERT. Python analytics SLA (2–5s P50) **unchanged**. | Board Eval F-08 (re-scoped) |

### 9.5.2 Rejected — Out-of-Scope Architecture Decisions

> These items were proposed in the Board Evaluation document but are **explicitly rejected** for TradingOS Alpha.

| Rejected Item | Reason |
|---|---|
| **T+0 8–10× daily capital turnover** | Swing trading system. T+0 intraday is explicitly **Out of Scope** for Phase 1–4. |
| **FIX 4.4 API standard** | Broker OMS order routing protocol. TradingOS gives recommendations, not orders. Consider Phase 5+ only if broker integration is added. |

---

## 10. Data Models & DuckDB Schema

### 10.1 New Tables for FR-6

```sql
-- Multi-day whale flow history (daily, append-only)
CREATE TABLE money_flow_daily (
    ticker          VARCHAR   NOT NULL,
    trade_date      DATE      NOT NULL,
    whale_net       BIGINT,              -- shares: whale_buy - whale_sell
    whale_net_proxy BIGINT,              -- nếu không có tick: proxy từ OHLCV
    data_source     VARCHAR,             -- 'TICK_REAL' | 'PROXY_OHLCV'
    fol_net         BIGINT,              -- foreign net qty
    cvd_end         BIGINT,              -- end-of-day CVD value
    sms             INTEGER,             -- computed SMS
    sms_label       VARCHAR,
    stealth_accum   BOOLEAN,
    sector_flow     VARCHAR,
    computed_at     TIMESTAMP,
    PRIMARY KEY (ticker, trade_date)
);

-- Sector flow cache
CREATE TABLE sector_flow (
    sector          VARCHAR   NOT NULL,
    flow_date       DATE      NOT NULL,
    inflow_score    DOUBLE,
    sms_avg         DOUBLE,
    momentum_5d     DOUBLE,
    flow_status     VARCHAR,             -- INFLOW|NEUTRAL|OUTFLOW
    hot_tickers     VARCHAR,             -- JSON array top 5 tickers
    computed_at     TIMESTAMP,
    PRIMARY KEY (sector, flow_date)
);

-- Whale distribution alerts
CREATE TABLE distribution_alerts (
    alert_id        VARCHAR   PRIMARY KEY,
    ticker          VARCHAR   NOT NULL,
    alert_date      DATE      NOT NULL,
    warning_level   VARCHAR,             -- WATCH|CAUTION|SELL_SIGNAL
    flags           VARCHAR,             -- JSON array
    score           INTEGER,
    explanation     TEXT,
    resolved        BOOLEAN   DEFAULT FALSE,
    created_at      TIMESTAMP
);
```

### 10.2 Existing Tables (unchanged)

```sql
-- (All tables from original SRS section 5.1 remain unchanged)
-- ohlcv_daily, ohlcv_5m, indicators_daily, signal_history,
-- audit_log, watchlist, scan_results, backtest_results, sector_map
-- Note: indicators_daily.vwap = alias for typical_price_close = (H+L+C)/3 daily ref.
-- Intraday cumulative VWAP (5-min) computed on-demand, NOT stored here.
```

### 10.3 Updated File Structure

```
src/tradingos/
├── core/
│   ├── gmo.py              # Module 1: HMM, Omega, Breadth, VN30F, Kalman
│   ├── indicators.py       # Module 2: SMA/EMA/RSI/ATR/OBV/VWAP-intraday(5m)/TP-daily/Hurst/OFI
│   ├── anti_manip.py       # Module 2.9+2.10: VQS, AMD, VSA, CVD intraday, AMF
│   ├── money_flow.py       # Module 2.11 (NEW FR-6): M-CVD, SMS, Stealth, Sector, Mode W
│   ├── patterns.py         # Module 3: Spring, VCP, FVG, Weis, RSI-Div, OB, CwH
│   ├── mfpm.py             # Module 4: Mode A/B/W scoring, MC gate, Kelly guard
│   ├── sizing.py           # Kelly bootstrap, progressive entry
│   ├── t25_engine.py       # Module 5: T+2.5 exit logic
│   ├── exit_engine.py      # Module 6: Progressive exit, trailing stop
│   ├── nlp.py              # Module 7: Advisory generation, SHAP
│   ├── backtest.py         # Module 8: VN-constrained backtest + walk-forward
│   ├── universe.py         # build_universe, CAN SLIM, RS Rating
│   └── atc_router.py       # Smart ATC/MTL router (KRX: MTL partial fill → LO remainder, ATC imbalance, anti-manip gate)
├── data/
│   ├── fetcher.py          # Async SSI EP-1..14 + DNSE
│   ├── cache.py            # DuckDB TTL management
│   ├── normalizer.py       # Ex-div, tick rounding
│   └── schemas.py          # Pydantic models (updated with SMS fields)
├── engines/
│   ├── profiler_service.py
│   ├── scanner_service.py
│   ├── money_flow_service.py   # NEW: MoneyFlowService orchestration
│   ├── audit_service.py
│   ├── backtest_service.py
│   └── portfolio_service.py
├── ui/
│   ├── app.py
│   ├── pages/
│   │   ├── profiler.py
│   │   ├── scanner.py
│   │   ├── money_flow.py       # NEW: DTL Dashboard page
│   │   ├── audit.py
│   │   ├── backtest.py
│   │   └── settings.py
│   └── components/
│       ├── signal_card.py
│       ├── horizon_table.py
│       ├── shap_chart.py
│       ├── sms_gauge.py         # NEW: SMS speedometer component
│       ├── mcvd_chart.py        # NEW: M-CVD bar chart N days
│       ├── sector_heatmap.py    # NEW: sector rotation heatmap
│       ├── equity_curve.py
│       └── audit_timeline.py
└── utils/
    ├── config.py
    ├── logging.py
    └── dates.py
```

---

## 11. API Specification

```python
# ProfilerService (updated)
class ProfilerService:
    def run(self, req: ProfilerRequest) -> list[TickerProfile]: ...
    def run_quick(self, ticker: str) -> TickerProfile: ...
    def get_horizon(self, ticker: str, horizon_days: int) -> HorizonRecommendation: ...

# ScannerService (updated — Stage 3 money flow filter)
class ScannerService:
    def scan(self, req: ScanRequest) -> ScanResult: ...
    def get_watchlist_scan(self, tickers: list[str]) -> ScanResult: ...
    def get_latest_scan(self, scan_type: str = "FULL") -> ScanResult | None: ...

# MoneyFlowService (NEW)
class MoneyFlowService:
    def get_sms(self, ticker: str, as_of_date: date | None = None) -> dict:
        """Compute Smart Money Score for 1 ticker."""

    def get_market_flow(self) -> dict:
        """Market-wide flow: sector rotation + top whale accum + distribution warnings."""

    def get_sector_rotation(self) -> dict:
        """Detect sector rotation phase + hot/cold sectors."""

    def get_whale_watchlist(self, min_sms: int = 70) -> list[dict]:
        """Top N tickers with whale accumulation active."""

    def get_distribution_alerts(self, active_only: bool = True) -> list[dict]:
        """Active whale distribution warnings."""

    def run_mcvd_daily_update(self, tickers: list[str]) -> None:
        """Post-close job: update money_flow_daily table for all tickers."""

# AuditService (updated with DTL events)
class AuditService:
    def log(self, event: AuditEventType, **kwargs) -> str: ...
    def query(self, event_types, ticker, start, end, limit) -> list[AuditRecord]: ...
    def get_signal_trace(self, signal_id: str) -> dict: ...
    def export_csv(self, query_params: dict, path: str) -> None: ...
    def get_rejection_stats(self, days: int = 30) -> dict: ...

# BacktestService (updated — Mode W backtest)
class BacktestService:
    def run(self, req: BacktestRequest) -> BacktestResult: ...
    def run_walk_forward(self, req: BacktestRequest) -> BacktestResult: ...
    def sensitivity_analysis(self, ticker, param, values, start, end) -> list[BacktestResult]: ...
    def compare_modes(self, ticker: str, start: date, end: date) -> dict:
        """Compare Mode A vs B vs W performance on same dataset."""
```

---

## 12. UI/UX Specification

### 12.1 Profiler Page (updated with SMS)

```
┌─────────────────────────────────────────────────────────────┐
│ STOCK PROFILER                                              │
│ Tickers: [HPG, VCB     ] Mode: [Full ▼] [Analyze]         │
│                                                             │
│ ── HPG (HOSE) @ 28,500 ──── STRONG_BUY (Mode W) ─── 94 ── │
│ HMM: STEADY_BULL │ AMD: ACCUMULATION │ H: 0.62            │
│                                                             │
│ 💰 DÒNG TIỀN: WHALE_BUYING │ SMS: 82 ▓▓▓▓▓▓▓▓▓▓▓░░ 82/100│
│  M-CVD 5d: +1.2M cổ ↑ │ Stealth: ✅ 12 phiên             │
│  NN 5d: +125K cổ/ngày│ Ngành STEEL: 🟢 INFLOW            │
│                                                             │
│ ┌────────┬──────┬──────────┬──────┬──────┬────┬──────┐     │
│ │Horizon │Label │ Action   │Entry │  SL  │TP1 │R/R   │     │
│ │  T+2   │Siêu  │  BUY/W   │  ATC │26,790│31K │ 2.59 │     │
│ │  T+5   │Short │  BUY/W   │14:05 │26,790│31K │ 2.59 │     │
│ │  T+10  │Mid   │STRONG/W  │14:05 │26,790│33K │ 3.10 │     │
│ │  T+15  │Long  │  BUY/W   │14:05 │26,790│35K │ 3.50 │     │
│ └────────┴──────┴──────────┴──────┴──────┴────┴──────┘     │
│                                                             │
│ [SMS Components] ─────────────────────────────────────     │
│ M-CVD trend:  ██████████████████████████ 25/25            │
│ VQS:          ████████████████████       18/20            │
│ FOL net 5d:   ████████████████           16/20            │
│ OBV slope:    ████████████               12/15            │
│ AMD align:    ██████████                 10/10            │
│ CVD today:    ████████                    8/10            │
│                                                             │
│ [Advisory VN] [SHAP] [Risk] [Export PDF/JSON/CSV]          │
│ ⚠️  Không có cảnh báo phân phối                            │
└─────────────────────────────────────────────────────────────┘
```

### 12.2 Money Flow Dashboard Page (NEW)

```
┌─────────────────────────────────────────────────────────────────┐
│  💰 DÒNG TIỀN LỚN — LARGE MONEY FLOW          [14:32] [↻]      │
│                                                                 │
│  SECTOR ROTATION ─────────────────────────────────────────────  │
│  Ngân Hàng    ████████████████████████ +82 🟢 INFLOW           │
│  Thép         ████████████████████     +65 🟢 INFLOW           │
│  Hóa Chất     ████████████             +35 🟡 NEUTRAL          │
│  Bất Động Sản ██████                   +15 🟡 NEUTRAL          │
│  Dầu Khí      ██░░░░░░░░               -40 🔴 OUTFLOW          │
│  Phase: ROTATION │ RISK_ON nếu Ngân Hàng + Thép dẫn đầu       │
│                                                                 │
│  TOP CÁ VOI ĐANG GOM ─────────────────────────────────────────  │
│  # │Ticker│SMS │M-CVD 5d   │Stealth │Signal   │vs giá hôm nay  │
│  1 │ HPG  │ 82 │+1.2M  ↑↑  │ ✅12d  │STRONG_W │ Chưa breakout │
│  2 │ VCB  │ 78 │+0.8M  ↑   │ ✅ 8d  │STRONG_W │ Chưa breakout │
│  3 │ BID  │ 74 │+0.6M  ↑   │ ✅ 5d  │  BUY_W  │ Near pivot   │
│  [Xem tất cả] [Add to Watchlist]                               │
│                                                                 │
│  CẢNH BÁO PHÂN PHỐI ─────────────────────────────────────────  │
│  ⚠️  PDR — CAUTION: Delta Diverge Bearish + OBV off │Score: 5  │
│  ⚡  NVL — SELL_SIGNAL: AMD Distrib + NN bán ròng  │Score: 7  │
│  [Xem chi tiết] [Notify]                                       │
│                                                                 │
│  DÒNG TIỀN NGOẠI (5d) ────── DÒNG TIỀN NỘI (5d) ──────────── │
│  🟢 VCB +38B │ HPG +31B      🟢 SHB +15B │ MBB +12B          │
│  🔴 PDR -28B │ NVL -22B      🔴 VIC -20B │ DXG -15B          │
└─────────────────────────────────────────────────────────────────┘
```

### 12.3 Scanner Page (updated)

```
┌─────────────────────────────────────────────────────────────────┐
│ MARKET SCANNER — Tìm Mã Để Mua                                  │
│ [Daily Scan] [Whale Watch] [Watchlist] [Custom]                │
│ Sector: [All▼] MFPM≥: [50] SMS≥: [40] Stealth: [☐]           │
│ Context: HMM=STEADY_BULL │ Rotation=RISK_ON │ Ω=0.55          │
│ 265 → CAN SLIM:72 → MF Filter:58 → AMF Pass:48 → Top 20      │
│                                                                 │
│ # │Ticker│MFPM│SMS │Mode  │Signal    │Entry  │TP1   │Reason   │
│ 1 │ HPG  │ 94 │ 82 │  W   │STRONG_BUY│28,500 │31,200│Whale+Sp │
│ 2 │ VCB  │ 88 │ 78 │  W   │STRONG_BUY│87,000 │96,000│M-CVD+FOL│
│ 3 │ FPT  │ 82 │ 65 │  B   │   BUY    │140,000│155K  │VCP+SMS  │
│ 4 │ BID  │ 75 │ 74 │  W   │   BUY    │32,000 │35,200│Stealth  │
│ [Click row → Full Profile]                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 12.4 Backtest — Mode Comparison Tab (NEW)

```
┌─────────────────────────────────────────────────────────────────┐
│  BACKTEST — MODE COMPARISON  HPG  2023-01 → 2026-03            │
│                                                                 │
│         │ Mode A │ Mode B │ Mode W │ Combined │                │
│ Trades  │   31   │   18   │   12   │   61     │                │
│ Win Rate│ 55.8%  │ 57.4%  │ 62.5%  │  57.9%   │ ← Mode W best │
│ Avg R/R │  2.21  │  2.45  │  2.71  │   2.38   │               │
│ Avg Hold│  4.2d  │  6.8d  │  8.1d  │   5.7d   │               │
│                                                                 │
│  [Equity Curves — all 3 modes overlaid]                        │
│  [Walk-Forward IS/OOS per mode]                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. Implementation Plan (17 tuần)

### Phase Overview

| Phase | Name | Duration | Key Output |
|---|---|---|---|
| P1 | Foundation | Weeks 1–3 | Data layer, DuckDB, indicators |
| P2 | Core Engine | Weeks 4–7 | MFPM A/B, Patterns, AMF, HMM, NLP |
| P2b | Money Flow | Week 4b (parallel) | money_flow.py: M-CVD, SMS, Stealth, Sector |
| P3 | Profiler + Audit | Weeks 8–10 | FR-1 + FR-3 + Streamlit Profiler |
| P4 | Scanner + DTL UI | Weeks 11–13 | FR-2 + FR-6 Dashboard |
| P5 | Backtest | Weeks 14–15 | FR-5 + Mode W backtest |
| P6 | Optimization | Weeks 16–17 | FR-4, testing, hardening |

---

### Week 1 — Data Layer

| Task | File | Priority |
|---|---|---|
| DuckDB schema init (all tables incl. money_flow_daily) | `scripts/init_db.py` | 🔴 |
| Rust data ingestion daemon scaffold | `data/collector_daemon/` (Rust crate) | 🟡 |
| Async fetcher SSI EP-1 (OHLCV daily) | `data/fetcher.py` | 🔴 |
| DNSE fallback | `data/fetcher.py` | 🔴 |
| DuckDB cache read/write + TTL | `data/cache.py` | 🔴 |
| Ex-dividend normalizer EP-11 | `data/normalizer.py` | 🔴 |
| Pydantic schemas (incl. SMS fields) | `data/schemas.py` | 🟡 |

### Week 2 — Technical Indicators

| Task | File | Priority |
|---|---|---|
| SMA/EMA/RSI/ATR/OBV | `core/indicators.py` | 🔴 |
| VWAP, Z_vol, MACD, ADX | `core/indicators.py` | 🔴 |
| `compute_vwap(mode="intraday")` — 5-min bars, on-demand, TTL 5 phút | `core/indicators.py` | 🔴 |
| `compute_vwap(mode="daily_ref")` — daily TP ref, lưu `typical_price_close` | `core/indicators.py` | 🔴 |
| Hurst exponent (min-length guard ≥ 200) | `core/indicators.py` | 🔴 |
| OFI adaptive field lookup (EP-4) | `core/indicators.py` | 🔴 |
| SSI EP-3 (quote), EP-4 (order book) fetcher | `data/fetcher.py` | 🟡 |
| Unit tests: all indicators | `tests/unit/test_indicators.py` | 🟡 |

### Week 3 — Universe + Config

| Task | File | Priority |
|---|---|---|
| Load/validate `strategy.yaml` (incl. money_flow section) | `utils/config.py` | 🔴 |
| `build_universe()` tiered HOSE/HNX | `core/universe.py` | 🔴 |
| CAN SLIM filter + `compute_rs_rating()` | `core/universe.py` | 🔴 |
| `detect_swing_low()` | `core/universe.py` | 🟡 |
| `scripts/seed_universe.py` + `scripts/backfill_ohlcv.py` | `scripts/` | 🟡 |

### Week 4a — Patterns + Anti-Manipulation

| Task | File | Priority |
|---|---|---|
| Spring, VCP (adaptive threshold) | `core/patterns.py` | 🔴 |
| Weis Wave, FVG, RSI Divergence | `core/patterns.py` | 🔴 |
| Order Block, Cup with Handle | `core/patterns.py` | 🟡 |
| VQS, detect_spring_quality, second_mouse_gate | `core/anti_manip.py` | 🔴 |
| detect_insider_run, anti_manipulation_filter ensemble | `core/anti_manip.py` | 🔴 |
| AMD classify, VSA bars, CVD proxy (intraday) | `core/anti_manip.py` | 🟡 |
| Unit tests: patterns + AMF | `tests/unit/` | 🟡 |

### Week 4b — Money Flow Module (NEW FR-6) ← PARALLEL với 4a

| Task | File | Priority |
|---|---|---|
| `proxy_whale_net_from_daily()` (Phase 1 no-tick path) | `core/money_flow.py` | 🔴 |
| `compute_multiday_whale_flow()` M-CVD | `core/money_flow.py` | 🔴 |
| `compute_smart_money_score()` SMS | `core/money_flow.py` | 🔴 |
| `detect_stealth_accumulation()` | `core/money_flow.py` | 🔴 |
| `detect_sector_rotation()` | `core/money_flow.py` | 🟡 |
| `detect_whale_distribution()` early warning | `core/money_flow.py` | 🔴 |
| `mode_w_entry_params()` Follow-the-Whale entry | `core/money_flow.py` | 🔴 |
| `money_flow_daily` DuckDB write + `run_mcvd_daily_update()` | `engines/money_flow_service.py` | 🔴 |
| Unit tests: SMS, M-CVD, Stealth, Distribution | `tests/unit/test_money_flow.py` | 🔴 |

### Week 5 — GMO + HMM

| Task | File | Priority |
|---|---|---|
| `fit_hmm()` state pinning (BEAR=0, SIDEWAYS=1, BULL=2) | `core/gmo.py` | 🔴 |
| `monthly_refit_hmm()` rolling 3-year window | `core/gmo.py` | 🔴 |
| GMO Omega calculation | `core/gmo.py` | 🔴 |
| Market breadth EP-7, VN30F Basis | `core/gmo.py` | 🟡 |
| `calibrate_herding_threshold()` Kalman | `core/gmo.py` | 🟡 |
| Unit tests: HMM state pinning, Omega | `tests/unit/test_gmo.py` | 🟡 |

### Week 6 — MFPM Engine (Updated for Mode W)

| Task | File | Priority |
|---|---|---|
| Pre-conditions check Mode A/B (10 gates + AMD + double-count) | `core/mfpm.py` | 🔴 |
| Mode A scoring (22 factors + mutex + SMS confirm rows) | `core/mfpm.py` | 🔴 |
| Mode B scoring + gap-up gate + second_mouse_gate | `core/mfpm.py` | 🔴 |
| **Mode W pre-conditions (W-1…W-8)** | `core/mfpm.py` | 🔴 |
| **Mode W scoring table (SMS components + bonuses)** | `core/mfpm.py` | 🔴 |
| `get_regime_mu()` + Monte Carlo gate | `core/mfpm.py` | 🔴 |
| Kelly bootstrap guard (< 30 trades → fixed 5%) | `core/sizing.py` | 🔴 |
| Progressive entry 50+50 / 6.25→25% | `core/sizing.py` | 🟡 |
| Unit tests: all 3 modes, boundary conditions | `tests/unit/test_mfpm.py` | 🔴 |

### Week 7 — NLP + T+2.5 + Exit

| Task | File | Priority |
|---|---|---|
| Advisory template (VN + EN) — updated for SMS fields | `core/nlp.py` | 🔴 |
| `generate_shap_explanation()` — includes SMS components | `core/nlp.py` | 🔴 |
| `t25_exit_check()` + danger window | `core/t25_engine.py` | 🔴 |
| Progressive exit (total_qty basis) + trailing stop | `core/exit_engine.py` | 🔴 |
| Smart ATC router + manipulation gate | `core/atc_router.py` | 🟡 |

### Week 8 — ProfilerService + AuditService

| Task | File | Priority |
|---|---|---|
| `ProfilerService.run()` — integrate SMS + stealth + sector | `engines/profiler_service.py` | 🔴 |
| Horizon projection (T+2..T+15) — Mode W threshold logic | `engines/profiler_service.py` | 🔴 |
| `run_quick()` deferred SMS computation | `engines/profiler_service.py` | 🟡 |
| `AuditService.log()` async write + DTL event types | `engines/audit_service.py` | 🔴 |
| `query()`, `get_signal_trace()`, `export_csv()` | `engines/audit_service.py` | 🔴 |
| Integration test: full profiler | `tests/integration/` | 🟡 |

### Week 9 — Profiler UI

| Task | File | Priority |
|---|---|---|
| `signal_card.py` + `horizon_table.py` | `ui/components/` | 🔴 |
| `shap_chart.py` + `sms_gauge.py` ← NEW | `ui/components/` | 🟡 |
| `pages/profiler.py` full Streamlit page (with SMS section) | `ui/pages/profiler.py` | 🔴 |

### Week 10 — Audit UI

| Task | File | Priority |
|---|---|---|
| `audit_timeline.py` + `pages/audit.py` | `ui/` | 🔴 |
| Signal drill-down + Money flow trace view | `ui/pages/audit.py` | 🔴 |

### Week 11 — ScannerService + Money Flow Service

| Task | File | Priority |
|---|---|---|
| 5-stage scanner pipeline + Stage 3 money flow filter | `engines/scanner_service.py` | 🔴 |
| `parallel_mfpm_score()` ProcessPoolExecutor | `engines/scanner_service.py` | 🔴 |
| `MoneyFlowService.get_market_flow()` | `engines/money_flow_service.py` | 🔴 |
| `MoneyFlowService.get_whale_watchlist()` | `engines/money_flow_service.py` | 🔴 |
| `MoneyFlowService.get_distribution_alerts()` | `engines/money_flow_service.py` | 🔴 |
| Post-close cron: `run_mcvd_daily_update()` | `scripts/scheduled_update.py` | 🟡 |

### Week 12 — Scanner UI + Money Flow Dashboard

| Task | File | Priority |
|---|---|---|
| `pages/scanner.py` — SMS column + Mode W tag | `ui/pages/scanner.py` | 🔴 |
| `sector_heatmap.py` component | `ui/components/` | 🟡 |
| `mcvd_chart.py` component | `ui/components/` | 🟡 |
| **`pages/money_flow.py` — DTL Dashboard** (FR-6.8) | `ui/pages/money_flow.py` | 🔴 |
| Whale Watch scan filter | `ui/pages/scanner.py` | 🟡 |

### Week 13 — Backtest Engine (Mode W)

| Task | File | Priority |
|---|---|---|
| VN-constrained simulation engine (T+2.5, lot, comm, slip) | `core/backtest.py` | 🔴 |
| `walk_forward_backtest()` IS/OOS windows | `core/backtest.py` | 🔴 |
| **Mode W simulation path** (SMS-based entry) | `core/backtest.py` | 🔴 |
| Overfitting detection (OOS < IS × 0.85) | `core/backtest.py` | 🔴 |
| M-CVD proxy backfill for historical runs | `core/backtest.py` | 🟡 |
| Unit tests: T+2.5, lot, commission | `tests/unit/test_backtest.py` | 🔴 |

### Week 14 — Backtest + Sensitivity UI

| Task | File | Priority |
|---|---|---|
| `equity_curve.py` + `pages/backtest.py` | `ui/` | 🔴 |
| **Mode A vs B vs W comparison chart** | `ui/pages/backtest.py` | 🔴 |
| SMS × MFPM sensitivity heatmap | `ui/pages/backtest.py` | 🟡 |
| Trade log + CSV export | `ui/pages/backtest.py` | 🟡 |

### Week 15 — `sensitivity_analysis()` + Portfolio

| Task | File | Priority |
|---|---|---|
| `BacktestService.sensitivity_analysis()` | `engines/backtest_service.py` | 🟡 |
| `PortfolioService` + `pages/portfolio.py` | `engines/`, `ui/pages/` | 🟡 |
| `pages/settings.py` — strategy.yaml UI editor | `ui/pages/settings.py` | 🟡 |

### Week 16 — Async + Cache Optimization

| Task | Priority |
|---|---|
| Convert all fetchers to `asyncio` + `aiohttp` | 🔴 |
| Incremental indicator update (append-only new bar) | 🔴 |
| SMS memoize per session | 🟡 |
| DuckDB connection pool | 🟡 |
| Benchmark all SLAs vs targets | 🔴 |

### Week 17 — Testing + Hardening

| Task | Priority |
|---|---|
| ≥ 80% unit test coverage: core + money_flow | 🔴 |
| Integration test: Profiler + Scanner + DTL + Audit | 🔴 |
| All SSI failure paths gracefully handled | 🔴 |
| Load test: 10 concurrent profiler requests | 🟡 |
| README + deployment guide + CHANGELOG | 🟢 |

---

## 14. Risk Register

| Risk | Prob | Impact | Mitigation |
|---|---|---|---|
| SSI tick data (EP FastConnect) không khả dụng | High | Med | M-CVD proxy từ daily OHLCV; log `DATA_FETCH_FAILED` |
| Proxy whale_net không accurate | High | Med | Backtest proxy vs real CVD khi data available; tune threshold |
| SMS false signal (SMS cao nhưng thực ra retail chasing) | Med | High | VQS cross-check: cần VQS ≥ +0.3 khi SMS ≥ 70 để activate Mode W |
| Sector ETF data không available SSI | Med | Med | Dùng average OHLCV của top-10 tickers per sector làm proxy |
| Mode W over-trading nếu threshold thấp | Med | High | Minimum: W-1 SMS ≥ 70 + W-2 consistency 55% + W-3 AMF=PASS bắt buộc |
| M-CVD look-ahead bias trong backtest | Med | High | Dùng proxy_whale_net tính từ open→close same day; không dùng T+1 data |
| SSI API schema changes | High | High | Adaptive field lookup; DNSE fallback |
| HMM label switching after refit | Low | High | State pinning by emission mean; unit test |
| Kelly over-sizing với sparse data | Med | High | Bootstrap guard: fixed 5% cho đến 30 trades |
| Backtest bull-bias 2020–2025 | Med | High | Walk-forward OOS: OOS ≥ IS × 0.85 gate |
| Streamlit chậm với 20+ profiles | Med | Med | Pagination; lazy SMS load; quick mode default |
| AMF false positive BLOCK | Med | Med | Ensemble 2/3 vote; WARN vs BLOCK |

---

*TradingOS Alpha SRS v1.0 — End of Document*

*Xem thêm: [`docs/proposal/TradingOS-Alpha-Proposal-v1.0.md`](../proposal/TradingOS-Alpha-Proposal-v1.0.md)*
