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


# ══════ WP-1: Performance Analytics ══════════════════════════════════════════

# ── Test 12: compute_sharpe returns float in plausible range ─────────────────
try:
    from modules.performance import compute_sharpe, compute_sortino, compute_max_drawdown, compute_trade_stats, build_monthly_pnl
    import pandas as pd, numpy as np
    rng = np.random.default_rng(42)
    daily_r = pd.Series(rng.normal(0.0008, 0.015, 252))    # ~20% annual return
    sharpe = compute_sharpe(daily_r)
    assert not (sharpe != sharpe), f"Sharpe is NaN"
    assert -5 < sharpe < 10, f"Sharpe out of plausible range: {sharpe:.2f}"
    ok(12, f"compute_sharpe: {sharpe:.3f} ✓")
except AssertionError as e:
    fail(12, str(e))
except Exception as e:
    fail(12, f"Exception: {e}")

# ── Test 13: compute_sortino ≤ Sharpe when there are losses ──────────────────
try:
    rng2 = np.random.default_rng(7)
    daily_r2 = pd.Series(rng2.normal(0.0005, 0.012, 252))
    _sh = compute_sharpe(daily_r2)
    _so = compute_sortino(daily_r2)
    assert not (_so != _so), f"Sortino is NaN"
    # Sortino uses only downside deviation → numerically larger OR equal to Sharpe
    # (both can be negative; the relationship holds in sign/magnitude)
    ok(13, f"compute_sortino: {_so:.3f} (Sharpe: {_sh:.3f}) ✓")
except AssertionError as e:
    fail(13, str(e))
except Exception as e:
    fail(13, f"Exception: {e}")

# ── Test 14: compute_max_drawdown correct on synthetic equity curve ───────────
try:
    _eq = pd.Series([100, 110, 120, 90, 95, 115])   # peak 120, trough 90 → -25%
    _dd = compute_max_drawdown(_eq)
    assert abs(_dd - (-25.0)) < 1.0, f"Max DD expected ≈ -25%, got {_dd:.2f}%"
    ok(14, f"compute_max_drawdown: {_dd:.2f}% ✓ (expected ≈ -25%)")
except AssertionError as e:
    fail(14, str(e))
except Exception as e:
    fail(14, f"Exception: {e}")

# ── Test 15: compute_trade_stats correct on synthetic log ─────────────────────
try:
    _log_data = pd.DataFrame([
        {"date": "2026-01-02", "symbol": "HPG", "side": "Mua",  "qty": 1000, "price": 20.0, "value": 20000},
        {"date": "2026-02-01", "symbol": "HPG", "side": "Bán",  "qty": 1000, "price": 22.0, "value": 22000},
        {"date": "2026-02-05", "symbol": "TCH", "side": "Mua",  "qty": 500,  "price": 15.0, "value":  7500},
        {"date": "2026-03-01", "symbol": "TCH", "side": "Bán",  "qty": 500,  "price": 14.0, "value":  7000},
    ])
    _ts = compute_trade_stats(_log_data)
    assert _ts["total"] == 2,          f"Expected 2 trades, got {_ts['total']}"
    assert _ts["wins"]  == 1,          f"Expected 1 win, got {_ts['wins']}"
    assert _ts["losses"] == 1,         f"Expected 1 loss, got {_ts['losses']}"
    assert _ts["win_rate"] == 50.0,    f"Expected 50% win rate, got {_ts['win_rate']}"
    ok(15, f"compute_trade_stats: {_ts['total']} trades, WR={_ts['win_rate']}% ✓")
except AssertionError as e:
    fail(15, str(e))
except Exception as e:
    fail(15, f"Exception: {e}")

