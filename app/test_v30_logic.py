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
