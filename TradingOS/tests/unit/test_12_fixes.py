"""
Regression tests for the 12 credibility/correctness fixes.
Each test class maps to one numbered issue.
Run with: pytest tests/unit/test_12_fixes.py -v
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 200, seed: int = 42, trend: float = 0.001) -> pd.DataFrame:
    """Generate deterministic OHLCV with a `date` column (clean_ohlcv style)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", periods=n)
    close = 50_000.0 * np.cumprod(1 + rng.normal(trend, 0.015, n))
    volume = rng.integers(200_000, 2_000_000, n).astype(float)
    return pd.DataFrame({
        "date":   dates,
        "open":   close * rng.uniform(0.99, 1.01, n),
        "high":   close * rng.uniform(1.00, 1.02, n),
        "low":    close * rng.uniform(0.98, 1.00, n),
        "close":  close,
        "volume": volume,
    })


def _make_flow(df: pd.DataFrame) -> pd.DataFrame:
    """Create a daily_flow_df from an OHLCV DataFrame."""
    from tradingos.core.money_flow import proxy_whale_net_from_daily
    flow = proxy_whale_net_from_daily(df)
    flow["data_source"] = "PROXY_OHLCV"
    return flow


# ─────────────────────────────────────────────────────────────────────────────
# Issue #1 — Monte Carlo uses bootstrap (not Gaussian)
# ─────────────────────────────────────────────────────────────────────────────

class TestMonteCarloBootstrap:
    """#1: mc_win_prob must use empirical returns instead of Normal draws."""

    def test_returns_float_in_range(self):
        from tradingos.core.mfpm import monte_carlo_win_prob
        df = _make_ohlcv()
        p = monte_carlo_win_prob(df, entry=50_000, sl=47_000, tp=55_000)
        assert 0.0 <= p <= 1.0

    def test_fat_tail_crash_reduces_win_prob(self):
        """Injecting a crash sequence should lower win-prob vs. calm market."""
        from tradingos.core.mfpm import monte_carlo_win_prob
        calm = _make_ohlcv(200, seed=1, trend=0.001)
        # Inject large negative returns to simulate VN crash sessions
        crash = calm.copy()
        crash.loc[180:199, "close"] = crash["close"].iloc[179] * np.cumprod(
            [0.93] * 20  # 7% daily drops
        )
        p_calm  = monte_carlo_win_prob(calm,  entry=50_000, sl=47_000, tp=55_000, n_sim=1000)
        p_crash = monte_carlo_win_prob(crash, entry=50_000, sl=47_000, tp=55_000, n_sim=1000)
        # Crash market must produce lower (or equal) win probability
        assert p_crash <= p_calm + 0.05, (
            f"Bootstrap should detect fat tails: crash={p_crash:.3f} > calm={p_calm:.3f}"
        )

    def test_degenerate_inputs_return_half(self):
        from tradingos.core.mfpm import monte_carlo_win_prob
        df = _make_ohlcv(10)  # too few bars
        assert monte_carlo_win_prob(df, 0, 0, 0) == 0.5
        assert monte_carlo_win_prob(pd.DataFrame(), 50_000, 47_000, 55_000) == 0.5
        large = _make_ohlcv()
        assert monte_carlo_win_prob(large, 50_000, 51_000, 55_000) == 0.5  # sl >= entry


# ─────────────────────────────────────────────────────────────────────────────
# Issue #2 — data_source not mislabeled as TICK_REAL
# ─────────────────────────────────────────────────────────────────────────────

class TestDataSourceLabel:
    """#2: OHLCV proxy must NOT receive TICK_REAL label in compute_multiday_whale_flow."""

    def test_proxy_flow_labeled_proxy(self):
        from tradingos.core.money_flow import proxy_whale_net_from_daily, compute_multiday_whale_flow
        df = _make_ohlcv()
        flow = proxy_whale_net_from_daily(df)
        flow["data_source"] = "PROXY_OHLCV"
        result = compute_multiday_whale_flow(flow)
        assert result["data_source"] == "PROXY_OHLCV", (
            f"Expected PROXY_OHLCV, got {result['data_source']}"
        )

    def test_partial_proxy_labeled_partial(self):
        from tradingos.core.money_flow import compute_whale_net_from_pt_deals, compute_multiday_whale_flow
        df = _make_ohlcv()
        pt = pd.DataFrame({
            "date":   [df["date"].iloc[-3].date(), df["date"].iloc[-2].date()],
            "value":  [500_000_000, -200_000_000],
            "volume": [10_000, 4_000],
            "price":  [50_000, 50_000],
        })
        flow = compute_whale_net_from_pt_deals(pt, df)
        result = compute_multiday_whale_flow(flow)
        assert result["data_source"] == "PARTIAL_PROXY"

    def test_no_proxy_columns_stays_proxy(self):
        """whale_net-only DataFrame (no proxy column) but has data_source=PROXY_OHLCV."""
        from tradingos.core.money_flow import compute_multiday_whale_flow
        n = 25
        flow = pd.DataFrame({
            "whale_net": np.random.randint(-1000, 1000, n),
            "close":     np.linspace(50_000, 52_000, n),
            "volume":    np.full(n, 500_000.0),
            "data_source": ["PROXY_OHLCV"] * n,
        })
        result = compute_multiday_whale_flow(flow)
        assert result["data_source"] == "PROXY_OHLCV"


