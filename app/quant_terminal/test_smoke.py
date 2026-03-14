"""
Smoke test for Captain Seventh Quant Terminal.
Run from quant_terminal/ directory:
    python test_smoke.py
"""
import sys
import os
import datetime

sys.path.insert(0, os.path.dirname(__file__))

passed = 0
failed = 0
_results = []


def ok(n, msg):
    global passed
    passed += 1
    print(f"OK  [{n:02d}] {msg}")
    _results.append((n, True, msg))


def fail(n, msg):
    global failed
    failed += 1
    print(f"FAIL[{n:02d}] {msg}")
    _results.append((n, False, msg))


# ── Test 1: All imports ───────────────────────────────────────────────────────
try:
    from modules.data_fetcher import get_history, get_quote, get_quotes_batch, get_financials
    from modules.analysis import compute_indicators, compute_signal_score, find_support_resistance
    from modules.scenarios import generate_scenarios, build_lo_instruction, current_session
    from modules.portfolio import Portfolio, is_settled
    from config import PORTFOLIO_DIR, TRADE_LOG_DIR, KELLY_FRACTION
    ok(1, "All imports OK")
except Exception as e:
    fail(1, f"Import error: {e}")
    sys.exit(1)

# ── Test 2: History fetch returns data with normalized price ──────────────────
try:
    df = get_history("TCH", 60)
    assert df is not None and not df.empty, "Empty DataFrame returned"
    assert "close" in df.columns, "No 'close' column"
    med = df["close"].median()
    assert med < 1000, f"Price NOT normalized — median={med:.1f} (raw VND?)"
    assert len(df) >= 30, f"Too few rows: {len(df)}"
    ok(2, f"get_history TCH: {len(df)} rows, median_close={med:.2f} ✓ (normalized)")
except AssertionError as e:
    fail(2, str(e))
except Exception as e:
    fail(2, f"Exception: {e}")

# ── Test 3: Bollinger Bands — upper must be strictly > lower ─────────────────
try:
    df = get_history("TCH", 80)
    df_ind = compute_indicators(df)
    last = df_ind.iloc[-1]
    assert not (last["bb_upper"] != last["bb_upper"]), "bb_upper is NaN"
    assert not (last["bb_lower"] != last["bb_lower"]), "bb_lower is NaN"
    assert last["bb_upper"] > last["bb_lower"], (
        f"BB INVERTED: upper={last['bb_upper']:.2f} <= lower={last['bb_lower']:.2f}"
    )
    ok(3, f"BB sanity: upper={last['bb_upper']:.2f} > lower={last['bb_lower']:.2f} ✓")
except AssertionError as e:
    fail(3, str(e))
except Exception as e:
    fail(3, f"Exception: {e}")

# ── Test 4: MACD — histogram must equal macd - signal ────────────────────────
try:
    df = get_history("HPG", 80)
    df_ind = compute_indicators(df)
    last = df_ind.iloc[-1]
    computed_hist = last["macd"] - last["macd_signal"]
    stored_hist   = last["macd_hist"]
    diff = abs(computed_hist - stored_hist)
    assert diff < 0.01, (
        f"MACD hist mismatch: computed={computed_hist:.4f}, stored={stored_hist:.4f}"
    )
    ok(4, f"MACD histogram consistent: {stored_hist:.4f} == macd - signal ✓")
except AssertionError as e:
    fail(4, str(e))
except Exception as e:
    fail(4, f"Exception: {e}")

# ── Test 5: Signal score within valid range ───────────────────────────────────
try:
    df = get_history("CII", 80)
    sig = compute_signal_score(df)
    assert "score" in sig and "label" in sig, "Missing keys in signal result"
    assert -100 <= sig["score"] <= 100, f"Score out of range: {sig['score']}"
    assert sig["label"], "Empty label"
    ok(5, f"Signal CII: score={sig['score']} label=[{sig['label']}] ✓")
except AssertionError as e:
    fail(5, str(e))
except Exception as e:
    fail(5, f"Exception: {e}")

# ── Test 6: Scenarios — R:R, EV, order P&L non-zero ─────────────────────────
try:
    df = get_history("TCH", 100)
    sc = generate_scenarios(
        "TCH",
        cost_price=14.475,
        market_price=15.10,
        qty=1000,
        hist_df=df,
    )
    assert sc["bull_target"] > sc["stop_loss"], (
        f"bull_target ({sc['bull_target']:.2f}) <= stop_loss ({sc['stop_loss']:.2f})"
    )
    assert sc["rr_bull"] > 0, f"R:R bull = {sc['rr_bull']}"
    order_pnls = [o["pnl_est"] for o in sc["orders"]]
    non_zero = [p for p in order_pnls if p != 0]
    assert len(non_zero) >= 2, f"Most order P&Ls are 0: {order_pnls}"
    ok(6, (
        f"Scenarios TCH: bull={sc['bull_target']:.2f}, stop={sc['stop_loss']:.2f}, "
        f"RR={sc['rr_bull']}, pnls={[round(p) for p in order_pnls]} ✓"
    ))