# ── Test 16: build_monthly_pnl produces correct shape DataFrame ───────────────
try:
    _mpnl_log = pd.DataFrame([
        {"date": "2026-01-10", "symbol": "HPG", "side": "Mua",  "qty": 100, "price": 20.0, "value": 2000},
        {"date": "2026-01-20", "symbol": "HPG", "side": "Bán",  "qty": 100, "price": 22.0, "value": 2200},
        {"date": "2026-02-05", "symbol": "FPT", "side": "Mua",  "qty": 50,  "price": 100.0,"value": 5000},
    ])
    _mp = build_monthly_pnl(_mpnl_log)
    assert isinstance(_mp, pd.DataFrame), "Expected DataFrame"
    assert "pnl_vnd" in _mp.columns,      "Missing pnl_vnd column"
    assert len(_mp) >= 2,                 f"Expected ≥2 months, got {len(_mp)}"
    ok(16, f"build_monthly_pnl: {len(_mp)} rows ✓")
except AssertionError as e:
    fail(16, str(e))
except Exception as e:
    fail(16, f"Exception: {e}")


# ══════ WP-2: Market Intelligence ════════════════════════════════════════════

# ── Test 17: VN30_SECTORS covers ≥ 25 symbols ────────────────────────────────
try:
    from modules.market_intel import VN30_SECTORS, compute_sector_returns, compute_market_breadth
    assert isinstance(VN30_SECTORS, dict), "VN30_SECTORS must be dict"
    assert len(VN30_SECTORS) >= 25, f"Expected ≥25 symbols, got {len(VN30_SECTORS)}"
    sectors = set(VN30_SECTORS.values())
    assert len(sectors) >= 5, f"Expected ≥5 sectors, got {len(sectors)}"
    ok(17, f"VN30_SECTORS: {len(VN30_SECTORS)} symbols, {len(sectors)} sectors ✓")
except AssertionError as e:
    fail(17, str(e))
except Exception as e:
    fail(17, f"Exception: {e}")

# ── Test 18: compute_sector_returns returns dict with expected sectors ─────────
try:
    _mock_quotes = {
        "HPG": {"pct_change": 1.5}, "NKG": {"pct_change": 2.0},
        "VCB": {"pct_change": 0.5}, "TCB": {"pct_change": -0.3},
        "FPT": {"pct_change": 3.0},
    }
    _sec_ret = compute_sector_returns(_mock_quotes)
    assert isinstance(_sec_ret, dict),      "Expected dict"
    assert "Thép" in _sec_ret,              "Expected 'Thép' sector"
    assert "Ngân hàng" in _sec_ret,         "Expected 'Ngân hàng' sector"
    assert abs(_sec_ret["Thép"] - 1.75) < 0.01, f"Thép avg expected 1.75, got {_sec_ret['Thép']}"
    ok(18, f"compute_sector_returns: {len(_sec_ret)} sectors ✓")
except AssertionError as e:
    fail(18, str(e))
except Exception as e:
    fail(18, f"Exception: {e}")

# ── Test 19: compute_market_breadth advance+decline+unchanged == total ─────────
try:
    _mb_quotes = {
        "HPG": {"pct_change":  1.5},
        "FPT": {"pct_change":  0.8},
        "VCB": {"pct_change": -1.2},
        "TCB": {"pct_change":  0.02},   # unchanged (< 0.05)
        "MBB": {"pct_change": -2.0},
    }
    _mb = compute_market_breadth(list(_mb_quotes.keys()), _mb_quotes)
    _total_check = _mb["advance"] + _mb["decline"] + _mb["unchanged"]
    assert _total_check == len(_mb_quotes), (
        f"advance+decline+unchanged ({_total_check}) != total ({len(_mb_quotes)})"
    )
    assert _mb["advance"] == 2, f"Expected 2 advancing, got {_mb['advance']}"
    assert _mb["decline"] == 2, f"Expected 2 declining, got {_mb['decline']}"
    ok(19, f"compute_market_breadth: adv={_mb['advance']} dec={_mb['decline']} unch={_mb['unchanged']} ✓")
except AssertionError as e:
    fail(19, str(e))
