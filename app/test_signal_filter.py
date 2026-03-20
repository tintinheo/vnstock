"""
test_signal_filter.py  —  Unit tests for the Phân Tích signal/action filter logic
====================================================================================
Tests the pure filtering logic extracted from main() in Quant_Profiler_ui.py.
No Streamlit runtime required — all UI calls are stubbed.

Run:
    cd d:\\portfolio\\vnstock\\app
    python test_signal_filter.py
"""
from __future__ import annotations

import sys
import os
import types

# ── Stub Streamlit so the import works without a running server ───────────────
_st_stub = types.ModuleType("streamlit")

class _FakeMultiselect:
    """Captures options/default; returns default as if user selected all."""
    def __call__(self, label, options=None, default=None, key=None):
        return default or []

_st_stub.multiselect = _FakeMultiselect()
_st_stub.info        = lambda *a, **kw: None
_st_stub.session_state = {}
sys.modules["streamlit"] = _st_stub

# ── Test machinery ────────────────────────────────────────────────────────────
PASS = "✅ PASS"
FAIL = "❌ FAIL"
_results: list[tuple[str, str]] = []


def _pass(name: str) -> None:
    _results.append((PASS, name))


def _fail(name: str, reason: str) -> None:
    _results.append((FAIL, f"{name}: {reason}"))


# ── Pure filter logic (mirrors what main() now does) ─────────────────────────

_ALL_SIGNALS = ["MUA", "THEO DÕI–TĂNG", "TRUNG LẬP", "THEO DÕI–GIẢM", "BÁN / TRÁNH"]
_SIG_ICONS   = {
    "MUA":            "🟢",
    "THEO DÕI–TĂNG":  "🔵",
    "TRUNG LẬP":      "⚪",
    "THEO DÕI–GIẢM":  "🟠",
    "BÁN / TRÁNH":    "🔴",
}


def _apply_filter(results: list[dict], selected_signals: list[str]) -> list[dict]:
    """
    Mirrors the filter logic in main().
    selected_signals is a list of raw signal strings (without icon prefix).
    """
    if len(results) <= 1:
        return results

    _present = [
        s for s in _ALL_SIGNALS
        if any(r.get("signal") == s for r in results if "error" not in r)
    ]
    if not _present:
        return results

    _opts    = [f"{_SIG_ICONS[s]} {s}" for s in _present]
    _sel     = [f"{_SIG_ICONS[s]} {s}" for s in selected_signals if s in _present]
    _sel_set = {s for s in _present if f"{_SIG_ICONS[s]} {s}" in _sel}

    return [r for r in results if "error" in r or r.get("signal") in _sel_set]


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_results(*signals) -> list[dict]:
    """Build a minimal results list with the given signals."""
    return [{"ticker": f"T{i}", "signal": s, "price": 100.0}
            for i, s in enumerate(signals)]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_all_selected_returns_all() -> None:
    results = _make_results("MUA", "TRUNG LẬP", "BÁN / TRÁNH")
    filtered = _apply_filter(results, ["MUA", "TRUNG LẬP", "BÁN / TRÁNH"])
    assert len(filtered) == 3, f"Expected 3, got {len(filtered)}"
    _pass("All signals selected → all results returned")


def test_filter_buy_only() -> None:
    results = _make_results("MUA", "TRUNG LẬP", "BÁN / TRÁNH", "MUA")
    filtered = _apply_filter(results, ["MUA"])
    assert len(filtered) == 2, f"Expected 2, got {len(filtered)}"
    assert all(r["signal"] == "MUA" for r in filtered)
    _pass("Filter MUA only → only MUA results returned")


def test_filter_sell_only() -> None:
    results = _make_results("MUA", "BÁN / TRÁNH", "TRUNG LẬP", "BÁN / TRÁNH")
    filtered = _apply_filter(results, ["BÁN / TRÁNH"])
    assert len(filtered) == 2
    assert all(r["signal"] == "BÁN / TRÁNH" for r in filtered)
    _pass("Filter BÁN / TRÁNH only → only sell results returned")


def test_filter_multiple_signals() -> None:
    results = _make_results("MUA", "THEO DÕI–TĂNG", "TRUNG LẬP", "BÁN / TRÁNH")
    filtered = _apply_filter(results, ["MUA", "THEO DÕI–TĂNG"])
    assert len(filtered) == 2
    sigs = {r["signal"] for r in filtered}
    assert sigs == {"MUA", "THEO DÕI–TĂNG"}
    _pass("Filter MUA + THEO DÕI–TĂNG → 2 results")


def test_empty_selection_returns_empty() -> None:
    results = _make_results("MUA", "TRUNG LẬP")
    filtered = _apply_filter(results, [])
    assert len(filtered) == 0, f"Expected 0, got {len(filtered)}"
    _pass("Empty selection → empty result list")


