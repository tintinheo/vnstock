"""Integration smoke test — no network, no file DB needed."""
import sys

# Ensure stdout uses UTF-8 on Windows (avoids charmap errors from emoji in advisory text)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

np.random.seed(42)
n = 120
dates = pd.date_range("2024-01-01", periods=n, freq="B")
close = 50000 + np.cumsum(np.random.randn(n) * 500)
df_synth = pd.DataFrame(
    {
        "open": close * 0.999,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.random.randint(500_000, 2_000_000, n).astype(float),
    },
    index=dates,
)

# Patch fetch_ohlcv at the module where it is USED
import tradingos.engines.profiler_service as ps
import tradingos.engines.backtest_service as bs
ps.fetch_ohlcv = lambda ticker, days=260, **kw: df_synth
bs.fetch_ohlcv = lambda ticker, days=520, **kw: df_synth

# ── ProfilerService ────────────────────────────────────────────────────────
print("--- ProfilerService ---")
from tradingos.engines.profiler_service import ProfilerService
from tradingos.data.schemas import ProfilerRequest

svc = ProfilerService(portfolio_value=300_000_000)
req = ProfilerRequest(ticker="VCB", mode="FULL")
p = svc.run(req)
print(f"  action={p.action}  confidence={p.confidence}")
print(f"  mfpm={p.mfpm_score}  sms={p.sms_raw}  vqs={p.vqs:.3f}")
print(f"  entry={p.entry_price:.0f}  sl={p.stop_loss:.0f}  tp1={p.tp1:.0f}  rr={p.rr_ratio:.1f}")
print(f"  mode={p.signal_mode}  hmm={p.hmm_state}  amd={p.amd_phase}")
print(f"  stealth={p.stealth_accum}  dist={p.distribution_warning}")
print(f"  sizing={p.sizing_shares} shares ({p.sizing_pct:.1%})")
print(f"  horizons={len(p.horizons)}")
print(f"  advisory[0:80]={p.advisory_text[:80]!r}")

assert p.ticker == "VCB"
assert p.action in ("BUY", "STRONG_BUY", "WATCH", "NO_ACTION", "EXIT", "FORCED_EXIT")
assert isinstance(p.mfpm_score, int)
assert isinstance(p.vqs, float)
assert p.entry_price >= 0
print("  [PASS]")

# ── BacktestService ────────────────────────────────────────────────────────
print("\n--- BacktestService ---")
from tradingos.engines.backtest_service import BacktestService
from tradingos.data.schemas import BacktestRequest

bsvc = BacktestService()
req2 = BacktestRequest(ticker="VCB")
results = bsvc.run(req2)
for mode, bt in results.items():
    print(
        f"  {mode}: trades={bt.n_trades}  wr={bt.win_rate:.0%}"
        f"  ret={bt.total_return:+.1%}  sharpe={bt.sharpe:.2f}  maxDD={bt.max_drawdown:.1%}"
    )
assert len(results) == 3
print("  [PASS]")

# ── AuditService ───────────────────────────────────────────────────────────
print("\n--- AuditService ---")
from tradingos.engines.audit_service import AuditService

asvc = AuditService()
asvc.log_event("PROFILE", "VCB", "BUY", mfpm_score=70, sms_raw=60, confidence="MEDIUM")
stats = asvc.summary_stats(days_back=30)
print(f"  total_events={stats['total_events']}")
print(f"  breakdown={stats['action_breakdown']}")
assert stats["total_events"] >= 1
print("  [PASS]")

# ── MoneyFlowService ───────────────────────────────────────────────────────
print("\n--- MoneyFlowService ---")
import tradingos.data.fetcher as fetcher_mod
fetcher_mod.fetch_ohlcv = lambda ticker, days=120, **kw: df_synth