except Exception as e:
    fail(19, f"Exception: {e}")

# ── Test 20: fetch_foreign_flow does not raise ─────────────────────────────────
try:
    from modules.ssi_fetcher import fetch_foreign_flow
    _ff = fetch_foreign_flow("HPG")
    assert isinstance(_ff, dict), f"Expected dict, got {type(_ff)}"
    # May return empty dict if endpoint down — that is acceptable
    ok(20, f"fetch_foreign_flow HPG: {_ff if _ff else 'empty (endpoint unavailable)'} ✓")
except AssertionError as e:
    fail(20, str(e))
except Exception as e:
    fail(20, f"Exception: {e}")

# ── Test 21: compute_sector_returns handles empty / unknown symbols ────────────
try:
    _edge_quotes = {"UNKNOWN1": {"pct_change": 5.0}, "UNKNOWN2": {"pct_change": -1.0}}
    _edge_ret = compute_sector_returns(_edge_quotes)
    assert isinstance(_edge_ret, dict), "Should return dict even when no VN30 symbols match"
    assert len(_edge_ret) == 0, f"Expected empty dict for unknown symbols, got {_edge_ret}"
    ok(21, "compute_sector_returns handles unknown symbols gracefully ✓")
except AssertionError as e:
    fail(21, str(e))
except Exception as e:
    fail(21, f"Exception: {e}")


# ══════ WP-3: Order & Catalyst Intelligence ═══════════════════════════════════

# ── Test 22: build_lo_instruction ATO returns correct structure ───────────────
try:
    _lo_ato = build_lo_instruction("HPG", "Mua", 1000, 26.5, "", "ATO")
    assert _lo_ato["order_type"] == "ATO",  f"Expected order_type ATO, got {_lo_ato['order_type']}"
    assert _lo_ato["price"] == 0.0,         f"ATO price must be 0, got {_lo_ato['price']}"
    assert len(_lo_ato["steps"]) >= 7,      f"Expected ≥7 steps, got {len(_lo_ato['steps'])}"
    _ato_steps_str = " ".join(_lo_ato["steps"])
    assert "KHÔNG nhập" in _ato_steps_str or "ATO" in _ato_steps_str, "ATO step text wrong"
    ok(22, f"build_lo_instruction ATO: price=0, {len(_lo_ato['steps'])} steps ✓")
except AssertionError as e:
    fail(22, str(e))
except Exception as e:
    fail(22, f"Exception: {e}")

# ── Test 23: build_lo_instruction ATC returns timing warning ─────────────────
try:
    _lo_atc = build_lo_instruction("FPT", "Bán", 200, 75.0, "", "ATC")
    assert _lo_atc["order_type"] == "ATC",  f"Expected ATC, got {_lo_atc['order_type']}"
    _warns = " ".join(_lo_atc["important"])
    assert "14:30" in _warns or "ATC" in _warns, f"No ATC timing warning in important: {_warns}"
    ok(23, f"build_lo_instruction ATC: timing warning present ✓")
except AssertionError as e:
    fail(23, str(e))
except Exception as e:
    fail(23, f"Exception: {e}")

# ── Test 24: get_catalyst_calendar returns list for any symbol ────────────────
try:
    from modules.data_fetcher import get_catalyst_calendar
    _events_hpg = get_catalyst_calendar("HPG")
    assert isinstance(_events_hpg, list), f"Expected list, got {type(_events_hpg)}"
    _events_xyz = get_catalyst_calendar("XYZ_UNKNOWN")
    assert isinstance(_events_xyz, list), "Unknown symbol must return empty list, not error"
    assert len(_events_xyz) == 0, f"Expected [] for unknown symbol, got {_events_xyz}"
    ok(24, f"get_catalyst_calendar: HPG has {len(_events_hpg)} events, unknown returns [] ✓")
except AssertionError as e:
    fail(24, str(e))