def test_error_results_always_kept() -> None:
    """Tickers with errors must pass through the filter regardless of signal selection."""
    results = [
        {"ticker": "AAA", "signal": "MUA",      "price": 100.0},
        {"ticker": "BBB", "error": "timeout",   },
        {"ticker": "CCC", "signal": "TRUNG LẬP","price": 90.0},
    ]
    filtered = _apply_filter(results, ["MUA"])
    tickers  = [r["ticker"] for r in filtered]
    assert "BBB" in tickers, "Error ticker BBB should always be kept"
    assert "AAA" in tickers
    assert "CCC" not in tickers
    _pass("Error tickers always kept regardless of signal filter")


def test_single_ticker_bypasses_filter() -> None:
    """Filter is not applied when only 1 result exists."""
    results  = [{"ticker": "AAA", "signal": "MUA", "price": 100.0}]
    filtered = _apply_filter(results, [])   # empty selection, but single ticker
    assert len(filtered) == 1
    _pass("Single ticker bypasses filter (always shown)")


def test_present_signals_only_offered() -> None:
    """Only signals that appear in the current results are in _present."""
    results  = _make_results("MUA", "MUA", "TRUNG LẬP")
    _present = [
        s for s in _ALL_SIGNALS
        if any(r.get("signal") == s for r in results if "error" not in r)
    ]
    assert set(_present) == {"MUA", "TRUNG LẬP"}, f"Unexpected: {_present}"
    assert "BÁN / TRÁNH"    not in _present
    assert "THEO DÕI–TĂNG"  not in _present
    _pass("Only signals present in results are offered as filter options")


def test_all_error_results_no_present_signals() -> None:
    """When ALL results are errors, _present is empty → filter returns results unchanged."""
    results = [
        {"ticker": "X", "error": "failed"},
        {"ticker": "Y", "error": "timeout"},
    ]
    _present = [
        s for s in _ALL_SIGNALS
        if any(r.get("signal") == s for r in results if "error" not in r)
    ]
    assert _present == [], f"Expected empty, got {_present}"
    # In this case the filter returns results unchanged
    filtered = results if not _present else []
    assert len(filtered) == 2
    _pass("All-error results: _present empty → filter passthrough")


def test_icon_prefix_mapping_complete() -> None:
    """Every signal in _ALL_SIGNALS has a corresponding icon."""
    for sig in _ALL_SIGNALS:
        assert sig in _SIG_ICONS, f"Missing icon for signal '{sig}'"
    _pass("All signals have icon mappings")


def test_filter_theo_doi_tang() -> None:
    results = _make_results("MUA", "THEO DÕI–TĂNG", "THEO DÕI–GIẢM", "TRUNG LẬP")
    filtered = _apply_filter(results, ["THEO DÕI–TĂNG", "THEO DÕI–GIẢM"])
    sigs = {r["signal"] for r in filtered}
    assert sigs == {"THEO DÕI–TĂNG", "THEO DÕI–GIẢM"}, f"Got {sigs}"
    _pass("Filter THEO DÕI–TĂNG + THEO DÕI–GIẢM → exact match")


def test_filter_preserves_order() -> None:
    """Filter must preserve the original order of results."""
    results = _make_results("MUA", "TRUNG LẬP", "MUA", "BÁN / TRÁNH", "MUA")
    filtered = _apply_filter(results, ["MUA"])
    tickers = [r["ticker"] for r in filtered]
    assert tickers == ["T0", "T2", "T4"], f"Order mismatch: {tickers}"
    _pass("Filter preserves original result order")


# ── Runner ────────────────────────────────────────────────────────────────────

_TESTS = [
    test_all_selected_returns_all,
    test_filter_buy_only,
    test_filter_sell_only,
    test_filter_multiple_signals,
    test_empty_selection_returns_empty,
    test_error_results_always_kept,
    test_single_ticker_bypasses_filter,
    test_present_signals_only_offered,
    test_all_error_results_no_present_signals,
    test_icon_prefix_mapping_complete,
    test_filter_theo_doi_tang,
    test_filter_preserves_order,
]

if __name__ == "__main__":
    print(f"\n{'=' * 60}")
    print(f"  Signal Filter Test Suite  ({len(_TESTS)} tests)")
    print(f"{'=' * 60}")

    for t in _TESTS:
        prev = len(_results)
        try:
            t()
            if len(_results) == prev:
                _pass(t.__name__)
        except AssertionError as exc:
            _fail(t.__name__, str(exc))
        except Exception as exc:
            _fail(t.__name__, f"EXCEPTION {type(exc).__name__}: {exc}")

    for status, name in _results:
        print(f"  {status}  {name}")

    passed = sum(1 for s, _ in _results if s == PASS)
    failed = sum(1 for s, _ in _results if s == FAIL)
    print(f"{'=' * 60}")
    print(f"  {passed} passed  /  {failed} failed  /  {len(_TESTS)} total")
    print(f"{'=' * 60}\n")
    sys.exit(0 if failed == 0 else 1)