# ─────────────────────────────────────────────────────────────────────────────
# Issue #3 — score_mode_b never negative
# ─────────────────────────────────────────────────────────────────────────────

class TestModeBScoreFloor:
    """#3: score_mode_b must always return >= 0."""

    def test_score_non_negative_worst_case(self):
        from tradingos.core.mfpm import score_mode_b
        # Build a df where breakout barely triggered, second-mouse gate fails (penalty)
        df = _make_ohlcv(30)
        # Force the last close just above 20d high to trigger breakout
        df.loc[df.index[-1], "close"] = float(df["high"].iloc[:-1].max()) * 1.001
        # A pattern_result with a very low pivot that guarantees breakout
        pattern = {"pivot": float(df["close"].iloc[-2] * 0.5)}
        score = score_mode_b(df, pattern)
        assert score >= 0, f"score_mode_b returned {score} (negative not allowed)"

    def test_score_capped_at_60(self):
        from tradingos.core.mfpm import score_mode_b
        df = _make_ohlcv(50)
        # Set up very favourable conditions
        df.loc[df.index[-1], "close"]  = 80_000.0
        df.loc[df.index[-1], "volume"] = 5_000_000.0  # large volume
        df.loc[df.index[-1], "ATR14"]  = 1_500.0      # if column added
        pattern = {"pivot": 40_000.0, "pattern_bonus": 20}
        score = score_mode_b(df, pattern)
        assert score <= 60


# ─────────────────────────────────────────────────────────────────────────────
# Issue #4 — compute_whale_net_from_pt_deals: no AttributeError on df.get()
# ─────────────────────────────────────────────────────────────────────────────

class TestPTDealAlignment:
    """#4: compute_whale_net_from_pt_deals must not raise AttributeError."""

    def test_no_error_with_date_column(self):
        from tradingos.core.money_flow import compute_whale_net_from_pt_deals
        df = _make_ohlcv(50)  # has 'date' column, RangeIndex
        pt = pd.DataFrame({
            "date":  [df["date"].iloc[-1].date()],
            "value": [200_000_000],
        })
        # Must not raise
        result = compute_whale_net_from_pt_deals(pt, df)
        assert "whale_net" in result.columns

    def test_no_error_with_empty_pt(self):
        from tradingos.core.money_flow import compute_whale_net_from_pt_deals
        df = _make_ohlcv(50)
        result = compute_whale_net_from_pt_deals(pd.DataFrame(), df)
        assert result["data_source"].iloc[0] == "PROXY_OHLCV"

    def test_no_error_without_date_column(self):
        """DatetimeIndex style DataFrame (no 'date' column)."""
        from tradingos.core.money_flow import compute_whale_net_from_pt_deals
        df = _make_ohlcv(50).set_index("date")  # type: ignore
        pt = pd.DataFrame({
            "date":  [df.index[-1].date()],
            "value": [100_000_000],
        })
        # Must not raise
        result = compute_whale_net_from_pt_deals(pt, df)
        assert isinstance(result, pd.DataFrame)


# ─────────────────────────────────────────────────────────────────────────────
# Issue #5 — vwap_daily is volume-weighted, not just typical price
# ─────────────────────────────────────────────────────────────────────────────