from tradingos.engines.money_flow_service import MoneyFlowService
mfsvc = MoneyFlowService()
sms_data = mfsvc.get_sms("VCB")
dist = mfsvc.get_distribution_status("VCB")
print(f"  sms={sms_data.get('sms')}  label={sms_data.get('sms_label')}")
print(f"  dist_level={dist.get('level')}")
assert isinstance(sms_data.get("sms"), int)
print("  [PASS]")

# ── UI module imports ──────────────────────────────────────────────────────
print("\n--- UI imports (no Streamlit render) ---")
import os
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

from tradingos.ui.pages import profiler, scanner, money_flow, backtest, audit, settings
from tradingos.ui.components import (
    render_signal_card, render_horizon_table, render_shap_chart,
    render_sms_gauge, render_mcvd_chart, render_sector_heatmap,
    render_equity_curve, render_backtest_summary,
    render_audit_timeline, render_audit_stats,
)
print("  All UI modules imported OK")
print("  [PASS]")

# ── SRS §3.4 New Fields ────────────────────────────────────────────────────
print("\n--- TickerProfile SRS §3.4 fields ---")
assert hasattr(p, "gmo_omega"),   "missing gmo_omega"
assert hasattr(p, "amf_flags"),   "missing amf_flags"
assert hasattr(p, "sector_flow"), "missing sector_flow"
assert hasattr(p, "fol_net_5d"),  "missing fol_net_5d"
assert hasattr(p, "whale_pct_vol"), "missing whale_pct_vol"
assert isinstance(p.gmo_omega, float), "gmo_omega not float"
assert isinstance(p.amf_flags, list),  "amf_flags not list"
assert p.sector_flow in ("INFLOW", "NEUTRAL", "OUTFLOW"), f"bad sector_flow={p.sector_flow}"
assert isinstance(p.fol_net_5d, int),  "fol_net_5d not int"
print(f"  gmo_omega={p.gmo_omega:.3f}  sector_flow={p.sector_flow}")
print(f"  fol_net_5d={p.fol_net_5d}  whale_pct_vol={p.whale_pct_vol}")
print(f"  amf_flags={p.amf_flags}")
print("  [PASS]")

# ── ScannerService ─────────────────────────────────────────────────────────
print("\n--- ScannerService ---")
import tradingos.engines.scanner_service as ss_mod
ss_mod.fetch_ohlcv = lambda ticker, days=120, **kw: df_synth

from tradingos.engines.scanner_service import ScannerService
from tradingos.data.schemas import ScanRequest

scan_svc = ScannerService(max_workers=2)
scan_req = ScanRequest(tickers=["VCB", "HPG", "SSI"], limit=10)
scan_result = scan_svc.scan(scan_req)

print(f"  scanned={scan_result.tickers_scanned}  passed={scan_result.tickers_passed}")
assert scan_result.tickers_scanned == 3, "should scan all 3 tickers"
assert scan_result.tickers_passed == 3, "all tickers should return results (no filter)"
assert len(scan_result.results) == 3, "3 result items expected"

item = scan_result.results[0]
assert hasattr(item, "sms_label"),    "ScanResultItem missing sms_label"
assert hasattr(item, "stealth_accum"), "ScanResultItem missing stealth_accum"
assert item.sms_label in ("WHALE_BUYING","WHALE_DISTRIBUTING","MIXED","RETAIL_DRIVEN"), \
    f"bad sms_label={item.sms_label}"
assert isinstance(item.stealth_accum, bool), "stealth_accum not bool"
print(f"  item[0]: {item.ticker} action={item.action} sms_label={item.sms_label} stealth={item.stealth_accum}")
print("  [PASS]")

# ── Stealth Accumulation Detection ────────────────────────────────────────
print("\n--- Stealth Accumulation (core/money_flow) ---")
from tradingos.core.money_flow import detect_stealth_accumulation, proxy_whale_net_from_daily
from tradingos.core import compute_indicators