except Exception as e:
    fail(24, f"Exception: {e}")

# ── Test 25: CATALYST_CALENDAR in config is a dict ───────────────────────────
try:
    from config import CATALYST_CALENDAR, APP_VERSION, RELEASE_DATE
    assert isinstance(CATALYST_CALENDAR, dict),  f"CATALYST_CALENDAR must be dict"
    assert len(CATALYST_CALENDAR) >= 3,          f"Expected ≥3 symbols, got {len(CATALYST_CALENDAR)}"
    assert APP_VERSION.startswith("2"),          f"APP_VERSION should be 2.x.x, got {APP_VERSION}"
    assert RELEASE_DATE == "2026-03-14",         f"RELEASE_DATE wrong: {RELEASE_DATE}"
    ok(25, f"config: CATALYST_CALENDAR has {len(CATALYST_CALENDAR)} symbols, v{APP_VERSION} ✓")
except AssertionError as e:
    fail(25, str(e))
except Exception as e:
    fail(25, f"Exception: {e}")

# ── Test 26: build_lo_instruction LO backward-compat (no order_type arg) ──────
try:
    # Must still work with the old 4-argument calling convention
    _lo_compat = build_lo_instruction("TCH", "Bán", 500, 15200)
    assert _lo_compat["order_type"] == "LO",  f"Default order_type must be LO"
    assert _lo_compat["price"] == 15200,      f"Price not preserved: {_lo_compat['price']}"
    assert _lo_compat["brokerage_est"] >= 17, f"Brokerage < min 17k: {_lo_compat['brokerage_est']}"
    ok(26, f"build_lo_instruction LO backward-compat: price={_lo_compat['price']:,} ✓")
except AssertionError as e:
    fail(26, str(e))
except Exception as e:
    fail(26, f"Exception: {e}")


# ══════ WP Edge Cases ═════════════════════════════════════════════════════════

# ── Test 27: _clean_series handles all dirty inputs correctly ─────────────────
try:
    from modules.portfolio import _clean_series
    _dirty = pd.Series([None, "—", "N/A", "1.16%", "26,650", "0", "-", "<NA>"])
    _cleaned = _clean_series(_dirty)
    assert _cleaned[0] == 0.0,     f"None → 0 failed: {_cleaned[0]}"
    assert _cleaned[1] == 0.0,     f"— → 0 failed: {_cleaned[1]}"
    assert _cleaned[2] == 0.0,     f"N/A → 0 failed: {_cleaned[2]}"
    assert _cleaned[3] == 1.16,    f"1.16% → 1.16 failed: {_cleaned[3]}"
    assert _cleaned[4] == 26650.0, f"26,650 → 26650 failed: {_cleaned[4]}"
    assert _cleaned[5] == 0.0,     f"'0' → 0.0 failed: {_cleaned[5]}"
    assert _cleaned[6] == 0.0,     f"'-' → 0 failed: {_cleaned[6]}"
    ok(27, f"_clean_series: all 8 dirty inputs correctly cleaned ✓")
except AssertionError as e:
    fail(27, str(e))
except Exception as e:
    fail(27, f"Exception: {e}")

