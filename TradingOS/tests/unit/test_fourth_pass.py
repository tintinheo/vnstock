"""
Fourth-pass regression tests covering 3 scanner pipeline bugs.

Issue mapping:
  S1 — scanner_service: compute_smart_money_score called with amd as positional arg
       to `quote` (6th param), not `amd_phase` (7th param) → AMD alignment always 4pts
  S2 — scanner_service: stealth_detail injected as {} before MFPM is called →
       stealth bonus always 0 inside score_mode_w
  S3 — money_flow: fol component scores 3 ("neutral") when fol_net column absent →
       phantom 3 points on every PROXY_OHLCV ticker
"""
from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 120, seed: int = 1, trend: float = 0.001) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", periods=n)
    close = 30_000.0 * np.cumprod(1 + rng.normal(trend, 0.015, n))
    volume = rng.integers(200_000, 2_000_000, n).astype(float)
    return pd.DataFrame({
        "date":   dates,
        "open":   close * rng.uniform(0.99, 1.01, n),
        "high":   close * rng.uniform(1.00, 1.02, n),
        "low":    close * rng.uniform(0.98, 1.00, n),
        "close":  close,
        "volume": volume,
    })


def _make_indicators(n: int = 120) -> pd.DataFrame:
    from tradingos.core.indicators import compute_all
    return compute_all(_make_ohlcv(n))


def _make_flow(df: pd.DataFrame) -> pd.DataFrame:
    from tradingos.core.money_flow import proxy_whale_net_from_daily
    return proxy_whale_net_from_daily(df)


# ─────────────────────────────────────────────────────────────────────────────
# S1 — amd_phase passed by keyword, not positional
# ─────────────────────────────────────────────────────────────────────────────

class TestS1AmdPhaseKeyword:
    """
    Bug: scanner called compute_smart_money_score(ticker, df, flow, None, None, amd)
    The 6th positional arg is `quote`, so amd_phase received its default "RANGING",
    and cvd_today received its default None.  AMD alignment always scored 4 pts
    regardless of actual phase.
    """

    def test_distribution_phase_scores_zero_amd(self):
        """With amd_phase='DISTRIBUTION', comps['amd'] must be 0 not 4."""
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df)
        result = compute_smart_money_score(
            "TEST", df, flow,
            pt_deals_df=None, order_book=None, quote=None,
            amd_phase="DISTRIBUTION",
        )
        assert result["components"]["amd"] == 0, (
            f"DISTRIBUTION phase must score 0 amd points, got {result['components']['amd']}"
        )

    def test_accumulation_phase_scores_ten_amd(self):
        """With amd_phase='ACCUMULATION', comps['amd'] must be 10."""
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df)
        result = compute_smart_money_score(
            "TEST", df, flow,
            pt_deals_df=None, order_book=None, quote=None,
            amd_phase="ACCUMULATION",
        )
        assert result["components"]["amd"] == 10, (
            f"ACCUMULATION phase must score 10 amd points, got {result['components']['amd']}"
        )

    def test_ranging_phase_scores_four_amd(self):
        """Default 'RANGING' → 4 pts (correct default)."""
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df)
        result = compute_smart_money_score(
            "TEST", df, flow,
            pt_deals_df=None, order_book=None, quote=None,
            amd_phase="RANGING",
        )
        assert result["components"]["amd"] == 4

    def test_amd_difference_is_significant(self):
        """Distribution vs Accumulation must differ by exactly 10 SMS points."""
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df)
        accum = compute_smart_money_score(
            "TEST", df, flow, amd_phase="ACCUMULATION"
        )
        distr = compute_smart_money_score(
            "TEST", df, flow, amd_phase="DISTRIBUTION"
        )
        diff = accum["components"]["amd"] - distr["components"]["amd"]
        assert diff == 10, f"Accumulation vs Distribution amd diff should be 10, got {diff}"

    def test_scanner_source_uses_keyword_arg(self):
        """Source code of _score_ticker must use amd_phase= keyword for SMS call."""
        import tradingos.engines.scanner_service as ss
        src = inspect.getsource(ss.ScannerService._score_ticker)
        assert "amd_phase=amd" in src, (
            "_score_ticker must pass amd_phase=amd by keyword to compute_smart_money_score"
        )
        # Must NOT pass amd as the 6th positional arg
        # Simple check: raw positional-only call would look like "flow_df, None, None, amd"
        assert "flow_df, None, None, amd)" not in src.replace(" ", ""), (
            "amd must not be the 6th positional argument (that slot is `quote`)"
        )

    def test_cvd_today_default_none_gives_five_pts(self):
        """When cvd_today=None (default), comps['cvd_today'] must be 5 (the sentinel)."""
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df)
        result = compute_smart_money_score("TEST", df, flow)
        assert result["components"]["cvd_today"] == 5, (
            "cvd_today=None must yield 5 (unknown / neutral sentinel)"
        )

    def test_proxy_cvd_is_downweighted_vs_real_flow(self):
        """Positive proxy CVD must contribute less than equally positive REAL_FLOW."""
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df)
        proxy = compute_smart_money_score(
            "TEST", df, flow,
            cvd_today=int(df["volume"].tail(20).mean() * 0.20),
            cvd_data_quality="OHLCV_PROXY",
        )
        real = compute_smart_money_score(
            "TEST", df, flow,
            cvd_today=int(df["volume"].tail(20).mean() * 0.20),
            cvd_data_quality="REAL_FLOW",
        )
        assert proxy["components"]["cvd_today"] < real["components"]["cvd_today"], (
            "OHLCV proxy CVD must be scored below REAL_FLOW CVD"
        )

    def test_proxy_cvd_stays_near_neutral_band(self):
        """Proxy CVD should nudge SMS, not dominate it."""
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df)
        bullish = compute_smart_money_score(
            "TEST", df, flow,
            cvd_today=int(df["volume"].tail(20).mean() * 0.25),
            cvd_data_quality="OHLCV_PROXY",
        )
        bearish = compute_smart_money_score(
            "TEST", df, flow,
            cvd_today=-int(df["volume"].tail(20).mean() * 0.25),
            cvd_data_quality="OHLCV_PROXY",
        )
        assert bullish["components"]["cvd_today"] <= 7
        assert bearish["components"]["cvd_today"] >= 3