df_ind = compute_indicators(df_synth)
flow_df = proxy_whale_net_from_daily(df_ind)
stealth_result = detect_stealth_accumulation(df_ind, flow_df)
print(f"  detected={stealth_result['detected']}  confidence={stealth_result['confidence']}")
print(f"  days_active={stealth_result['days_active']}")
assert isinstance(stealth_result["detected"], bool), "detected not bool"
assert stealth_result["confidence"] in ("HIGH","MEDIUM","LOW"), "bad confidence"
print("  [PASS]")

# ── Distribution Warning ──────────────────────────────────────────────────
print("\n--- Whale Distribution Warning ---")
from tradingos.core.money_flow import detect_whale_distribution
dist_result = detect_whale_distribution(df_ind, flow_df)
assert "level" in dist_result, "missing 'level' key in dist result"
assert "warning_level" in dist_result, "missing 'warning_level' key in dist result"
assert dist_result["level"] in ("NONE","WATCH","CAUTION","EXIT","FORCED_EXIT"), \
    f"bad dist level={dist_result['level']}"
print(f"  level={dist_result['level']}  score={dist_result['score']}  flags={dist_result['flags']}")
print("  [PASS]")

# ── Backtest modes differ ─────────────────────────────────────────────────
print("\n--- Backtest mode differentiation ---")
mode_trades = {m: results[m].n_trades for m in results}
print(f"  trade counts: {mode_trades}")
mode_sets = [results[m].n_trades for m in ("MODE_A","MODE_B","MODE_W")]
assert not all(t == mode_sets[0] for t in mode_sets), \
    "All 3 modes returned identical trade counts — signals not differentiated"
for m, bt in results.items():
    assert -20 <= bt.sharpe <= 20, f"{m} sharpe out of range: {bt.sharpe}"
print("  [PASS]")

# ── Mode W path (high-SMS synthetic) ─────────────────────────────────────
print("\n--- Mode W path (forced high SMS) ---")
from tradingos.core.mfpm import compute_mfpm
from tradingos.core.indicators import compute_all as compute_all_ind

df_mw = df_synth.copy()
df_mw = compute_indicators(df_mw)
# Force a high-SMS result by injecting a mock sms_result
sms_mock = {
    "sms": 82,
    "sms_label": "WHALE_BUYING",
    "components": {
        "mcvd": 25, "vqs": 18, "fol": 12, "obv": 15, "amd": 8, "cvd_today": 8
    },
    "mcvd_detail": {
        "mcvd_5d": 500000, "mcvd_20d": 2000000,
        "mcvd_trend": "UP", "mcvd_vs_price": "CONFIRM",
        "consistency": 0.70, "mcvd_slope": 0.05, "data_source": "PROXY_OHLCV",
    },
    "stealth_detail": {"detected": True, "confidence": "HIGH"},
    "distribution_warning": "NONE",
    "fol_net_5d": 100000, "whale_pct_vol": 5.0, "sector_flow": "INFLOW",
}
amf_pass = {"decision": "PASS", "flags": []}
pat = {"best_pattern": "VCP", "pattern_bonus": 10}

mw_result = compute_mfpm(
    df=df_mw, sms_result=sms_mock, amf_result=amf_pass,
    pattern_result=pat, hmm_state="STEADY_BULL",
    amd_phase="ACCUMULATION", sector_flow="INFLOW",
)
print(f"  mode={mw_result['signal_mode']}  mfpm={mw_result['mfpm_score']}")
print(f"  mode_w_score={mw_result['mode_w_score']}  action={mw_result['action']}")
# With SMS=82, STEADY_BULL, ACCUMULATION, sector INFLOW — Mode W should fire
assert mw_result["signal_mode"] == "MODE_W", \
    f"Expected MODE_W but got {mw_result['signal_mode']}"
assert mw_result["action"] in ("BUY","STRONG_BUY","WATCH"), \
    f"Expected actionable signal, got {mw_result['action']}"
print("  [PASS]")

print("\n" + "=" * 40)
print("ALL TESTS PASSED")