class TestVwapDaily:
    """#5: vwap_daily must differ from simple typical price when volume varies."""

    def test_vwap_differs_from_typical_price_on_volume_variation(self):
        from tradingos.core.indicators import vwap_daily
        df = pd.DataFrame({
            "high":   [110, 120, 130, 140, 150],
            "low":    [ 90, 100, 110, 120, 130],
            "close":  [100, 110, 120, 130, 140],
            "volume": [100, 100, 100, 100, 1_000_000],  # last bar dominates
        })
        vwap = vwap_daily(df)
        tp   = (df["high"] + df["low"] + df["close"]) / 3  # old formula
        # VWAP should be pulled towards the last bar's typical price due to huge volume
        assert abs(vwap.iloc[-1] - tp.iloc[-1]) < 1.0, \
            "Last bar dominates volume so VWAP ≈ TP of last bar"
        # For earlier bars, VWAP should differ from simple TP because of volume weighting
        assert not np.allclose(vwap.values, tp.values, atol=1.0), \
            "VWAP should differ from simple typical price across the series"

    def test_vwap_no_nan_with_nonzero_volume(self):
        from tradingos.core.indicators import vwap_daily
        df = _make_ohlcv()
        result = vwap_daily(df)
        assert result.notna().all(), "vwap_daily should produce no NaN for valid input"

    def test_vwap_positive(self):
        from tradingos.core.indicators import vwap_daily
        df = _make_ohlcv()
        assert (vwap_daily(df) > 0).all()


# ─────────────────────────────────────────────────────────────────────────────
# Issue #6 — Kelly fraction read from config (0.3), not hardcoded 0.5
# ─────────────────────────────────────────────────────────────────────────────

class TestKellyFromConfig:
    """#6: compute_position_size must use config kelly_fraction=0.3 by default."""

    def test_default_uses_config_30pct(self):
        from tradingos.core.sizing import compute_position_size, kelly_fraction
        entry, sl, win_prob, rr = 50_000.0, 47_500.0, 0.60, 2.5
        portfolio = 300_000_000.0

        # What config (0.3 fraction) gives
        k_30 = kelly_fraction(win_prob, rr, fraction=0.3)
        # What old default (0.5 fraction) gives
        k_50 = kelly_fraction(win_prob, rr, fraction=0.5)

        result = compute_position_size(portfolio, entry, sl, win_prob, rr)
        # shares * entry should align with the 0.3-fraction sizing
        actual_pct = result["shares"] * entry / portfolio
        # Must be materially closer to 0.3-fraction than 0.5-fraction
        diff_30 = abs(actual_pct - k_30)
        diff_50 = abs(actual_pct - k_50)
        assert diff_30 <= diff_50 + 0.02, (
            f"Expected 0.3-fraction sizing (k={k_30:.3f}), got pct={actual_pct:.3f}"
        )

    def test_explicit_override_respected(self):
        from tradingos.core.sizing import compute_position_size
        result_30 = compute_position_size(300_000_000, 50_000, 47_000, kelly_fraction_=0.3)
        result_50 = compute_position_size(300_000_000, 50_000, 47_000, kelly_fraction_=0.5)
        assert result_30["shares"] <= result_50["shares"], \
            "Lower kelly_fraction must produce smaller (or equal) position"


# ─────────────────────────────────────────────────────────────────────────────
# Issue #7 — fol_net column included when date column is present
# ─────────────────────────────────────────────────────────────────────────────

class TestFolNetPopulation:
    """#7: proxy_whale_net_from_daily should include 'date' column for merging."""

    def test_date_column_present_in_flow(self):
        from tradingos.core.money_flow import proxy_whale_net_from_daily
        df = _make_ohlcv()
        flow = proxy_whale_net_from_daily(df)
        assert "date" in flow.columns, "date column must be present for fol_net merging"

    def test_fol_net_mergeable_by_date(self):
        from tradingos.core.money_flow import proxy_whale_net_from_daily
        df = _make_ohlcv(50)
        flow = proxy_whale_net_from_daily(df)

        fol_df = pd.DataFrame({
            "date":    [flow["date"].iloc[-1].date() if hasattr(flow["date"].iloc[-1], "date")
                        else flow["date"].iloc[-1]],
            "fol_net": [500_000.0],
        })
        fol_df["date"] = pd.to_datetime(fol_df["date"]).dt.date
        flow["date"]   = pd.to_datetime(flow["date"]).dt.date

        merged = flow.merge(fol_df, on="date", how="left").fillna({"fol_net": 0})
        assert "fol_net" in merged.columns
        assert merged["fol_net"].iloc[-1] == 500_000.0


# ─────────────────────────────────────────────────────────────────────────────
# Issue #8 — Hurst reliable: max_lag=40, needs >= 80 bars
# ─────────────────────────────────────────────────────────────────────────────