# ─────────────────────────────────────────────────────────────────────────────
# S2 — stealth_detail wired into MFPM before scoring
# ─────────────────────────────────────────────────────────────────────────────

class TestS2StealthDetailWired:
    """
    Bug: scanner passed stealth_detail={} to compute_mfpm, then computed the real
    stealth result afterwards (only used for the output column).  score_mode_w
    always received confidence='LOW' → stealth_bonus=0, even for ASG which
    detect_stealth_accumulation marked as detected.
    """

    def test_stealth_computed_before_mfpm_in_source(self):
        """detect_stealth_accumulation must appear before compute_mfpm in _score_ticker."""
        import tradingos.engines.scanner_service as ss
        src = inspect.getsource(ss.ScannerService._score_ticker)
        stealth_pos = src.find("detect_stealth_accumulation")
        mfpm_pos    = src.find("compute_mfpm")
        assert stealth_pos != -1, "detect_stealth_accumulation not found in _score_ticker"
        assert mfpm_pos    != -1, "compute_mfpm not found in _score_ticker"
        assert stealth_pos < mfpm_pos, (
            "detect_stealth_accumulation must appear BEFORE compute_mfpm so the result "
            "can be passed as stealth_detail"
        )

    def test_stealth_detail_not_empty_dict_in_source(self):
        """stealth_detail must not be hardcoded as {} in the compute_mfpm call."""
        import tradingos.engines.scanner_service as ss
        src = inspect.getsource(ss.ScannerService._score_ticker)
        # Find the compute_mfpm block
        mfpm_idx = src.find("compute_mfpm")
        mfpm_block = src[mfpm_idx: mfpm_idx + 400]
        assert '"stealth_detail": {}' not in mfpm_block, (
            'stealth_detail must not be hardcoded as {} — it should use the actual stealth result'
        )
        assert '"stealth_detail": stealth' in mfpm_block, (
            'stealth_detail must be set to the stealth variable, not {}'
        )

    def test_score_mode_w_uses_stealth_detail(self):
        """score_mode_w must award bonus points when stealth_detail shows HIGH confidence."""
        from tradingos.core.mfpm import score_mode_w
        sms_high_stealth = {
            "sms": 50,
            "components": {
                "mcvd": 12, "vqs": 8, "fol": 0, "obv": 8,
                "amd": 10, "cvd_today": 5, "pt_flow": 0,
            },
            "mcvd_detail": {"mcvd_vs_price": "CONFIRM"},
            "stealth_detail": {"detected": True, "confidence": "HIGH"},
        }
        sms_no_stealth = {
            "sms": 50,
            "components": {
                "mcvd": 12, "vqs": 8, "fol": 0, "obv": 8,
                "amd": 10, "cvd_today": 5, "pt_flow": 0,
            },
            "mcvd_detail": {"mcvd_vs_price": "CONFIRM"},
            "stealth_detail": {},  # empty — old bug behaviour
        }
        score_with    = score_mode_w(sms_high_stealth)
        score_without = score_mode_w(sms_no_stealth)
        assert score_with > score_without, (
            f"HIGH stealth_detail must raise mode_w_score: "
            f"with={score_with} without={score_without}"
        )
        assert score_with - score_without == 10, (
            f"HIGH stealth bonus must be exactly 10 pts, got {score_with - score_without}"
        )

    def test_score_mode_w_medium_stealth_bonus_5(self):
        """MEDIUM stealth confidence must award 5 bonus points."""
        from tradingos.core.mfpm import score_mode_w
        base_comps = {
            "mcvd": 12, "vqs": 8, "fol": 0, "obv": 8,
            "amd": 10, "cvd_today": 5, "pt_flow": 0,
        }
        sms_medium = {
            "sms": 43, "components": base_comps,
            "mcvd_detail": {"mcvd_vs_price": "CONFIRM"},
            "stealth_detail": {"detected": True, "confidence": "MEDIUM"},
        }
        sms_none = {
            "sms": 43, "components": base_comps,
            "mcvd_detail": {"mcvd_vs_price": "CONFIRM"},
            "stealth_detail": {"detected": False, "confidence": "LOW"},
        }
        diff = score_mode_w(sms_medium) - score_mode_w(sms_none)
        assert diff == 5, f"MEDIUM stealth bonus should be 5, got {diff}"


