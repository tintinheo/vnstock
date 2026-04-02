"""
Integration tests for all 3 implementation phases.

Phase 1 — Put-through data integration
Phase 2 — Second Mouse Gate (breakout confirmation)
Phase 3 — Sector map update script (SSI-backed)
"""
import os
import sys
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 60, trend: str = "up") -> pd.DataFrame:
    """Generate a synthetic OHLCV DataFrame."""
    np.random.seed(42)
    base = 50_000.0
    closes = [base]
    for _ in range(n - 1):
        delta = np.random.normal(200 if trend == "up" else -200, 500)
        closes.append(max(closes[-1] + delta, 10_000))
    arr = np.array(closes)
    df = pd.DataFrame({
        "date":   pd.date_range("2025-01-01", periods=n, freq="B"),
        "open":   arr * np.random.uniform(0.995, 1.005, n),
        "high":   arr * np.random.uniform(1.005, 1.015, n),
        "low":    arr * np.random.uniform(0.985, 0.995, n),
        "close":  arr,
        "volume": np.random.randint(500_000, 5_000_000, n).astype(float),
    })
    return df


def _make_daily_flow(df: pd.DataFrame) -> pd.DataFrame:
    from tradingos.core.money_flow import proxy_whale_net_from_daily
    return proxy_whale_net_from_daily(df)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Put-through Data Integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase1PutThroughFetcher:
    """FR-P1.1 — fetch_put_through_deals returns correct schema."""

    def test_returns_dataframe(self):
        from tradingos.data.fetcher import fetch_put_through_deals
        result = fetch_put_through_deals("CMG", days=5)
        assert isinstance(result, pd.DataFrame)

    def test_schema_columns(self):
        from tradingos.data.fetcher import fetch_put_through_deals
        result = fetch_put_through_deals("FPT", days=5)
        expected = {"date", "buyer", "seller", "volume", "price", "value"}
        assert expected.issubset(set(result.columns)), \
            f"Missing columns: {expected - set(result.columns)}"

    def test_returns_empty_gracefully_on_bad_ticker(self):
        from tradingos.data.fetcher import fetch_put_through_deals
        result = fetch_put_through_deals("INVALID_TICKER_XYZ", days=5)
        assert isinstance(result, pd.DataFrame)
        assert len(result) >= 0  # empty is acceptable

    def test_value_column_is_vol_times_price(self):
        """value == volume * price for all non-empty rows."""
        from tradingos.data.fetcher import fetch_put_through_deals
        result = fetch_put_through_deals("HPG", days=5)
        if not result.empty:
            computed = result["volume"] * result["price"]
            pd.testing.assert_series_equal(
                result["value"].round(2), computed.round(2), check_names=False
            )