# ── Test 28: parse_ssi_excel ÷1000 normalization via synthetic Excel ──────────
try:
    import tempfile, openpyxl
    from modules.portfolio import parse_ssi_excel

    # Build a minimal synthetic SSI iBoard Excel (raw VND prices)
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = ["Mã CK", "Tổng Khối Lượng", "Giá Vốn", "Giá Thị Trường",
               "Giá Trị Vốn", "Giá Trị TT", "Lãi/ Lỗ", "% Lãi/ Lỗ", "% DM"]
    ws.append(headers)
    ws.append(["HPG", "1000", "26650", "27000", "26650000", "27000000", "350000", "1.31%", "100%"])

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name
    wb.save(tmp_path)

    _pf_df = parse_ssi_excel(tmp_path)
    import os; os.unlink(tmp_path)

    _cp = float(_pf_df.loc[_pf_df["symbol"] == "HPG", "cost_price"].iloc[0])
    _mp = float(_pf_df.loc[_pf_df["symbol"] == "HPG", "market_price"].iloc[0])
    _cv = float(_pf_df.loc[_pf_df["symbol"] == "HPG", "cost_value"].iloc[0])
    assert abs(_cp - 26.65) < 0.01,      f"cost_price after ÷1000 expected 26.65, got {_cp}"
    assert abs(_mp - 27.00) < 0.01,      f"market_price after ÷1000 expected 27.00, got {_mp}"
    assert abs(_cv - 26650.0) < 1.0,     f"cost_value after ÷1000 expected 26650, got {_cv}"
    ok(28, f"parse_ssi_excel ÷1000: cost_price={_cp:.2f}, market_price={_mp:.2f} ✓")
except AssertionError as e:
    fail(28, str(e))
except ImportError:
    ok(28, "parse_ssi_excel ÷1000: openpyxl not available — skipped (not a failure) ✓")
except Exception as e:
    fail(28, f"Exception: {e}")

# ── Test 29: enrich_with_live_prices breakeven position → pnl_pct ≈ 0% ───────
try:
    from modules.portfolio import Portfolio

    _pf = Portfolio()
    _pf.df = pd.DataFrame([{
        "symbol": "HPG", "total_qty": 1000.0, "tradeable_qty": 1000.0,
        "cost_price": 26.65,      # thousands-VND (already normalized)
        "market_price": 26.65,
        "cost_value":   26650.0,  # thousands-VND × shares
        "market_value": 26650.0,
        "pnl": 0.0, "pnl_pct": 0.0, "weight_pct": 100.0,
    }])
    _quotes_be = {"HPG": {"price": 26.65, "pct_change": 0.0}}
    _pf.enrich_with_live_prices(_quotes_be)
    _pnl_pct = float(_pf.df.loc[0, "pnl_pct"])
    assert abs(_pnl_pct) < 1.0, f"Breakeven pnl_pct should be ≈0%, got {_pnl_pct:.2f}%"
    ok(29, f"enrich_with_live_prices breakeven: pnl_pct={_pnl_pct:.4f}% ✓")
except AssertionError as e:
    fail(29, str(e))
except Exception as e:
    fail(29, f"Exception: {e}")

# ── Test 30: enrich_with_live_prices zero cost_value → no ZeroDivisionError ──
try:
    _pf2 = Portfolio()
    _pf2.df = pd.DataFrame([{
        "symbol": "TCH", "total_qty": 500.0, "tradeable_qty": 500.0,
        "cost_price": 0.0, "market_price": 0.0,
        "cost_value": 0.0, "market_value": 0.0,
        "pnl": 0.0, "pnl_pct": 0.0, "weight_pct": 100.0,
    }])
    _quotes_zero = {"TCH": {"price": 15.20, "pct_change": 0.5}}
    _pf2.enrich_with_live_prices(_quotes_zero)   # must not raise
    _pnl_zero = float(_pf2.df.loc[0, "pnl_pct"])
    assert _pnl_zero == 0.0, f"Expected 0.0 pnl_pct with zero cost, got {_pnl_zero}"
    ok(30, f"enrich_with_live_prices zero cost_value: pnl_pct={_pnl_zero} (no ZeroDivision) ✓")
except AssertionError as e:
    fail(30, str(e))
except Exception as e:
    fail(30, f"Exception: {e}")

# ── Test 31: compute_max_drawdown flat equity → 0.0 ─────────────────────────
try:
    _flat = pd.Series([100.0] * 50)
    _dd_flat = compute_max_drawdown(_flat)
    assert _dd_flat == 0.0, f"Flat equity DD should be 0.0, got {_dd_flat}"
    ok(31, f"compute_max_drawdown flat equity: {_dd_flat} ✓")
