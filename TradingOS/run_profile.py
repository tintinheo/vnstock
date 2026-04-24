"""One-shot profiler CLI — run analysis on multiple tickers and print results."""
import sys
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, "d:/portfolio/vnstock/TradingOS/src")

from tradingos.engines.profiler_service import ProfilerService
from tradingos.data.schemas import ProfilerRequest

tickers = [
    "CTD","ACB","AAA","EIB","LCG","PVT","VCB","SHB","VID","CPC",
    "MBB","CLC","DC4","FPT","KDH","OGC","SRC","VCI","DTG","PGN",
    "SCI","DSE","NVL","CII","ICT","IMP","SSB","TPB","BAB","IDC",
    "L14","PCE","ONE",
]
svc = ProfilerService(portfolio_value=300_000_000)

for t in tickers:
    try:
        req = ProfilerRequest(ticker=t)
        p = svc.run(req)
        print(f"=== {t} ===")
        print(f"  action={p.action}  conf={p.confidence}  mode={p.signal_mode}")
        print(f"  mfpm={p.mfpm_score}  mc_prob={p.mc_win_prob:.0%}")
        print(f"  close={p.close:,.0f}  entry={p.entry_price:,.0f}  sl={p.stop_loss:,.0f}")
        print(f"  tp1={p.tp1:,.0f}  tp2={p.tp2:,.0f}  RR={p.rr_ratio:.2f}  sl_pct={p.sl_pct:.1f}%")
        print(f"  sms={p.sms_raw}  label={p.sms_label}  mcvd_5d={p.mcvd_5d:+,.0f}  trend={p.mcvd_trend}")
        print(f"  amd={p.amd_phase}  hmm={p.hmm_state}  rsi={p.rsi14:.1f}")
        print(f"  sector={p.sector}  sector_flow={p.sector_flow}")
        print(f"  stealth={p.stealth_accum}  dist_warn={p.distribution_warning}")
        print(f"  sizing={p.sizing_pct:.1f}%  shares={p.sizing_shares}")
        macro_regime = getattr(p, "macro_regime", "—")
        macro_score  = getattr(p, "macro_score",  0)
        h_short = getattr(p, "horizon_short_vote", "—")
        h_mid   = getattr(p, "horizon_mid_vote",   "—")
        h_long  = getattr(p, "horizon_long_vote",  "—")
        print(f"  macro_regime={macro_regime}  macro_score={macro_score:.0f}")
        print(f"  horizon short={h_short}  mid={h_mid}  long={h_long}")
        print(f"  advisory: {p.advisory_text[:120]}")
        print()
    except Exception as e:
        print(f"{t} ERROR: {e}")
        import traceback; traceback.print_exc()
        print()