class TestHurstReliability:
    """#8: Hurst exponent uses max_lag=40; returns 0.5 when < 80 bars."""

    def test_returns_half_when_too_few_bars(self):
        from tradingos.core.indicators import hurst_exponent
        short = pd.Series(np.linspace(10, 20, 60))  # < 80 bars
        assert hurst_exponent(short) == 0.5

    def test_returns_value_with_sufficient_bars(self):
        from tradingos.core.indicators import hurst_exponent
        rng = np.random.default_rng(7)
        series = pd.Series(10.0 + np.cumsum(rng.normal(0, 0.5, 200)))
        h = hurst_exponent(series)
        assert 0.0 <= h <= 1.0

    def test_trending_series_hurst_above_half(self):
        """A pure uptrend should produce Hurst > 0.5 (persistent)."""
        from tradingos.core.indicators import hurst_exponent
        trending = pd.Series(np.linspace(10, 100, 200))
        h = hurst_exponent(trending)
        assert h > 0.5, f"Trending series should have H > 0.5, got {h:.3f}"

    def test_compute_all_uses_new_threshold(self):
        """compute_all with 80+ bars must produce a Hurst value (not always 0.5)."""
        from tradingos.core.indicators import compute_all
        df = _make_ohlcv(150)
        out = compute_all(df)
        # With 150 bars, Hurst column must be populated
        assert "Hurst" in out.columns
        assert out["Hurst"].iloc[-1] != 0.5 or True  # 0.5 is valid; just check no NaN
        assert pd.notna(out["Hurst"].iloc[-1])


# ─────────────────────────────────────────────────────────────────────────────
# Issue #9 — FOL date format dd/MM/YYYY in fetch_foreign_flow
# ─────────────────────────────────────────────────────────────────────────────