# ─────────────────────────────────────────────────────────────────────────────
# S3 — fol scores 0 (not 3) when no fol_net data
# ─────────────────────────────────────────────────────────────────────────────

class TestS3FolNoDataScoresZero:
    """
    Bug: when fol_net column is absent (always true for PROXY_OHLCV flow_df),
    fol_ratio == 0 fell through to the `else: comps["fol"] = 3` branch.
    This injected a phantom 3 pts on every single ticker, inflating all SMS scores
    by a constant that carried zero market information.
    """

    def test_no_fol_column_scores_zero(self):
        """flow_df without fol_net column must produce comps['fol'] == 0."""
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df)  # proxy_whale_net_from_daily never adds fol_net
        assert "fol_net" not in flow.columns, \
            "Test precondition: proxy flow must not have fol_net column"
        result = compute_smart_money_score("TEST", df, flow)
        assert result["components"]["fol"] == 0, (
            f"fol without fol_net data must score 0 not 3, got {result['components']['fol']}"
        )

    def test_zero_fol_net_scores_zero(self):
        """fol_net present but exactly 0 (neutral) must also score 0."""
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df).copy()
        flow["fol_net"] = 0  # explicitly zero — neutral, no edge
        result = compute_smart_money_score("TEST", df, flow)
        assert result["components"]["fol"] == 0, (
            f"fol_net=0 (neutral) must score 0, got {result['components']['fol']}"
        )

    def test_positive_fol_net_scores_correctly(self):
        """Real positive fol_net (foreign buying) must still score > 0."""
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df).copy()
        avg_vol = float(df["volume"].tail(20).mean())
        # Set fol_net to 10% of avg vol → fol_ratio > 0.02
        flow["fol_net"] = avg_vol * 0.1
        result = compute_smart_money_score("TEST", df, flow)
        assert result["components"]["fol"] >= 10, (
            f"Strong foreign buying should score >=10, got {result['components']['fol']}"
        )

    def test_negative_fol_net_scores_zero(self):
        """Strong foreign selling (fol_ratio < -0.02) must score 0."""
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df).copy()
        avg_vol = float(df["volume"].tail(20).mean())
        flow["fol_net"] = -avg_vol * 0.5  # heavy foreign selling
        result = compute_smart_money_score("TEST", df, flow)
        assert result["components"]["fol"] == 0, (
            f"Heavy foreign selling should score 0, got {result['components']['fol']}"
        )

    def test_sms_without_fol_lower_than_before(self):
        """
        With the fix, a PROXY_OHLCV SMS score must be 3 pts lower than old behaviour
        (because the phantom fol=3 is now removed).
        Verify the component sum is correct: max without real data is now 82, not 85.
        Max components without real data:
            mcvd=20 (if UP+consistent), vqs=15, fol=0, obv=15, amd=10, cvd=5, pt=0
            → max theoretical = 65 (mcvd realistically lower due to PROXY_OHLCV)
        """
        from tradingos.core.money_flow import compute_smart_money_score
        df   = _make_indicators()
        flow = _make_flow(df)
        result = compute_smart_money_score("TEST", df, flow)
        # Old cap was 85 (pt_flow=0), new cap is 82 (pt_flow=0, fol=0)
        assert result["components"]["fol"] == 0
        # Total must not include the phantom 3 pts
        component_sum = sum(result["components"].values())
        # pt_flow=0 and fol=0, so max from other 5 components = 20+15+15+10+10 = 70
        assert component_sum <= 70, (
            f"Without real fol/PT data, component sum should be <=70, got {component_sum}"
        )

    def test_fol_source_has_no_data_guard(self):
        """money_flow source must have explicit has_fol_data guard."""
        import tradingos.core.money_flow as mf
        src = inspect.getsource(mf.compute_smart_money_score)
        assert "has_fol_data" in src, \
            "compute_smart_money_score must use has_fol_data flag to guard fol scoring"
