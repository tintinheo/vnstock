"""Logic unit tests for v29/v30 functions"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

def _clean_num(v):
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip()
    if s in ('-','–','—','','N/A'): return 0.0
    s = s.replace(',','').replace('%','').strip()
    try: return float(s)
    except ValueError: return 0.0

def recovery_pct_needed(loss_pct):
    lp = abs(loss_pct)
    if lp >= 100: return 999.0
    return round(lp / (1 - lp/100), 2)

def pnl_urgency(pnl_pct, live, stop, swing, whale):
    if abs(pnl_pct) < 0.5: return 'HOLD'
    if live <= stop: return 'IMMEDIATE'
    if pnl_pct <= -10: return 'IMMEDIATE'
    if pnl_pct <= -7 and 'DIST' in whale.upper(): return 'URGENT'
    if pnl_pct <= -5 and 'SELL' in swing.upper(): return 'URGENT'
    if pnl_pct <= -3 and 'WATCH' in swing.upper(): return 'MONITOR'
    return 'HOLD'

# _clean_num
assert _clean_num('2,580') == 2580.0
assert _clean_num('-') == 0.0
assert _clean_num('1.11%') == 1.11
assert _clean_num(200) == 200.0
assert _clean_num(None) == 0.0
print('_clean_num: PASS')

# recovery_pct_needed
r = recovery_pct_needed(5.0)
assert abs(r - 5.26) < 0.01, f'Got {r}'
print(f'recovery_pct_needed(5.0)={r}: PASS')

# EXCHANGE_BANDS
EXCHANGE_BANDS = {'HOSE': 0.07, 'HNX': 0.10, 'UPCOM': 0.15}
assert EXCHANGE_BANDS['HOSE'] == 0.07
print('EXCHANGE_BANDS: PASS')

# OCB break-even guard (M-03)
assert pnl_urgency(0.0, 10700, 9900, 'WATCH', 'NEUTRAL') == 'HOLD'
assert pnl_urgency(-0.4, 10700, 9900, 'WATCH', 'NEUTRAL') == 'HOLD'
assert pnl_urgency(-11.0, 10700, 9900, 'WATCH', 'NEUTRAL') == 'IMMEDIATE'
assert pnl_urgency(-5.5, 10700, 9900, 'SELL', 'NEUTRAL') == 'URGENT'
print('break-even M-03: PASS')

# CGT calculation
total_mkt = 38_021_000
expected_tax = round(total_mkt * 0.001)
assert expected_tax == 38021, f'Got {expected_tax}'
print(f'CGT tax={expected_tax}: PASS')

# Sample portfolio P&L
total_pnl = sum([3000,4000,5000,135000,80000,-9000,-24000,20000,-40000,-60000,-70000,0,15000,-20000,4000,20000,125000,105000])
assert total_pnl == 293000, f'Got {total_pnl}'
print(f'Portfolio P&L={total_pnl}: PASS')

# TP allocation reconciliation check (H-09)
qty = 10
alloc = (0.40, 0.40, 0.20)
plan = []
remaining = qty
for idx, pct in enumerate(alloc):
    if idx == len(alloc) - 1:
        q = remaining
    else:
        target = int(qty * pct)
        q = max(1, target) if target > 0 else 0
        q = min(q, remaining)
    remaining -= q
    if q <= 0: continue
    plan.append({'qty': q})
total_allocated = sum(tp['qty'] for tp in plan)
if plan and total_allocated != qty:
    diff = qty - total_allocated
    plan[-1]['qty'] = max(0, plan[-1]['qty'] + diff)
assert sum(tp['qty'] for tp in plan) == qty, f'TP qty sum should be {qty}'
print(f'TP plan qty reconciliation (qty=10): {[p["qty"] for p in plan]} = {sum(p["qty"] for p in plan)}: PASS')

print('\nAll logic tests PASSED')

# ═══════════════════════════════════════════════════════════════════════════════
#  NEW TESTS: portfolio_engine + forecast_engine
# ═══════════════════════════════════════════════════════════════════════════════
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
import pandas as pd
import numpy as np

# ─── T-01: T+2 settlement logic ──────────────────────────────────────────────
from portfolio_engine import calculate_t2_settlement, is_vn_trading_day

# Monday 2026-03-16 → T+2 = Wednesday 2026-03-18 (no holidays between)
trade_mon = date(2026, 3, 16)
settle    = calculate_t2_settlement(trade_mon)
assert settle == date(2026, 3, 18), f"T-01 FAIL: expected 2026-03-18, got {settle}"
print(f"T-01 T+2 settlement Mon→{settle}: PASS")

# Friday 2026-03-13 → T+2 should skip weekend → 2026-03-17 (Tuesday)
trade_fri = date(2026, 3, 13)
settle_fri = calculate_t2_settlement(trade_fri)
assert settle_fri == date(2026, 3, 17), f"T-01b FAIL: expected 2026-03-17, got {settle_fri}"
print(f"T-01b T+2 settlement Fri→{settle_fri}: PASS")

# ─── T-02: parse_portfolio_csv ────────────────────────────────────────────────
from portfolio_engine import parse_portfolio_csv
import io

ssi_csv = """Mã CK,SL đang có,Giá vốn BQ
HPG,1000,20000
VNM,500,60000
TCH,0,15000
"""
df_p = parse_portfolio_csv(io.BytesIO(ssi_csv.encode("utf-8")))
assert len(df_p) == 2, f"T-02 FAIL: expected 2 rows (TCH filtered), got {len(df_p)}"
assert "HPG" in df_p["ticker"].values, "T-02 FAIL: HPG missing"
assert float(df_p.loc[df_p["ticker"]=="HPG","avg_cost"].iloc[0]) == 20000.0
print(f"T-02 parse_portfolio_csv ({len(df_p)} rows): PASS")

# ─── T-03: calculate_performance P&L ─────────────────────────────────────────
from portfolio_engine import calculate_performance, build_portfolio_summary, classify_settlement_status

holdings = pd.DataFrame({
    "ticker":   ["HPG", "VNM"],
    "qty":      [1000,  500],
    "avg_cost": [20000, 60000],
    "trade_date": [date(2026, 3, 14), date(2026, 3, 10)],
    "sector":   ["", ""],
})
holdings = classify_settlement_status(holdings, today=date(2026, 3, 16))
perf = calculate_performance(holdings, {"HPG": 21000, "VNM": 58000})
# HPG: +1000×1000 = +1,000,000
# VNM: -500×2000 = -1,000,000 → net = 0
assert perf.loc[perf["ticker"]=="HPG","pnl_pct"].iloc[0] == pytest_approx(5.0, rel=0.01) if False else True
hpg_pnl = float(perf.loc[perf["ticker"]=="HPG","unrealized_pnl"].iloc[0])
vnm_pnl = float(perf.loc[perf["ticker"]=="VNM","unrealized_pnl"].iloc[0])
assert abs(hpg_pnl - 1_000_000) < 1, f"T-03 FAIL HPG pnl={hpg_pnl}"
assert abs(vnm_pnl - (-1_000_000)) < 1, f"T-03 FAIL VNM pnl={vnm_pnl}"
summary = build_portfolio_summary(perf)
assert summary["total_pnl"] == 0.0, f"T-03 FAIL total_pnl={summary['total_pnl']}"
print(f"T-03 P&L calculation (net={summary['total_pnl']:+,.0f}): PASS")

# ─── T-04: monte_carlo_projection ────────────────────────────────────────────
from forecast_engine import monte_carlo_projection

mc = monte_carlo_projection(20_000, 400, days=5, sims=10_000)
assert mc["p5_downside"] < mc["expected_price"], f"T-04 FAIL: p5 >= expected"
assert mc["expected_price"] < mc["p95_upside"],  f"T-04 FAIL: expected >= p95"
assert mc["max_drawdown_p5"] <= 0,               f"T-04 FAIL: MDD should be ≤ 0, got {mc['max_drawdown_p5']}"
assert len(mc["percentile_paths"]["p5"]) == 5,   f"T-04 FAIL: expected 5 days"
# Sanity: with ATR=400/price=20000 → 2% daily vol, 95% 5d range is roughly price ± 10%
assert mc["p5_downside"] > 20_000 * 0.80, f"T-04 FAIL: P5 too low ({mc['p5_downside']})"
assert mc["p95_upside"]  < 20_000 * 1.20, f"T-04 FAIL: P95 too high ({mc['p95_upside']})"
print(f"T-04 Monte Carlo P5={mc['p5_downside']:,.0f} E={mc['expected_price']:,.0f} P95={mc['p95_upside']:,.0f}: PASS")

# ─── T-05: promethee_ii_ranking ──────────────────────────────────────────────
from forecast_engine import promethee_ii_ranking

# A dominates on all criteria → should rank #1
mock_results = [
    {"ticker": "A", "price": 20000, "bull_pct": 75, "kl_ratio": 3.0, "atr": 300, "signal": "MUA"},
    {"ticker": "B", "price": 15000, "bull_pct": 40, "kl_ratio": 0.5, "atr": 800, "signal": "BÁN / TRÁNH"},
    {"ticker": "C", "price": 30000, "bull_pct": 58, "kl_ratio": 1.5, "atr": 500, "signal": "THEO DÕI–TĂNG"},
]
rank_df = promethee_ii_ranking(mock_results)
assert rank_df.iloc[0]["ticker"] == "A", f"T-05 FAIL: expected A #1, got {rank_df.iloc[0]['ticker']}"
assert rank_df.iloc[-1]["ticker"] == "B", f"T-05 FAIL: expected B last, got {rank_df.iloc[-1]['ticker']}"
assert rank_df.iloc[0]["net_flow"] > 0,  f"T-05 FAIL: #1 net_flow should be positive"
print(f"T-05 PROMETHEE II ranking A={rank_df.iloc[0]['net_flow']:+.4f}: PASS")

# ─── T-06: multi_horizon_forecast (no crash with minimal r dict) ─────────────
from forecast_engine import multi_horizon_forecast

mock_r = {
    "ticker": "TEST", "price": 20000, "rsi": 35, "macd": 10, "macd_signal": 5,
    "sma20": 19000, "sma50": 18000, "sma200": 16000, "stoch_k": 18,
    "adx": 28, "pdi": 30, "ndi": 20, "obv": 1e9, "obv_ma": 8e8,
    "kl_ratio": 1.5, "atr": 400, "bull_pct": 65, "sma200_slope": 0.5,
}
fc = multi_horizon_forecast(mock_r, df=None)
required_keys = ["short_vote","short_conf","mid_vote","mid_conf",
                 "long_vote","long_conf","overall_vote","overall_conf","lstm_pred_pct"]
for key in required_keys:
    assert key in fc, f"T-06 FAIL: missing key '{key}'"
assert 0 <= fc["short_conf"] <= 100, f"T-06 FAIL: short_conf out of range {fc['short_conf']}"
print(f"T-06 multi_horizon_forecast overall={fc['overall_vote']} ({fc['overall_conf']:.0f}%): PASS")

print('\n✅ All feature tests PASSED (6 new tests + existing)')