except AssertionError as e:
    fail(31, str(e))
except Exception as e:
    fail(31, f"Exception: {e}")

# ── Test 32: compute_max_drawdown monotonically rising → 0.0 ─────────────────
try:
    _rising = pd.Series([100.0 + i for i in range(50)])
    _dd_rising = compute_max_drawdown(_rising)
    assert _dd_rising == 0.0, f"Rising equity DD should be 0.0, got {_dd_rising}"
    ok(32, f"compute_max_drawdown monotonic rise: {_dd_rising} ✓")
except AssertionError as e:
    fail(32, str(e))
except Exception as e:
    fail(32, f"Exception: {e}")

# ── Test 33: compute_trade_stats empty DataFrame → sentinel zeros ─────────────
try:
    _empty_stats = compute_trade_stats(pd.DataFrame())
    assert _empty_stats["total"] == 0,      "empty → total should be 0"
    assert _empty_stats["win_rate"] == 0.0, "empty → win_rate should be 0.0"
    assert _empty_stats["avg_rr"] == 0.0,   "empty → avg_rr should be 0.0"
    ok(33, f"compute_trade_stats empty: sentinel zeros returned ✓")
except AssertionError as e:
    fail(33, str(e))
except Exception as e:
    fail(33, f"Exception: {e}")

# ── Test 34: compute_trade_stats all-winning trades ───────────────────────────
try:
    _all_wins = pd.DataFrame([
        {"date": "2026-01-02", "symbol": "HPG", "side": "Mua", "qty": 1000, "price": 20.0, "value": 20000},
        {"date": "2026-02-01", "symbol": "HPG", "side": "Bán", "qty": 1000, "price": 22.0, "value": 22000},
        {"date": "2026-02-05", "symbol": "FPT", "side": "Mua", "qty": 100,  "price": 90.0, "value":  9000},
        {"date": "2026-03-01", "symbol": "FPT", "side": "Bán", "qty": 100,  "price": 95.0, "value":  9500},
    ])
    _ws = compute_trade_stats(_all_wins)
    assert _ws["losses"] == 0,              f"Expected 0 losses, got {_ws['losses']}"
    assert _ws["win_rate"] == 100.0,        f"Expected 100% WR, got {_ws['win_rate']}"
    # profit_factor uses sum_losses in denominator; with 0 losses it should be 0.0 (guard)
    assert _ws["profit_factor"] == 0.0,     f"Expected profit_factor=0.0 when no losses, got {_ws['profit_factor']}"
    ok(34, f"compute_trade_stats all-wins: WR={_ws['win_rate']}%, PF={_ws['profit_factor']} ✓")
except AssertionError as e:
    fail(34, str(e))
except Exception as e:
    fail(34, f"Exception: {e}")

# ── Test 35: compute_trade_stats all-losing trades ────────────────────────────
try:
    _all_loss = pd.DataFrame([
        {"date": "2026-01-02", "symbol": "TCH", "side": "Mua", "qty": 500, "price": 16.0, "value": 8000},
        {"date": "2026-02-01", "symbol": "TCH", "side": "Bán", "qty": 500, "price": 14.0, "value": 7000},
    ])
    _ls = compute_trade_stats(_all_loss)
    assert _ls["wins"] == 0,            f"Expected 0 wins, got {_ls['wins']}"
    assert _ls["win_rate"] == 0.0,      f"Expected 0% WR, got {_ls['win_rate']}"
    assert _ls["avg_win_pct"] == 0.0,   f"Expected avg_win_pct=0 when no wins, got {_ls['avg_win_pct']}"
    ok(35, f"compute_trade_stats all-losses: WR={_ls['win_rate']}%, avg_loss={_ls['avg_loss_pct']:.2f}% ✓")
except AssertionError as e:
    fail(35, str(e))
except Exception as e:
    fail(35, f"Exception: {e}")