except AssertionError as e:
    fail(6, str(e))
except Exception as e:
    fail(6, f"Exception: {e}")

# ── Test 7: T+2 settlement logic ─────────────────────────────────────────────
try:
    # Tuesday 11 Mar → settled by Thursday 13 Mar (T+2 business days)
    assert is_settled(datetime.date(2026, 3, 11), as_of=datetime.date(2026, 3, 13)), \
        "11 Mar should be settled by 13 Mar"
    # Same-day trade should NOT be settled
    assert not is_settled(datetime.date(2026, 3, 13), as_of=datetime.date(2026, 3, 13)), \
        "Same-day trade should not be settled"
    # Friday trade → settled Monday+2 business days = Wednesday
    assert is_settled(datetime.date(2026, 3, 13), as_of=datetime.date(2026, 3, 17)), \
        "Friday 13 Mar should be settled by Tuesday 17 Mar (skip weekend)"
    ok(7, "T+2 settlement logic correct for weekday and weekend cases ✓")
except AssertionError as e:
    fail(7, str(e))
except Exception as e:
    fail(7, f"Exception: {e}")

# ── Test 8: LO order builder ─────────────────────────────────────────────────
try:
    lo = build_lo_instruction("TCH", "Bán", 500, 15200)
    assert lo["price"] == 15200, f"Price not tick-rounded correctly: {lo['price']}"
    assert lo["brokerage_est"] > 0, "Brokerage fee is 0"
    assert len(lo["steps"]) >= 7, f"Not enough steps: {len(lo['steps'])}"
    assert len(lo["important"]) >= 3, f"Not enough important notes"
    assert lo["value"] == 15200 * 500, f"Value calc wrong: {lo['value']}"
    ok(8, f"LO builder: price={lo['price']:,}, fee={lo['brokerage_est']:,}đ, {len(lo['steps'])} steps ✓")
except AssertionError as e:
    fail(8, str(e))
except Exception as e:
    fail(8, f"Exception: {e}")

# ── Test 9: Support below & resistance above current price ───────────────────
try:
    df = get_history("HPG", 120)
    sr = find_support_resistance(df)
    cur = df["close"].iloc[-1]
    assert sr["resistance"], "No resistance levels found"
    assert sr["support"],    "No support levels found"
    has_resistance_above = any(r > cur for r in sr["resistance"])
    has_support_below    = any(s < cur for s in sr["support"])
    assert has_resistance_above, f"No resistance above {cur:.2f}: {sr['resistance']}"
    assert has_support_below,    f"No support below {cur:.2f}: {sr['support']}"
    ok(9, f"S/R HPG @ {cur:.2f}: sup={sr['support']}, res={sr['resistance']} ✓")
except AssertionError as e:
    fail(9, str(e))
except Exception as e:
    fail(9, f"Exception: {e}")

# ── Test 10: Quote price normalized ──────────────────────────────────────────
try:
    q = get_quote("HPG")
    assert q["price"] > 0, "Price is 0"
    assert q["price"] < 1000, (
        f"Price not normalized: {q['price']:.1f} (should be ~26.x, not raw VND)"
    )
    assert "source" in q, "No 'source' key in quote — multi-source tracking missing"
    ok(10, f"Quote HPG: price={q['price']:.2f}, chg={q['pct_change']:+.2f}%, src={q.get('source','?')} ✓")
except AssertionError as e:
    fail(10, str(e))
except Exception as e:
    fail(10, f"Exception: {e}")

# ── Test 11: Empty portfolio edge cases ──────────────────────────────────────
try:
    from modules.portfolio import Portfolio
    pf_empty = Portfolio()
    syms = pf_empty.tradeable_symbols()
    assert syms == [], f"Expected [], got {syms}"
    pos = pf_empty.get_position("HPG")
    assert pos is None, f"Expected None, got {pos}"
    ok(11, f"Empty portfolio: tradeable_symbols=[], get_position=None ✓")
except AssertionError as e:
    fail(11, str(e))
except Exception as e:
    fail(11, f"Exception: {e}")

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 55)
print(f"  SMOKE TEST RESULT: {passed}/{passed + failed} passed, {failed} failed")
print("=" * 55)

if failed:
    print("\nFailed tests:")
    for n, ok_flag, msg in _results:
        if not ok_flag:
            print(f"  [{n:02d}] {msg}")
    sys.exit(1)
else:
    print("  All tests passed ✓")