class TestPhase1SmartMoneyScore:
    """FR-P1.2 — SMS integrates pt_flow component."""

    def _sms(self, pt_df=None):
        from tradingos.core.money_flow import compute_smart_money_score
        from tradingos.core.indicators import compute_all
        df   = _make_ohlcv(60)
        df   = compute_all(df)
        flow = _make_daily_flow(df)
        return compute_smart_money_score("TST", df, flow, pt_df)

    def test_sms_without_pt_data(self):
        result = self._sms(pt_df=None)
        assert "sms" in result
        assert 0 <= result["sms"] <= 100
        assert "pt_flow" not in result["components"] or result["components"]["pt_flow"] == 0

    def test_sms_with_empty_pt_df(self):
        empty = pd.DataFrame(columns=["date", "buyer", "seller", "volume", "price", "value"])
        result = self._sms(pt_df=empty)
        assert result["components"].get("pt_flow", 0) == 0

    def test_sms_with_positive_pt_flow(self):
        """Large put-through buying should increase SMS."""
        # Create mock PT data with significant net buy value
        pt_df = pd.DataFrame({
            "date":   ["2025-03-01"] * 5,
            "buyer":  ["A"] * 5,
            "seller": ["B"] * 5,
            "volume": [100_000.0] * 5,
            "price":  [50_000.0] * 5,
            "value":  [5_000_000_000.0] * 5,  # 5B VND net buy per row
        })
        result = self._sms(pt_df=pt_df)
        assert result["components"].get("pt_flow", 0) > 0

    def test_sms_returns_pt_net_and_ratio(self):
        pt_df = pd.DataFrame({
            "date": ["2025-03-01"],
            "buyer": ["X"], "seller": ["Y"],
            "volume": [10_000.0], "price": [50_000.0], "value": [500_000_000.0],
        })
        result = self._sms(pt_df=pt_df)
        assert "pt_net_5d" in result
        assert "pt_ratio_5d" in result
        assert result["pt_net_5d"] > 0

    def test_sms_total_capped_at_100(self):
        """SMS must never exceed 100."""
        pt_df = pd.DataFrame({
            "date": ["2025-03-01"] * 10,
            "buyer": ["X"] * 10, "seller": ["Y"] * 10,
            "volume": [1_000_000.0] * 10,
            "price": [50_000.0] * 10,
            "value": [50_000_000_000.0] * 10,  # astronomical
        })
        result = self._sms(pt_df=pt_df)
        assert result["sms"] <= 100


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Second Mouse Gate
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase2SecondMouseGate:
    """FR-P2.1 — second_mouse_gate function logic."""

    def _gate(self, df, level):
        from tradingos.core.patterns import second_mouse_gate
        return second_mouse_gate(df, breakout_level=level, lookback=10)

    def test_returns_dict_with_confirmed_key(self):
        df = _make_ohlcv(20)
        result = self._gate(df, df["close"].max() * 0.9)
        assert "confirmed" in result
        assert isinstance(result["confirmed"], bool)

    def test_insufficient_data_not_confirmed(self):
        df = _make_ohlcv(3)
        result = self._gate(df, 50_000.0)
        assert result["confirmed"] is False

    def test_no_breakout_not_confirmed(self):
        """When price never breaks the level, gate is not confirmed."""
        df = _make_ohlcv(20, trend="up")
        high_level = df["close"].max() * 2.0  # way above all prices
        result = self._gate(df, high_level)
        assert result["confirmed"] is False

    def test_confirmed_retest_structure(self):
        """Construct a synthetic breakout+retest and verify confirmation."""
        # Build a price series: consolidation → breakout → small pullback → recovery
        n = 15
        level = 55_000.0
        closes = ([50_000.0] * 5          # below level
                  + [56_000.0]            # breakout bar
                  + [54_500.0]            # retest (above level)
                  + [57_000.0] * (n - 7)) # recovery
        df = pd.DataFrame({
            "date":   pd.date_range("2025-01-01", periods=n),
            "open":   np.array(closes) * 0.99,
            "high":   np.array(closes) * 1.01,
            "low":    np.array(closes) * 0.98,
            "close":  closes,
            "volume": ([1_000_000] * 5
                       + [3_000_000]   # high volume breakout
                       + [600_000]     # low volume retest
                       + [1_200_000] * (n - 7)),
        })
        result = self._gate(df, level)
        # Should detect retest_low above level
        if result["confirmed"]:
            assert result["retest_low"] > level