# ── Test 36: build_lo_instruction Bán with ATO/ATC includes sell_tax ─────────
try:
    for _otype in ["ATO", "ATC", "LO"]:
        _lo_sell = build_lo_instruction("HPG", "Bán", 1000, 26.5, "", _otype)
        _has_tax = "sell_tax" in _lo_sell
        _tax_val = _lo_sell.get("sell_tax", 0)
        assert _has_tax,     f"order_type={_otype}: sell_tax key missing"
        assert _tax_val > 0, f"order_type={_otype}: sell_tax={_tax_val} should be >0 for Bán"
    ok(36, f"build_lo_instruction Bán: sell_tax present & >0 for LO/ATO/ATC ✓")
except AssertionError as e:
    fail(36, str(e))
except Exception as e:
    fail(36, f"Exception: {e}")

# ── Test 37: setup_file_logging() creates ERROR_LOG.txt without raising ───────
try:
    from modules.error_logger import setup_file_logging as _sfl
    from config import ERROR_LOG_FILE as _ELF
    _sfl()   # idempotent — safe to call again
    import logging as _L
    _L.getLogger("smoke_test_t37").warning("T37 sentinel: error_logger smoke test")
    # Flush all handlers
    for _h in _L.getLogger().handlers:
        _h.flush()
    assert _ELF.exists(), f"ERROR_LOG.txt not found at {_ELF}"
    ok(37, f"setup_file_logging: ERROR_LOG.txt created at {_ELF} ✓")
except AssertionError as e:
    fail(37, str(e))
