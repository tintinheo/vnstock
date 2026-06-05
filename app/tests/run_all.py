"""
run_all.py — run the full VN-Swing Alpha test suite and report results.

Usage (from app root or tests/):
    python tests/run_all.py
"""
from __future__ import annotations
import subprocess
import sys
import os
import time

# Ensure app root is on path
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PYTHON = sys.executable

TESTS = [
    ("test_improvements.py",   "VN-Swing Alpha Improvements"),
    ("test_v30_logic.py",      "v30 Logic"),
    ("test_signal_filter.py",  "Signal Filter"),
    ("test_trend_warning.py",  "Trend Warning Engine"),
]

def run_test(filename: str, label: str) -> tuple[bool, float, str]:
    path = os.path.join(_TESTS_DIR, filename)
    t0   = time.time()
    result = subprocess.run(
        [_PYTHON, path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=_APP_DIR,
    )
    elapsed = time.time() - t0
    passed  = result.returncode == 0
    output  = (result.stdout + result.stderr).strip()
    return passed, elapsed, output


if __name__ == "__main__":
    print("=" * 62)
    print("  VN-Swing Alpha — Full Test Suite")
    print("=" * 62)

    total_pass = 0
    total_fail = 0

    for filename, label in TESTS:
        passed, elapsed, output = run_test(filename, label)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n[{status}]  {label}  ({elapsed:.1f}s)")
        if not passed:
            print("  --- output ---")
            for line in output.splitlines()[-20:]:
                print("  " + line)
            total_fail += 1
        else:
            # Print last summary line from the test
            for line in reversed(output.splitlines()):
                if "PASSED" in line or "PASS" in line:
                    print(f"  {line.strip()}")
                    break
            total_pass += 1

    print()
    print("=" * 62)
    print(f"  {total_pass} passed  /  {total_fail} failed  /  {total_pass + total_fail} total")
    print("=" * 62)

    sys.exit(0 if total_fail == 0 else 1)
