#!/usr/bin/env python3
"""test_data_live.py – Verify KBS(IIS) + CafeF returns real prices."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("=" * 60)
    print("  REAL DATA TEST (KBS IIS + CafeF)")
    print("=" * 60)

    from data.data_manager import DataManager, DataUnavailableError

    EXPECTED = {
        "VCG": (15000, 35000),
        "FPT": (50000, 200000),
        "HPG": (15000, 50000),
        "VCB": (50000, 150000),
        "TCB": (30000, 80000),
    }

    dm = DataManager()
    passed = failed = 0

    for ticker, (lo, hi) in EXPECTED.items():
        try:
            df = dm.get_ohlcv(ticker)
            src = dm.get_data_source(df)
            last = df["close"].iloc[-1]
            dt = df["date"].iloc[-1].strftime("%Y-%m-%d")
            ok = lo <= last <= hi
            tag = "OK" if ok else "XX"
            print(f"  {tag} {ticker}: {last:>10,.0f} VND | {src:8s} | {len(df):>5} bars | {dt}")
            if ok: passed += 1
            else: failed += 1; print(f"       Expected {lo:,}-{hi:,}")
        except DataUnavailableError as e:
            print(f"  XX {ticker}: UNAVAILABLE")
            failed += 1
        except Exception as e:
            print(f"  XX {ticker}: {type(e).__name__}: {e}")
            failed += 1

        time.sleep(1)

    print(f"\n{'='*60}")
    print(f"  {passed}/{len(EXPECTED)} passed")
    if failed == 0: print("  ALL VERIFIED!")
    print("="*60)

if __name__ == "__main__":
    main()