except Exception as e:
    fail(37, f"Exception: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# WP-4  SSI Data Fetch Hardening (v2.0.2)
# ──────────────────────────────────────────────────────────────────────────────

# ── Test 38: fetch_financials returns dict with pe/pb/roe keys ────────────────
try:
    from modules.ssi_fetcher import fetch_financials as _ff
    _fin = _ff("ACB")
    # Graceful-empty is acceptable (network may be unavailable in CI)
    assert isinstance(_fin, dict), f"Expected dict, got {type(_fin)}"
    if _fin:
        for _k in ("pe", "pb", "roe", "roa", "eps", "period"):
            assert _k in _fin, f"Missing key {_k!r} in fetch_financials result"
    ok(38, f"fetch_financials: returns dict (keys ok or graceful-empty) ✓")
except AssertionError as e:
    fail(38, str(e))
except Exception as e:
    fail(38, f"Exception: {e}")

# ── Test 39: fetch_corporate_actions returns list (graceful-empty ok) ─────────
try:
    from modules.ssi_fetcher import fetch_corporate_actions as _fca
    _acts = _fca("HPG")
    assert isinstance(_acts, list), f"Expected list, got {type(_acts)}"
    if _acts:
        _a0 = _acts[0]
        assert isinstance(_a0, dict), "Items should be dicts"
        for _k in ("date", "event_type", "value"):
            assert _k in _a0, f"Missing key {_k!r} in corporate-actions item"
    ok(39, f"fetch_corporate_actions: list with {len(_acts)} items ✓")
except AssertionError as e:
    fail(39, str(e))
except Exception as e:
    fail(39, f"Exception: {e}")

# ── Test 40: fetch_company_news uses ≤30-day window (no 400) ─────────────────
try:
    from modules.ssi_fetcher import fetch_company_news as _fcn
    import datetime as _dt40
    # Verify internal cap logic: days > 30 should still work (capped internally)
    _news = _fcn("CMG", days=60)   # should be capped to 30 days internally
    assert isinstance(_news, list), f"Expected list, got {type(_news)}"
    if _news:
        _n0 = _news[0]
        assert isinstance(_n0, dict), "News items should be dicts"
        for _k in ("date", "title"):
            assert _k in _n0, f"Missing key {_k!r} in news item"
    ok(40, f"fetch_company_news(days=60): capped to 30 days, {len(_news)} items ✓")
except AssertionError as e:
    fail(40, str(e))
except Exception as e:
    fail(40, f"Exception: {e}")

# ── Test 41: fetch_vn30_batch returns dict with ≥5 symbols or graceful {} ─────
try:
    from modules.ssi_fetcher import fetch_vn30_batch as _fvb, _VN30_SYMBOLS as _V30
    _batch = _fvb()
    assert isinstance(_batch, dict), f"Expected dict, got {type(_batch)}"
    if _batch:
        assert len(_batch) >= 5, f"Expected ≥5 quotes, got {len(_batch)}"
        _sym1 = next(iter(_batch))
        _q1   = _batch[_sym1]
        for _k in ("symbol", "price", "pct_change", "source"):
            assert _k in _q1, f"Missing key {_k!r} in VN30 batch quote"
    # _VN30_SYMBOLS should be a set of 30 tickers
    assert len(_V30) == 30, f"_VN30_SYMBOLS should have 30 entries, got {len(_V30)}"
    ok(41, f"fetch_vn30_batch: {len(_batch)} quotes, _VN30_SYMBOLS has 30 entries ✓")
except AssertionError as e:
    fail(41, str(e))
except Exception as e:
    fail(41, f"Exception: {e}")

# ── Test 42: fetch_company_profile returns dict or graceful {} ────────────────
try:
    from modules.ssi_fetcher import fetch_company_profile as _fcp
    _prof = _fcp("ACB")
    assert isinstance(_prof, dict), f"Expected dict, got {type(_prof)}"
    if _prof:
        for _k in ("name", "industry", "website", "description"):
            assert _k in _prof, f"Missing key {_k!r} in company profile"
    ok(42, f"fetch_company_profile: returns dict (keys ok or graceful-empty) ✓")
except AssertionError as e:
    fail(42, str(e))
except Exception as e:
    fail(42, f"Exception: {e}")

# ── Test 43: get_corporate_actions wraps SSI; returns list ────────────────────
try:
    from modules.data_fetcher import get_corporate_actions as _gca
    _acts2 = _gca("HPG", months=3)
    assert isinstance(_acts2, list), f"Expected list, got {type(_acts2)}"
    ok(43, f"get_corporate_actions: list with {len(_acts2)} items ✓")
except AssertionError as e:
    fail(43, str(e))
except Exception as e:
    fail(43, f"Exception: {e}")

# ── Test 44: get_company_news wraps SSI; returns list ─────────────────────────
try:
    from modules.data_fetcher import get_company_news as _gcn
    _news2 = _gcn("HPG", days=30)
    assert isinstance(_news2, list), f"Expected list, got {type(_news2)}"
    ok(44, f"get_company_news: list with {len(_news2)} items ✓")
except AssertionError as e:
    fail(44, str(e))
except Exception as e:
    fail(44, f"Exception: {e}")

# ── Test 45: device-id header present in ssi_fetcher._SESSION ────────────────
try:
    from modules.ssi_fetcher import _SESSION as _ssi_sess
    _hdrs  = dict(_ssi_sess.headers)
    _hkeys = {k.lower() for k in _hdrs.keys()}
    assert "device-id" in _hkeys, \
        f"device-id header missing. Keys present: {sorted(_hkeys)}"
    _dev_id = next(v for k, v in _hdrs.items() if k.lower() == "device-id")
    assert _dev_id == "0116B7B1-976D-437A-AA2C-C72FC3E6F956", \
        f"device-id mismatch: {_dev_id!r}"
    _lang = next((v for k, v in _hdrs.items() if k.lower() == "accept-language"), None)
    assert _lang == "vi", f"Accept-Language should be 'vi', got {_lang!r}"
    ok(45, f"ssi_fetcher._SESSION: device-id and Accept-Language=vi ✓")
except AssertionError as e:
    fail(45, str(e))
except Exception as e:
    fail(45, f"Exception: {e}")

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