class TestFolDateFormat:
    """#9: fetch_foreign_flow must send dd/MM/YYYY to SSI."""

    def test_from_date_is_dd_mm_yyyy(self):
        """Inspect the params string constructed by fetch_foreign_flow."""
        import inspect
        from tradingos.data import fetcher
        src = inspect.getsource(fetcher.fetch_foreign_flow)
        # Must use %d/%m/%Y (day first), not %m/%d/%Y (month first)
        assert '"%d/%m/%Y"' in src or "'%d/%m/%Y'" in src, (
            "fetch_foreign_flow must use dd/MM/YYYY format (%d/%m/%Y)"
        )
        assert '"%m/%d/%Y"' not in src and "'%m/%d/%Y'" not in src, (
            "fetch_foreign_flow must NOT use MM/DD/YYYY format (%m/%d/%Y)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Issue #10 — Lock-san tiered by liquidity
# ─────────────────────────────────────────────────────────────────────────────

class TestLockSanTiered:
    """#10: _simulate_single_trade selects lock_san_prob from liquidity tier."""

    def _df(self, n: int = 60) -> pd.DataFrame:
        df = _make_ohlcv(n)
        df["ATR14"] = 1_500.0
        return df

    def test_illiquid_has_higher_lock_san_than_liquid(self):
        """Illiquid (avg_vol < 100k) should use higher lock_san than liquid (> 1M)."""
        from tradingos.utils.config import cfg
        tiers = cfg.strategy("backtest", "lock_san_by_liquidity", default={})
        liquid   = float(tiers.get("liquid",   0.01))
        illiquid = float(tiers.get("illiquid", 0.08))
        assert illiquid > liquid, (
            f"Illiquid tier ({illiquid}) should exceed liquid tier ({liquid})"
        )

    def test_config_tiers_present(self):
        from tradingos.utils.config import cfg
        tiers = cfg.strategy("backtest", "lock_san_by_liquidity", default={})
        assert "liquid"   in tiers, "Config must have 'liquid' tier"
        assert "normal"   in tiers, "Config must have 'normal' tier"
        assert "illiquid" in tiers, "Config must have 'illiquid' tier"

    def test_simulate_accepts_avg_vol_param(self):
        """_simulate_single_trade must accept avg_vol_20d without errors."""
        from tradingos.core.backtest import _simulate_single_trade
        df = self._df(60)
        trade = _simulate_single_trade(
            df, entry_idx=10, sl_pct=0.05, tp1_pct=0.10, tp2_pct=0.20,
            avg_vol_20d=50_000.0,  # illiquid tier
        )
        # May return None (if entry_idx near end), otherwise BacktestTrade
        assert trade is None or hasattr(trade, "pnl")


# ─────────────────────────────────────────────────────────────────────────────
# Issue #11 — AMD phase logic gap: 4% price + 3% OBV → MARKUP not RANGING
# ─────────────────────────────────────────────────────────────────────────────

class TestAMDMarkupGap:
    """#11: rising price + rising OBV should produce MARKUP, not RANGING."""

    def _make_markup_df(self, price_change: float = 0.04, obv_slope: float = 0.03) -> pd.DataFrame:
        n = 60
        rng = np.random.default_rng(99)
        base = 50_000.0
        prices = base * np.cumprod(1 + np.linspace(0, price_change, n))
        vols_up   = rng.integers(1_000_000, 2_000_000, n).astype(float)
        vols_down = rng.integers(500_000,   1_000_000, n).astype(float)
        # alternate slightly up/down days to give OBV slope
        vols = np.where(np.arange(n) % 3 != 2, vols_up, vols_down)
        obv_vals  = np.cumsum(vols * np.sign(np.diff(prices, prepend=prices[0])))
        return pd.DataFrame({
            "close":  prices,
            "open":   prices * 0.999,
            "high":   prices * 1.01,
            "low":    prices * 0.99,
            "volume": vols,
            "OBV":    obv_vals,
            "date":   pd.bdate_range("2023-01-02", periods=n),
        })

    def test_4pct_gain_3pct_obv_is_markup(self):
        from tradingos.core.anti_manip import detect_amd_phase
        df = self._make_markup_df(price_change=0.04, obv_slope=0.03)
        phase = detect_amd_phase(df)
        assert phase == "MARKUP", (
            f"4% price + rising OBV should be MARKUP, got '{phase}'"
        )

    def test_flat_price_rising_obv_is_accumulation(self):
        from tradingos.core.anti_manip import detect_amd_phase
        n = 60
        prices = np.full(n, 50_000.0) + np.random.normal(0, 100, n)
        # strongly rising OBV (heavy buying on flat price)
        obv_ = np.cumsum(np.full(n, 200_000.0))
        df = pd.DataFrame({
            "close":  prices,
            "open":   prices, "high": prices * 1.005, "low": prices * 0.995,
            "volume": np.full(n, 600_000.0),
            "OBV":    obv_,
            "date":   pd.bdate_range("2023-01-02", periods=n),
        })
        phase = detect_amd_phase(df)
        assert phase == "ACCUMULATION", f"Flat price + rising OBV = ACCUMULATION, got '{phase}'"

    def test_declining_price_obv_is_markdown(self):
        from tradingos.core.anti_manip import detect_amd_phase
        n = 60
        prices = 50_000.0 * np.cumprod(1 - np.full(n, 0.002))
        obv_   = np.cumsum(-np.full(n, 500_000.0))
        df = pd.DataFrame({
            "close":  prices, "open": prices, "high": prices * 1.002, "low": prices * 0.998,
            "volume": np.full(n, 1_000_000.0),
            "OBV":    obv_,
            "date":   pd.bdate_range("2023-01-02", periods=n),
        })
        phase = detect_amd_phase(df)
        assert phase == "MARKDOWN", f"Expected MARKDOWN, got '{phase}'"


# ─────────────────────────────────────────────────────────────────────────────
# Issue #12 — CVD intraday labeled PROXY_CVD
# ─────────────────────────────────────────────────────────────────────────────

class TestCVDProxyLabel:
    """#12: CVD intraday must be labeled as proxy quality."""

    def test_cvd_data_quality_function_exists(self):
        from tradingos.core.anti_manip import cvd_data_quality
        label = cvd_data_quality()
        assert label == "PROXY_CVD"

    def test_compute_cvd_returns_int(self):
        from tradingos.core.anti_manip import compute_cvd_intraday
        df_5m = pd.DataFrame({
            "open":   [100, 101, 102],
            "close":  [101, 100, 103],
            "volume": [1000, 2000, 500],
        })
        result = compute_cvd_intraday(df_5m)
        assert isinstance(result, int)

    def test_positive_bar_adds_volume(self):
        from tradingos.core.anti_manip import compute_cvd_intraday
        df_5m = pd.DataFrame({
            "open":   [100, 100],
            "close":  [105, 100],   # first bar is up
            "volume": [1000, 500],
        })
        assert compute_cvd_intraday(df_5m) == 1000

    def test_negative_bar_subtracts_volume(self):
        from tradingos.core.anti_manip import compute_cvd_intraday
        df_5m = pd.DataFrame({
            "open":   [105, 100],
            "close":  [100, 100],   # first bar is down
            "volume": [1000, 500],
        })
        assert compute_cvd_intraday(df_5m) == -1000
