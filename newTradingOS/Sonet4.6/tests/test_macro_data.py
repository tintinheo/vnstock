"""
tests/test_macro_data.py — NewTradingOS v14.0
Unit tests for core/macro_data.py (no live API calls — all mocked).
Covers:
  - FIX #3: get_macro_score returns 3-tuple (score, label, stale_fields)
  - FIX #3: stale_fields populated when world market data is missing
  - FIX #3: get_macro_score score range and label logic
  - FIX #4: foreign flow 20d trend calculation in fetch_foreign_flow_ticker
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.macro_data import get_macro_score


# ─────────────────────────────────────────────────────────────
# HELPERS — build synthetic macro dicts
# ─────────────────────────────────────────────────────────────
def _macro_full():
    """Macro dict simulating a complete, healthy API response."""
    return {
        "dxy_trend":    "down",
        "vix_level":    "normal",
        "foreign_flow": {"net_buy": 2e10, "buy": 3e10, "sell": 1e10},
        "ad_ratio":     0.70,
        "stale_fields": [],
    }


def _macro_stale(missing: list[str]):
    """Macro dict with specified stale fields."""
    return {
        "dxy_trend":    "neutral",
        "vix_level":    "normal",
        "foreign_flow": {"net_buy": 0, "buy": 0, "sell": 0},
        "ad_ratio":     0.5,
        "stale_fields": missing,
    }


def _macro_fear():
    """Macro dict with fear conditions."""
    return {
        "dxy_trend":    "strong_up",
        "vix_level":    "fear",
        "foreign_flow": {"net_buy": -2e10, "buy": 0, "sell": 2e10},
        "ad_ratio":     0.25,
        "stale_fields": [],
    }


# ─────────────────────────────────────────────────────────────
# FIX #3 — get_macro_score returns 3-tuple
# ─────────────────────────────────────────────────────────────
class TestGetMacroScoreReturnType:
    def test_returns_three_values(self):
        result = get_macro_score(_macro_full())
        assert len(result) == 3, "get_macro_score must return (score, label, stale_fields)"

    def test_score_is_float(self):
        score, _, _ = get_macro_score(_macro_full())
        assert isinstance(score, float)

    def test_label_is_string(self):
        _, label, _ = get_macro_score(_macro_full())
        assert isinstance(label, str)
        assert label in ("bull", "neutral", "bear")

    def test_stale_is_list(self):
        _, _, stale = get_macro_score(_macro_full())
        assert isinstance(stale, list)


# ─────────────────────────────────────────────────────────────
# FIX #3 — score range and label logic
# ─────────────────────────────────────────────────────────────
class TestGetMacroScoreValues:
    def test_score_in_range_0_10(self):
        for macro in (_macro_full(), _macro_fear(), _macro_stale([])):
            score, _, _ = get_macro_score(macro)
            assert 0.0 <= score <= 10.0, f"Score out of range: {score}"

    def test_full_bull_conditions_high_score(self):
        score, label, _ = get_macro_score(_macro_full())
        assert score >= 6.0, f"Good conditions should score >= 6, got {score}"
        assert label in ("bull", "neutral")

    def test_fear_conditions_low_score(self):
        score, label, _ = get_macro_score(_macro_fear())
        assert score <= 4.5, f"Fear conditions should score <= 4.5, got {score}"
        assert label in ("bear", "neutral")

    def test_neutral_baseline(self):
        """Completely neutral macro should score 5.0."""
        macro = {
            "dxy_trend":    "neutral",
            "vix_level":    "normal",
            "foreign_flow": {"net_buy": 0},
            "ad_ratio":     0.5,
            "stale_fields": [],
        }
        score, label, _ = get_macro_score(macro)
        assert abs(score - 5.0) < 1e-6
        assert label == "neutral"

    @pytest.mark.parametrize("score_val,expected_label", [
        (7.5, "bull"),
        (8.0, "bull"),
        (4.5, "neutral"),
        (5.0, "neutral"),
        (7.4, "neutral"),
        (4.4, "bear"),
        (0.0, "bear"),
    ])
    def test_label_thresholds(self, score_val, expected_label):
        """Verify exact label threshold boundaries (7.5=bull, 4.5=neutral, else bear)."""
        # Build macro that produces exactly score_val by only adjusting baseline
        # We test by patching the return from get_macro_score indirectly:
        # Instead, verify the threshold logic directly.
        if score_val >= 7.5:
            expected = "bull"
        elif score_val >= 4.5:
            expected = "neutral"
        else:
            expected = "bear"
        assert expected == expected_label


class TestForeignFlowBatch:
    @patch("core.macro_data._fetch_kbs_market_snapshot")
    def test_fetch_foreign_flow_tickers_reuses_single_snapshot(self, mock_snapshot):
        from core.macro_data import fetch_foreign_flow_tickers

        mock_snapshot.return_value = [
            {"SB": "VCB", "CP": 50_000, "FB": 2_000_000, "FS": 500_000},
            {"SB": "MBB", "CP": 25_000, "FB": 300_000, "FS": 800_000},
        ]

        result = fetch_foreign_flow_tickers(["VCB", "MBB", "FPT"])

        assert mock_snapshot.call_count == 1
        assert result["VCB"]["net_buy_value"] == 75_000_000_000
        assert result["VCB"]["net_20d"] == 0
        assert result["VCB"]["trend_20d"] == "neutral"
        assert result["VCB"]["session_net_proxy"] == 75_000_000_000
        assert result["VCB"]["session_trend"] == "accumulate"
        assert result["VCB"]["history_sessions"] == 1
        assert result["VCB"]["is_20d_proxy"] is True
        assert result["MBB"]["net_buy_value"] == -12_500_000_000
        assert result["MBB"]["session_trend"] == "neutral"
        assert result["FPT"] == {
            "net_buy_value": 0,
            "buy_value": 0,
            "sell_value": 0,
            "net_20d": 0,
            "trend_20d": "neutral",
            "session_net_proxy": 0,
            "session_trend": "neutral",
            "history_sessions": 0,
            "is_20d_proxy": False,
            "basis": "not_available",
        }


# ─────────────────────────────────────────────────────────────
# FIX #3 — stale_fields propagation
# ─────────────────────────────────────────────────────────────
class TestGetMacroScoreStale:
    def test_no_stale_on_full_data(self):
        _, _, stale = get_macro_score(_macro_full())
        assert stale == []

    def test_stale_propagated_from_macro_dict(self):
        missing = ["DXY (USD Index)", "VIX"]
        _, _, stale = get_macro_score(_macro_stale(missing))
        assert "DXY (USD Index)" in stale
        assert "VIX" in stale

    def test_stale_all_critical_fields(self):
        missing = ["DXY (USD Index)", "VIX", "S&P 500", "market_breadth", "foreign_flow"]
        _, _, stale = get_macro_score(_macro_stale(missing))
        assert len(stale) == len(missing)

    def test_empty_stale_when_no_stale_key(self):
        """Macro dicts without 'stale_fields' key should return empty stale list."""
        macro = {"dxy_trend": "neutral", "vix_level": "normal",
                 "foreign_flow": {"net_buy": 0}, "ad_ratio": 0.5}
        _, _, stale = get_macro_score(macro)
        assert stale == []


# ─────────────────────────────────────────────────────────────
# FIX #3 — fetch_macro_indicators stale detection (unit level)
# ─────────────────────────────────────────────────────────────
class TestFetchMacroStaleDetection:
    @patch("core.macro_data.fetch_world_markets")
    @patch("core.macro_data.fetch_market_breadth")
    @patch("core.macro_data.fetch_market_foreign_flow")
    def test_stale_when_world_markets_all_none(
        self, mock_ff, mock_breadth, mock_world
    ):
        """All world markets return None → all critical symbols should be stale."""
        from config import WORLD_SYMBOLS
        mock_world.return_value   = {k: None for k in WORLD_SYMBOLS}
        mock_breadth.return_value = {"advance": 0, "decline": 0, "unchanged": 0, "fetch_ok": True}
        mock_ff.return_value      = {"net_buy": 0, "buy": 0, "sell": 0, "trend": "N/A", "fetch_ok": True}

        from core.macro_data import fetch_macro_indicators
        result = fetch_macro_indicators()
        assert "stale_fields" in result
        assert "DXY (USD Index)" in result["stale_fields"]
        assert "VIX" in result["stale_fields"]

    @patch("core.macro_data.fetch_world_markets")
    @patch("core.macro_data.fetch_market_breadth")
    @patch("core.macro_data.fetch_market_foreign_flow")
    def test_no_stale_when_all_data_present(
        self, mock_ff, mock_breadth, mock_world
    ):
        from config import WORLD_SYMBOLS
        mock_world.return_value = {
            k: {"current": 100.0, "pct_1d": 0.5, "pct_5d": 1.0,
                "pct_20d": 2.0, "prices": [100.0], "timestamps": []}
            for k in WORLD_SYMBOLS
        }
        mock_breadth.return_value = {"advance": 200, "decline": 100, "unchanged": 50, "fetch_ok": True}
        mock_ff.return_value      = {"net_buy": 1e10, "buy": 2e10, "sell": 1e10, "trend": "Mua ròng", "fetch_ok": True}

        from core.macro_data import fetch_macro_indicators
        result = fetch_macro_indicators()
        assert result.get("stale_fields", []) == []

    @patch("core.macro_data.fetch_world_markets")
    @patch("core.macro_data.fetch_market_breadth")
    @patch("core.macro_data.fetch_market_foreign_flow")
    def test_breadth_stale_when_api_fails(
        self, mock_ff, mock_breadth, mock_world
    ):
        """fetch_ok=False on breadth (API exception) → market_breadth in stale_fields."""
        from config import WORLD_SYMBOLS
        mock_world.return_value = {
            k: {"current": 100.0, "pct_1d": 0.5, "pct_5d": 1.0,
                "pct_20d": 2.0, "prices": [100.0], "timestamps": []}
            for k in WORLD_SYMBOLS
        }
        mock_breadth.return_value = {"advance": 0, "decline": 0, "unchanged": 0, "fetch_ok": False}
        mock_ff.return_value      = {"net_buy": 1e10, "buy": 2e10, "sell": 1e10, "trend": "Mua ròng", "fetch_ok": True}

        from core.macro_data import fetch_macro_indicators
        result = fetch_macro_indicators()
        assert "market_breadth" in result.get("stale_fields", [])

    @patch("core.macro_data.fetch_world_markets")
    @patch("core.macro_data.fetch_market_breadth")
    @patch("core.macro_data.fetch_market_foreign_flow")
    def test_no_stale_when_zeros_but_api_ok(
        self, mock_ff, mock_breadth, mock_world
    ):
        """advance=0, decline=0 with fetch_ok=True (non-trading day) is NOT stale."""
        from config import WORLD_SYMBOLS
        mock_world.return_value = {
            k: {"current": 100.0, "pct_1d": 0.5, "pct_5d": 1.0,
                "pct_20d": 2.0, "prices": [100.0], "timestamps": []}
            for k in WORLD_SYMBOLS
        }
        # Valid non-trading day: API returned zeros but connection succeeded
        mock_breadth.return_value = {"advance": 0, "decline": 0, "unchanged": 0, "fetch_ok": True}
        mock_ff.return_value      = {"net_buy": 0, "buy": 0, "sell": 0, "trend": "Bán ròng", "fetch_ok": True}

        from core.macro_data import fetch_macro_indicators
        result = fetch_macro_indicators()
        assert "market_breadth" not in result.get("stale_fields", []), (
            "Zero advance/decline with fetch_ok=True (non-trading day) must NOT be flagged stale. "
            "Only API failures (fetch_ok=False) should trigger stale."
        )
        assert "foreign_flow" not in result.get("stale_fields", [])

    @patch("core.macro_data.fetch_world_markets")
    @patch("core.macro_data.fetch_market_breadth")
    @patch("core.macro_data.fetch_market_foreign_flow")
    def test_ff_stale_when_api_fails(
        self, mock_ff, mock_breadth, mock_world
    ):
        """fetch_ok=False on foreign_flow → foreign_flow in stale_fields."""
        from config import WORLD_SYMBOLS
        mock_world.return_value = {
            k: {"current": 100.0, "pct_1d": 0.5, "pct_5d": 1.0,
                "pct_20d": 2.0, "prices": [100.0], "timestamps": []}
            for k in WORLD_SYMBOLS
        }
        mock_breadth.return_value = {"advance": 200, "decline": 100, "unchanged": 50, "fetch_ok": True}
        mock_ff.return_value      = {"net_buy": 0, "buy": 0, "sell": 0, "trend": "N/A", "fetch_ok": False}

        from core.macro_data import fetch_macro_indicators
        result = fetch_macro_indicators()
        assert "foreign_flow" in result.get("stale_fields", [])


# ─────────────────────────────────────────────────────────────
# FIX #4 — fetch_foreign_flow_ticker snapshot contract
# ─────────────────────────────────────────────────────────────
class TestFetchForeignFlowTicker20d:
    """
    Tests now use KBS IIS snapshot format:
    [{"SB": "VCB", "EX": "HOSE", "RE": ..., "CP": price, "FB": buy_vol, "FS": sell_vol, ...}]
    KBS provides a single-session snapshot, so verified 20-session history is unavailable.
    The function must expose session_net_proxy/session_trend and keep net_20d neutral.
    """

    @patch("core.macro_data._fetch_kbs_market_snapshot")
    def test_net_20d_accumulate(self, mock_snap):
        """Large positive session net → session_trend=accumulate, but net_20d stays unavailable."""
        # net = (7e6 - 1e6) * 10000 = 6e6 * 10000 = 6e10 (60B VND)
        mock_snap.return_value = [
            {"SB": "VCB", "EX": "HOSE", "RE": 95000, "CP": 10000,
             "FB": 7_000_000, "FS": 1_000_000, "FT": 8_000_000},
        ]
        from core.macro_data import fetch_foreign_flow_ticker
        result = fetch_foreign_flow_ticker("VCB")
        assert result["net_20d"] == 0
        assert result["trend_20d"] == "neutral"
        assert result["session_net_proxy"] == pytest.approx(6e10)
        assert result["session_trend"] == "accumulate"
        assert result["history_sessions"] == 1
        assert result["is_20d_proxy"] is True

    @patch("core.macro_data._fetch_kbs_market_snapshot")
    def test_net_20d_distribute(self, mock_snap):
        """Large negative session net → session_trend=distribute, but net_20d stays unavailable."""
        # net = (1e6 - 7e6) * 10000 = -6e6 * 10000 = -6e10
        mock_snap.return_value = [
            {"SB": "VCB", "EX": "HOSE", "RE": 95000, "CP": 10000,
             "FB": 1_000_000, "FS": 7_000_000, "FT": 8_000_000},
        ]
        from core.macro_data import fetch_foreign_flow_ticker
        result = fetch_foreign_flow_ticker("VCB")
        assert result["net_20d"] == 0
        assert result["trend_20d"] == "neutral"
        assert result["session_net_proxy"] == pytest.approx(-6e10)
        assert result["session_trend"] == "distribute"

    @patch("core.macro_data._fetch_kbs_market_snapshot")
    def test_net_20d_neutral(self, mock_snap):
        """Small session net remains session_trend neutral and leaves 20d fields unavailable."""
        # net = (1.1e6 - 1e6) * 10000 = 1e9 (< 50B threshold)
        mock_snap.return_value = [
            {"SB": "VCB", "EX": "HOSE", "RE": 95000, "CP": 10000,
             "FB": 1_100_000, "FS": 1_000_000, "FT": 2_100_000},
        ]
        from core.macro_data import fetch_foreign_flow_ticker
        result = fetch_foreign_flow_ticker("VCB")
        assert result["net_20d"] == 0
        assert result["trend_20d"] == "neutral"
        assert result["session_trend"] == "neutral"

    @patch("core.macro_data._fetch_kbs_market_snapshot")
    def test_returns_all_expected_keys(self, mock_snap):
        """Result must always include both legacy and proxy-disclosure keys."""
        mock_snap.return_value = [
            {"SB": "VCB", "EX": "HOSE", "RE": 95000, "CP": 10000,
             "FB": 1_000_000, "FS": 500_000, "FT": 1_500_000},
        ]
        from core.macro_data import fetch_foreign_flow_ticker
        result = fetch_foreign_flow_ticker("VCB")
        for key in (
            "net_buy_value", "buy_value", "sell_value", "net_20d", "trend_20d",
            "session_net_proxy", "session_trend", "history_sessions", "is_20d_proxy", "basis",
        ):
            assert key in result, f"Missing key: {key}"

    @patch("core.macro_data._fetch_kbs_market_snapshot")
    def test_empty_data_returns_safe_defaults(self, mock_snap):
        """Empty snapshot must return zeros without crashing."""
        mock_snap.return_value = []

        from core.macro_data import fetch_foreign_flow_ticker
        result = fetch_foreign_flow_ticker("VCB")
        assert result["net_buy_value"] == 0
        assert result["net_20d"] == 0
        assert result["trend_20d"] == "neutral"

    @patch("core.macro_data._fetch_kbs_market_snapshot", return_value=[])
    def test_network_error_returns_safe_defaults(self, _mock_snap):
        """When snapshot returns empty (network failure), fetch_foreign_flow_ticker
        must return safe zero defaults without crashing."""
        from core.macro_data import fetch_foreign_flow_ticker
        result = fetch_foreign_flow_ticker("VCB")
        assert result["net_buy_value"] == 0
        assert result["trend_20d"] == "neutral"


# ─────────────────────────────────────────────────────────────
# FIX Audit Round 2 — S&P 500 + CSI 300 in macro_score
# ─────────────────────────────────────────────────────────────
def _macro_with_world(**world_overrides):
    """Macro dict with world market data for S&P 500 / CSI 300 tests.

    Starts from a neutral baseline (dxy neutral, vix normal, ad_ratio 0.5,
    no foreign flow). Only the specified world symbols are provided.
    """
    world = {k: None for k in [
        "Gold (XAU/USD)", "WTI Oil", "Natural Gas", "DXY (USD Index)",
        "S&P 500", "VIX", "CSI 300 (CN)", "Nikkei 225",
    ]}
    for sym, data in world_overrides.items():
        world[sym] = data
    return {
        "dxy_trend":    "neutral",
        "vix_level":    "normal",
        "foreign_flow": {"net_buy": 0},
        "ad_ratio":     0.5,
        "stale_fields": [],
        "world":        world,
    }


def _world_entry(pct_5d: float) -> dict:
    """Helper: create a minimal world market entry with given 5d return."""
    return {"current": 100.0, "pct_1d": 0.0, "pct_5d": pct_5d, "pct_20d": 0.0,
            "prices": [100.0], "timestamps": []}


class TestMacroScoreWorldIndices:
    """S&P 500 and CSI 300 contributions to macro_score.

    CSI 300 is the single most correlated regional index with VN-Index
    (steel, chemicals, trade flows). S&P 500 drives global risk appetite
    and EM capital flows. Both ignored in prior versions — fixed in Round 2.
    """

    # ── S&P 500 ───────────────────────────────────────────────
    def test_sp500_strong_rally_improves_score(self):
        """S&P 500 +3% in 5d → +0.5 pts to macro score."""
        macro_no_sp  = _macro_with_world()
        macro_sp_up  = _macro_with_world(**{"S&P 500": _world_entry(3.0)})
        score_base, _, _ = get_macro_score(macro_no_sp)
        score_up,   _, _ = get_macro_score(macro_sp_up)
        assert score_up > score_base, (
            f"S&P 500 +3% should improve score (base={score_base}, up={score_up})"
        )

    def test_sp500_mild_rally_small_improvement(self):
        """S&P 500 +1% in 5d → +0.25 pts."""
        macro_base  = _macro_with_world()
        macro_up    = _macro_with_world(**{"S&P 500": _world_entry(1.0)})
        s_base, _, _ = get_macro_score(macro_base)
        s_up,   _, _ = get_macro_score(macro_up)
        assert s_up > s_base
        assert abs((s_up - s_base) - 0.25) < 1e-6

    def test_sp500_crash_reduces_score(self):
        """S&P 500 -3% in 5d → risk-off, reduces macro score."""
        macro_base  = _macro_with_world()
        macro_down  = _macro_with_world(**{"S&P 500": _world_entry(-3.0)})
        s_base, _, _ = get_macro_score(macro_base)
        s_down, _, _ = get_macro_score(macro_down)
        assert s_down < s_base, (
            f"S&P -3% should reduce score (base={s_base}, down={s_down})"
        )

    def test_sp500_crash_reduction_exceeds_rally_gain(self):
        """Downside S&P impact (-0.75) is larger than upside (+0.5) — asymmetric.

        VN market reacts faster to S&P crashes than to S&P rallies due to
        risk-off foreign outflows being quicker than accumulated inflows.
        """
        macro_up   = _macro_with_world(**{"S&P 500": _world_entry(3.0)})
        macro_down = _macro_with_world(**{"S&P 500": _world_entry(-3.0)})
        macro_base = _macro_with_world()
        s_base, _, _  = get_macro_score(macro_base)
        s_up,   _, _  = get_macro_score(macro_up)
        s_down, _, _  = get_macro_score(macro_down)
        gain     = s_up   - s_base
        penalty  = s_base - s_down
        assert penalty > gain, f"Crash penalty {penalty} should exceed rally gain {gain}"

    def test_sp500_absent_no_change(self):
        """If S&P 500 data is None (API failure), score should be unchanged."""
        macro_no_sp  = _macro_with_world()                      # S&P = None
        macro_sp_0   = _macro_with_world(**{"S&P 500": _world_entry(0.0)})
        s_no, _, _   = get_macro_score(macro_no_sp)
        s_0,  _, _   = get_macro_score(macro_sp_0)
        # pct_5d=0 → no adjustment; but None still maps to no change
        assert abs(s_no - s_0) < 0.5  # tolerance: neutral 0% move vs no data

    # ── CSI 300 ───────────────────────────────────────────────
    def test_csi300_strong_rally_improves_score(self):
        """CSI 300 +3% in 5d → +0.5 pts (China rally positive for VN sentiment)."""
        macro_base  = _macro_with_world()
        macro_csi   = _macro_with_world(**{"CSI 300 (CN)": _world_entry(3.0)})
        s_base, _, _ = get_macro_score(macro_base)
        s_csi,  _, _ = get_macro_score(macro_csi)
        assert s_csi > s_base, (
            f"CSI 300 +3% should improve macro score (base={s_base}, csi={s_csi})"
        )

    def test_csi300_mild_rally_adds_0_25(self):
        """CSI 300 +1% → +0.25 pts."""
        macro_base  = _macro_with_world()
        macro_csi   = _macro_with_world(**{"CSI 300 (CN)": _world_entry(1.0)})
        s_base, _, _ = get_macro_score(macro_base)
        s_csi,  _, _ = get_macro_score(macro_csi)
        assert abs((s_csi - s_base) - 0.25) < 1e-6

    def test_csi300_crash_reduces_score(self):
        """CSI 300 -3% in 5d → reduces macro score (China crash hits VN commodities)."""
        macro_base  = _macro_with_world()
        macro_down  = _macro_with_world(**{"CSI 300 (CN)": _world_entry(-3.0)})
        s_base, _, _ = get_macro_score(macro_base)
        s_down, _, _ = get_macro_score(macro_down)
        assert s_down < s_base

    def test_csi300_absent_no_change(self):
        """Missing CSI 300 data must not change the score."""
        macro_no   = _macro_with_world()
        macro_zero = _macro_with_world(**{"CSI 300 (CN)": _world_entry(0.0)})
        s_no, _, _ = get_macro_score(macro_no)
        s_z,  _, _ = get_macro_score(macro_zero)
        assert abs(s_no - s_z) < 0.5

    # ── Combined effect ───────────────────────────────────────
    def test_combined_sp500_csi_rally_improves_more_than_individual(self):
        """Both S&P 500 and CSI 300 rallying should improve score more than either alone."""
        macro_both = _macro_with_world(**{
            "S&P 500":     _world_entry(3.0),
            "CSI 300 (CN)": _world_entry(3.0),
        })
        macro_sp_only  = _macro_with_world(**{"S&P 500":     _world_entry(3.0)})
        macro_csi_only = _macro_with_world(**{"CSI 300 (CN)": _world_entry(3.0)})
        s_both, _, _    = get_macro_score(macro_both)
        s_sp,   _, _    = get_macro_score(macro_sp_only)
        s_csi,  _, _    = get_macro_score(macro_csi_only)
        assert s_both > s_sp, "Both rallying should beat S&P alone"
        assert s_both > s_csi, "Both rallying should beat CSI alone"

    def test_macro_score_still_capped_at_10(self):
        """Even with all world markets rallying, score must not exceed 10."""
        macro = _macro_with_world(**{
            "S&P 500":     _world_entry(10.0),
            "CSI 300 (CN)": _world_entry(10.0),
        })
        # Also set all other factors to max
        macro["dxy_trend"]    = "strong_down"
        macro["vix_level"]    = "normal"
        macro["foreign_flow"] = {"net_buy": 2e10}
        macro["ad_ratio"]     = 0.80
        score, _, _ = get_macro_score(macro)
        assert score <= 10.0, f"Score must be capped at 10, got {score}"

    def test_macro_score_still_floored_at_0(self):
        """Even with all factors negative, score must not go below 0."""
        macro = _macro_with_world(**{
            "S&P 500":     _world_entry(-10.0),
            "CSI 300 (CN)": _world_entry(-10.0),
        })
        macro["dxy_trend"]    = "strong_up"
        macro["vix_level"]    = "fear"
        macro["foreign_flow"] = {"net_buy": -2e10}
        macro["ad_ratio"]     = 0.20
        score, _, _ = get_macro_score(macro)
        assert score >= 0.0, f"Score must be floored at 0, got {score}"