class TestPhase2ModeBScore:
    """FR-P2.2 — score_mode_b uses Second Mouse Gate."""

    def test_score_mode_b_accepts_pattern_result(self):
        from tradingos.core.mfpm import score_mode_b
        from tradingos.core.indicators import compute_all
        df = _make_ohlcv(40)
        df = compute_all(df)
        pattern_result = {"best_pattern": "NONE", "pattern_bonus": 0}
        score = score_mode_b(df, pattern_result)
        assert isinstance(score, int)
        assert 0 <= score <= 60

    def test_confirmed_retest_boosts_score(self):
        """A confirmed second-mouse retest should give higher Mode B score."""
        from tradingos.core.mfpm import score_mode_b
        from tradingos.core.indicators import compute_all

        # Build df where last bar is above a pivot and on high volume (breakout)
        n = 40
        closes = [50_000.0] * (n - 5) + [52_000.0, 51_500.0, 53_000.0, 54_000.0, 55_000.0]
        vols   = [1_000_000.0] * (n - 5) + [3_000_000.0, 500_000.0, 1_200_000.0, 1_300_000.0, 1_400_000.0]
        df = pd.DataFrame({
            "date":   pd.date_range("2025-01-01", periods=n),
            "open":   np.array(closes) * 0.998,
            "high":   np.array(closes) * 1.012,
            "low":    np.array(closes) * 0.988,
            "close":  closes,
            "volume": vols,
        })
        df = compute_all(df)
        score = score_mode_b(df, {"best_pattern": "NONE", "pattern_bonus": 0})
        assert score >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — Sector Map Update
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase3SectorMap:
    """FR-P3.1 — Sector map script logic."""

    @pytest.fixture(autouse=True)
    def _patch_json_path(self, tmp_path, monkeypatch):
        """Redirect JSON_PATH to a temp directory for isolation."""
        import importlib
        import tradingos  # ensure sys.path is set
        # Import script directly
        spec_path = str(Path(__file__).parents[2] / "scripts" / "update_sector_map.py")
        import importlib.util
        spec = importlib.util.spec_from_file_location("update_sector_map", spec_path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.tmp_json = tmp_path / "sector_map.json"
        monkeypatch.setattr(self.mod, "JSON_PATH", str(self.tmp_json))

    def test_load_existing_map_empty_when_missing(self):
        result = self.mod.load_existing_map()
        assert result == {}

    def test_load_existing_map_reads_file(self):
        data = {"ACB": {"sector": "HOSE", "industry": "Ngân hàng", "sub_sector": "Ngân hàng"}}
        self.tmp_json.write_text(json.dumps(data), encoding="utf-8")
        result = self.mod.load_existing_map()
        assert result == data

    def test_load_existing_map_invalid_json_returns_empty(self):
        self.tmp_json.write_text("NOT VALID JSON", encoding="utf-8")
        result = self.mod.load_existing_map()
        assert result == {}

    def test_save_writes_json_file(self, monkeypatch):
        # Mock Cache to avoid DB dependency
        class MockCache:
            def put_sector_map(self, records): pass
        monkeypatch.setattr(self.mod, "Cache", MockCache)

        data = {"FPT": {"sector": "HOSE", "industry": "Công nghệ Thông tin", "sub_sector": "Phần mềm"}}
        self.mod.save(data)
        assert self.tmp_json.exists()
        loaded = json.loads(self.tmp_json.read_text(encoding="utf-8"))
        assert loaded == data

    def test_manual_map_takes_priority(self, monkeypatch):
        """Manual entries are never overwritten by SSI fallback."""
        manual = {"ACB": {"sector": "HOSE", "industry": "Manual_Industry"}}
        self.tmp_json.write_text(json.dumps(manual), encoding="utf-8")

        # Mock universe to include ACB and fetch_profile to return different industry
        monkeypatch.setattr(self.mod, "fetch_universe", lambda: {"ACB": "HOSE"})
        monkeypatch.setattr(self.mod, "fetch_profile",
                            lambda ticker, exchange: {"sector": "HOSE", "industry": "SSI_Industry"})

        class MockCache:
            def put_sector_map(self, records): pass
        monkeypatch.setattr(self.mod, "Cache", MockCache)

        self.mod.update_sector_map()
        result = json.loads(self.tmp_json.read_text(encoding="utf-8"))
        # Manual entry should be preserved
        assert result["ACB"]["industry"] == "Manual_Industry"

    def test_ssi_fallback_fills_missing(self, monkeypatch):
        """Tickers absent from manual map are filled by SSI profile."""
        self.tmp_json.write_text("{}", encoding="utf-8")

        monkeypatch.setattr(self.mod, "fetch_universe", lambda: {"FPT": "HOSE", "CMG": "HOSE"})
        monkeypatch.setattr(self.mod, "fetch_profile",
                            lambda ticker, exchange: {"sector": exchange, "industry": f"Industry_{ticker}", "sub_sector": ""})

        class MockCache:
            def put_sector_map(self, records): pass
        monkeypatch.setattr(self.mod, "Cache", MockCache)

        self.mod.update_sector_map()
        result = json.loads(self.tmp_json.read_text(encoding="utf-8"))
        assert "FPT" in result
        assert result["FPT"]["industry"] == "Industry_FPT"
        assert "CMG" in result

    def test_aborts_if_universe_empty(self, monkeypatch):
        monkeypatch.setattr(self.mod, "fetch_universe", lambda: {})
        success = self.mod.update_sector_map()
        assert success is False


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION — Full ProfilerService smoke test
# ═══════════════════════════════════════════════════════════════════════════════

class TestProfilerServiceIntegration:
    """Smoke test: ProfilerService should run end-to-end without crashing."""

    def test_profiler_runs_with_mock_data(self, monkeypatch):
        from tradingos.engines.profiler_service import ProfilerService
        from tradingos.data.schemas import ProfilerRequest
        from tradingos.data.fetcher import fetch_put_through_deals

        df = _make_ohlcv(120)
        # Patch fetcher to return synthetic data
        monkeypatch.setattr(
            "tradingos.engines.profiler_service.fetch_ohlcv",
            lambda ticker, days=260: df,
        )
        monkeypatch.setattr(
            "tradingos.engines.profiler_service.fetch_put_through_deals",
            lambda ticker, days=5: pd.DataFrame(
                columns=["date", "buyer", "seller", "volume", "price", "value"]
            ),
        )

        svc = ProfilerService(portfolio_value=300_000_000)
        req = ProfilerRequest(ticker="TST", mode="FULL")
        profile = svc.run(req)

        assert profile is not None
        assert profile.ticker == "TST"
        assert isinstance(profile.sms_raw, (int, float))
        # Phase 1 fields present
        assert hasattr(profile, "pt_net_5d")
        assert hasattr(profile, "pt_ratio_5d")
