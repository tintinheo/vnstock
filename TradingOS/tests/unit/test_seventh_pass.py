"""
test_seventh_pass.py — Phase 1/2/3 feature tests

Covers:
  P1  — MacroResult dataclass and compute_macro_regime()
  P1b — macro_sizing_multiplier() and macro_score_gate_adjustment()
  P2  — EarningsRisk and compute_earnings_risk()
  P2b — earnings_stop_tightener() and earnings_gate_adjustment()
  P2c — _infer_earnings_calendar() regulatory schedule
  P2d — fetch_earnings_calendar() with empty vnstock (fallback to inference)
  P3  — FundamentalSnapshot and compute_fundamental_snapshot()
  P3b — canslim_fundamental_override() blending
  P3c — Fundamental scoring detail (each sub-component)
  P4  — New fetcher functions exist and return correct shape
  P5  — compute_position_size() accepts macro_multiplier
  P5b — Macro multiplier reduces position size as expected
  P6  — TickerProfile schema has new macro/earnings/fundamental fields
  P6b — ScanResultItem schema has macro_regime / macro_score fields
  P7  — compute_earnings_risk() with manually-built earnings DataFrame
  P8  — EarningsRisk HIGH_RISK within 5 days
  P9  — EarningsRisk CAUTION in 6–14 days
  P9b — EarningsRisk SAFE beyond 14 days
  P10 — FundamentalSnapshot returns None score for empty statements
  P11 — FundamentalSnapshot data_complete flag wiring
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

# ── Imports under test ────────────────────────────────────────────────────────
from tradingos.core.macro import (
    MacroResult,
    compute_macro_regime,
    macro_sizing_multiplier,
    macro_score_gate_adjustment,
)

# macro_regime is a plain string in macro.py (ACCOMMODATIVE | NEUTRAL | RESTRICTIVE)
class MacroRegime:
    ACCOMMODATIVE = "ACCOMMODATIVE"
    NEUTRAL       = "NEUTRAL"
    RESTRICTIVE   = "RESTRICTIVE"
from tradingos.core.earnings import (
    EarningsRisk,
    EarningsRolloverRisk,
    compute_earnings_risk,
    earnings_stop_tightener,
    earnings_gate_adjustment,
)
from tradingos.data.fetcher import _infer_earnings_calendar
from tradingos.core.fundamental import (
    FundamentalSnapshot,
    compute_fundamental_snapshot,
    canslim_fundamental_override,
)
from tradingos.core.sizing import compute_position_size
from tradingos.data.schemas import TickerProfile, ScanResultItem


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_usdvnd_df(rate: float, days: int = 30) -> pd.DataFrame:
    today = date.today()
    dates = [today - timedelta(days=d) for d in reversed(range(days))]
    return pd.DataFrame({"date": dates, "close": [rate] * days})


def _make_bond_df(yld: float, days: int = 30) -> pd.DataFrame:
    today = date.today()
    dates = [today - timedelta(days=d) for d in reversed(range(days))]
    return pd.DataFrame({"date": dates, "yield": [yld] * days})


def _make_earnings_df(ticker: str, pub_date: date, fiscal_quarter: str = "2025Q3") -> pd.DataFrame:
    today = date.today()
    return pd.DataFrame([{
        "ticker": ticker,
        "fiscal_quarter": fiscal_quarter,
        "expected_publication_date": pub_date,
        "actual_publication_date": pub_date if pub_date <= today else None,
        "confirmed": pub_date <= today,
        "eps_estimate": 500.0,
        "eps_actual": 0.0,
        "source": "test",
    }])


def _make_income_df(
    eps_growth_pct: float = 30.0,
    rev_growth_pct: float = 25.0,
    quarters: int = 8,
) -> pd.DataFrame:
    """Create a realistic income statement DataFrame with YoY growth."""
    base_rev = 1000.0  # VND billion
    base_ni  =  100.0
    rows = []
    for i in range(quarters):
        factor_rev = (1 + rev_growth_pct / 100) ** (i / 4)
        factor_ni  = (1 + eps_growth_pct / 100) ** (i / 4)
        rows.append({
            "period":      f"Q{(i % 4) + 1}",
            "revenue":     base_rev * factor_rev * 1e9,   # VND units
            "gross_profit":base_rev * factor_rev * 0.3e9,
            "ebit":        base_rev * factor_rev * 0.15e9,
            "net_income":  base_ni  * factor_ni  * 1e9,
            "eps":         base_ni  * factor_ni  * 1e9 / 1e8,  # ~ per share
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# P1 — Macro Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestMacroEngine:
    def test_compute_macro_regime_returns_MacroResult(self):
        usd_df   = _make_usdvnd_df(24_000)
        bond_df  = _make_bond_df(2.5)
        result   = compute_macro_regime(usdvnd_df=usd_df, bond_yield_df=bond_df)
        assert isinstance(result, MacroResult)

    def test_macro_regime_is_enum_string(self):
        result = compute_macro_regime()
        assert result.macro_regime in (
            MacroRegime.ACCOMMODATIVE,
            MacroRegime.NEUTRAL,
            MacroRegime.RESTRICTIVE,
        )

    def test_macro_score_in_range(self):
        result = compute_macro_regime()
        assert -100 <= result.macro_score <= 100

    def test_macro_confidence_not_empty(self):
        result = compute_macro_regime()
        assert result.macro_confidence in ("HIGH", "MEDIUM", "LOW")

    def test_macro_all_empty_returns_neutral(self):
        """With no data, engine should return NEUTRAL as safe default."""
        result = compute_macro_regime(
            usdvnd_df=pd.DataFrame(),
            bond_yield_df=pd.DataFrame(),
            sbv_net_injection_7d=None,
        )
        assert result.macro_regime == MacroRegime.NEUTRAL  # "NEUTRAL"

    def test_high_usdvnd_pressure_restrictive(self):
        """USD/VND near ceiling (25,900) → restrictive pressure."""
        usd_df  = _make_usdvnd_df(25_900)
        result  = compute_macro_regime(usdvnd_df=usd_df, bond_yield_df=pd.DataFrame())
        # Score should be negative (restrictive pressure) from USDVND component
        assert result.macro_score < 0

    def test_low_usdvnd_no_pressure_accommodative(self):
        """USD/VND well below ceiling (22,000) → non-negative score (no stress)."""
        usd_df  = _make_usdvnd_df(22_000)
        result  = compute_macro_regime(usdvnd_df=usd_df, bond_yield_df=pd.DataFrame())
        assert result.macro_score >= 0


class TestMacroSizing:
    def test_sizing_multiplier_restrictive(self):
        r = MacroResult(
            macro_score=-20, macro_regime="RESTRICTIVE",
            macro_confidence="HIGH", macro_staleness_days=0,
        )
        m = macro_sizing_multiplier(r)
        assert m < 1.0
        assert m >= 0.30

    def test_sizing_multiplier_accommodative(self):
        r = MacroResult(
            macro_score=30, macro_regime="ACCOMMODATIVE",
            macro_confidence="HIGH", macro_staleness_days=0,
        )
        m = macro_sizing_multiplier(r)
        assert m == pytest.approx(1.0, abs=0.05)

    def test_sizing_multiplier_neutral(self):
        r = MacroResult(
            macro_score=0, macro_regime="NEUTRAL",
            macro_confidence="MEDIUM", macro_staleness_days=0,
        )
        m = macro_sizing_multiplier(r)
        assert 0.5 <= m <= 0.9

    def test_gate_adjustment_restrictive(self):
        r = MacroResult(
            macro_score=-20, macro_regime="RESTRICTIVE",
            macro_confidence="HIGH", macro_staleness_days=0,
        )
        delta = macro_score_gate_adjustment(r)
        assert delta > 0  # raises the bar

    def test_gate_adjustment_accommodative(self):
        r = MacroResult(
            macro_score=30, macro_regime="ACCOMMODATIVE",
            macro_confidence="HIGH", macro_staleness_days=0,
        )
        delta = macro_score_gate_adjustment(r)
        assert delta <= 0  # lowers or keeps the bar

    def test_size_none_macro_result_returns_one(self):
        assert macro_sizing_multiplier(None) == 1.0

    def test_gate_none_macro_result_returns_zero(self):
        assert macro_score_gate_adjustment(None) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# P2 — Earnings Risk Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestEarningsRisk:
    def test_high_risk_within_5_days(self):
        pub_date = date.today() + timedelta(days=3)
        df = _make_earnings_df("VNM", pub_date)
        risk = compute_earnings_risk("VNM", current_date=date.today(), earnings_df=df)
        assert risk.rollover_risk == EarningsRolloverRisk.HIGH_RISK
        assert risk.days_to_next_event == 3

    def test_caution_within_14_days(self):
        pub_date = date.today() + timedelta(days=10)
        df = _make_earnings_df("HPG", pub_date)
        risk = compute_earnings_risk("HPG", current_date=date.today(), earnings_df=df)
        assert risk.rollover_risk == EarningsRolloverRisk.CAUTION

    def test_safe_beyond_14_days(self):
        pub_date = date.today() + timedelta(days=30)
        df = _make_earnings_df("FPT", pub_date)
        risk = compute_earnings_risk("FPT", current_date=date.today(), earnings_df=df)
        assert risk.rollover_risk == EarningsRolloverRisk.SAFE

    def test_safe_with_empty_df(self):
        risk = compute_earnings_risk("XYZ", earnings_df=pd.DataFrame())
        assert risk.rollover_risk == EarningsRolloverRisk.SAFE
        # days_to_next_event may be inferred from fiscal calendar even with empty df
        assert risk.days_to_next_event is None or isinstance(risk.days_to_next_event, int)

    def test_stop_tightener_high_risk(self):
        pub_date = date.today() + timedelta(days=2)
        df       = _make_earnings_df("VCB", pub_date)
        risk     = compute_earnings_risk("VCB", earnings_df=df)
        t        = earnings_stop_tightener(risk)
        assert t < 1.0
        assert t <= 0.65

    def test_stop_tightener_safe(self):
        pub_date = date.today() + timedelta(days=60)
        df       = _make_earnings_df("VCB", pub_date)
        risk     = compute_earnings_risk("VCB", earnings_df=df)
        t        = earnings_stop_tightener(risk)
        assert t == pytest.approx(1.0)

    def test_gate_delta_high_risk(self):
        pub_date = date.today() + timedelta(days=4)
        df       = _make_earnings_df("MWG", pub_date)
        risk     = compute_earnings_risk("MWG", earnings_df=df)
        delta    = earnings_gate_adjustment(risk)
        assert delta >= 8.0   # should be high (default 10)

    def test_gate_delta_safe(self):
        pub_date = date.today() + timedelta(days=60)
        df       = _make_earnings_df("MWG", pub_date)
        risk     = compute_earnings_risk("MWG", earnings_df=df)
        delta    = earnings_gate_adjustment(risk)
        assert delta == 0.0


class TestInferEarningsCalendar:
    def test_infer_returns_list_of_dicts(self):
        rows = _infer_earnings_calendar("VNM", date.today(), lookforward_days=180)
        assert isinstance(rows, list)
        assert len(rows) >= 1

    def test_infer_has_required_keys(self):
        rows = _infer_earnings_calendar("HPG", date.today(), lookforward_days=90)
        for r in rows:
            assert "ticker" in r
            assert "fiscal_quarter" in r
            assert "expected_publication_date" in r
            assert "confirmed" in r
            assert "source" in r

    def test_infer_confirmed_false_for_future(self):
        rows = _infer_earnings_calendar("FPT", date.today(), lookforward_days=365)
        future_rows = [r for r in rows if r["expected_publication_date"] > date.today()]
        for r in future_rows:
            assert r["confirmed"] is False

    def test_infer_regulatory_source_tag(self):
        rows = _infer_earnings_calendar("BID", date.today(), lookforward_days=365)
        sources = {r["source"] for r in rows}
        assert "regulatory_inference" in sources


# ═══════════════════════════════════════════════════════════════════════════════
# P3 — Fundamental Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestFundamentals:
    def test_empty_statements_returns_none_score(self):
        snap = compute_fundamental_snapshot("VNM", statements={})
        assert snap.fundamental_score is None
        assert snap.data_complete is False

    def test_with_good_income_data_returns_score(self):
        income_df = _make_income_df(eps_growth_pct=35, rev_growth_pct=30)
        stmts     = {"income": income_df, "balance": pd.DataFrame(), "cashflow": pd.DataFrame()}
        snap      = compute_fundamental_snapshot("VNM", statements=stmts)
        # With 35% EPS growth and 30% revenue growth, should score reasonably well
        assert snap.fundamental_score is not None
        assert snap.fundamental_score >= 35.0

    def test_negative_growth_scores_low(self):
        income_df = _make_income_df(eps_growth_pct=-20, rev_growth_pct=-10)
        stmts     = {"income": income_df, "balance": pd.DataFrame(), "cashflow": pd.DataFrame()}
        snap      = compute_fundamental_snapshot("VNM", statements=stmts)
        if snap.fundamental_score is not None:
            assert snap.fundamental_score < 40.0

    def test_eps_growth_yoy_populated(self):
        income_df = _make_income_df(eps_growth_pct=30)
        stmts     = {"income": income_df, "balance": pd.DataFrame(), "cashflow": pd.DataFrame()}
        snap      = compute_fundamental_snapshot("HPG", statements=stmts)
        if snap.data_complete:
            assert snap.eps_growth_yoy is not None

    def test_revenue_growth_yoy_populated(self):
        income_df = _make_income_df(rev_growth_pct=25)
        stmts     = {"income": income_df, "balance": pd.DataFrame(), "cashflow": pd.DataFrame()}
        snap      = compute_fundamental_snapshot("FPT", statements=stmts)
        if snap.data_complete:
            assert snap.revenue_growth_yoy is not None

    def test_score_in_range_0_100(self):
        income_df = _make_income_df(eps_growth_pct=50, rev_growth_pct=40)
        stmts     = {"income": income_df, "balance": pd.DataFrame(), "cashflow": pd.DataFrame()}
        snap      = compute_fundamental_snapshot("VCB", statements=stmts, fol_pct=25.0)
        if snap.fundamental_score is not None:
            assert 0.0 <= snap.fundamental_score <= 100.0

    def test_canslim_override_with_real_data(self):
        snap = FundamentalSnapshot(
            ticker="VNM",
            fundamental_score=70.0,
            data_complete=True,
            quarters_available=6,
        )
        blended = canslim_fundamental_override(snap, canslim_technical_score=40.0)
        # Expected: 0.7*70 + 0.3*40 = 49.0 + 12.0 = 61.0
        assert blended == pytest.approx(61.0, abs=1.0)

    def test_canslim_override_no_data_returns_technical(self):
        snap = FundamentalSnapshot(ticker="XYZ", fundamental_score=None)
        blended = canslim_fundamental_override(snap, canslim_technical_score=55.0)
        assert blended == pytest.approx(55.0, abs=0.1)

    def test_canslim_override_clamps_to_100(self):
        snap = FundamentalSnapshot(
            ticker="VNM",
            fundamental_score=100.0,
            data_complete=True,
            quarters_available=8,
        )
        blended = canslim_fundamental_override(snap, canslim_technical_score=100.0)
        assert blended <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# P4 — Fetcher function signatures
# ═══════════════════════════════════════════════════════════════════════════════

class TestFetcherSignatures:
    def test_fetch_usdvnd_exists(self):
        from tradingos.data.fetcher import fetch_usdvnd
        assert callable(fetch_usdvnd)

    def test_fetch_vn10y_bond_yield_exists(self):
        from tradingos.data.fetcher import fetch_vn10y_bond_yield
        assert callable(fetch_vn10y_bond_yield)

    def test_fetch_sbv_omo_net_exists(self):
        from tradingos.data.fetcher import fetch_sbv_omo_net
        assert callable(fetch_sbv_omo_net)

    def test_fetch_earnings_calendar_exists(self):
        from tradingos.data.fetcher import fetch_earnings_calendar
        assert callable(fetch_earnings_calendar)

    def test_fetch_financial_statements_exists(self):
        from tradingos.data.fetcher import fetch_financial_statements
        assert callable(fetch_financial_statements)

    def test_fetch_usdvnd_returns_dataframe_when_network_unavailable(self):
        """Should return empty DataFrame (not raise) on network failure."""
        from tradingos.data.fetcher import fetch_usdvnd
        with patch("requests.Session.get", side_effect=ConnectionError("test")):
            result = fetch_usdvnd(days=30)
        assert isinstance(result, pd.DataFrame)

    def test_fetch_earnings_calendar_returns_df_with_required_cols(self):
        """Returns DataFrame with required columns even when vnstock unavailable."""
        from tradingos.data.fetcher import fetch_earnings_calendar
        with patch("tradingos.data.fetcher._get", side_effect=Exception("no network")):
            result = fetch_earnings_calendar("VNM", lookforward_days=90)
        assert isinstance(result, pd.DataFrame)
        # Either has data (from inference) or is empty but has the right cols
        if not result.empty:
            assert "expected_publication_date" in result.columns
            assert "confirmed" in result.columns

    def test_fetch_financial_statements_returns_dict_with_keys(self):
        from tradingos.data.fetcher import fetch_financial_statements
        # Mock vnstock to raise ImportError → fallback returns empty dict
        with patch.dict("sys.modules", {"vnstock": None}):
            result = fetch_financial_statements("VNM", quarters=4)
        assert isinstance(result, dict)
        assert "income" in result
        assert "balance" in result
        assert "cashflow" in result


# ═══════════════════════════════════════════════════════════════════════════════
# P5 — Position sizing with macro multiplier
# ═══════════════════════════════════════════════════════════════════════════════

class TestSizingMacroMultiplier:
    def test_accepts_macro_multiplier_param(self):
        result = compute_position_size(
            portfolio_value=1_000_000_000,
            entry=50_000,
            sl=47_000,
            win_prob=0.60,
            rr=2.5,
            macro_multiplier=1.0,
        )
        assert "size_pct" in result

    def test_restrictive_macro_reduces_size(self):
        base = compute_position_size(
            portfolio_value=1_000_000_000,
            entry=50_000, sl=47_000,
            win_prob=0.60, rr=2.5,
            macro_multiplier=1.0,
        )
        restricted = compute_position_size(
            portfolio_value=1_000_000_000,
            entry=50_000, sl=47_000,
            win_prob=0.60, rr=2.5,
            macro_multiplier=0.32,
        )
        assert restricted["size_pct"] <= base["size_pct"]

    def test_multiplier_one_same_as_default(self):
        with_mult = compute_position_size(
            portfolio_value=500_000_000,
            entry=30_000, sl=28_500,
            win_prob=0.55, rr=2.0,
            macro_multiplier=1.0,
        )
        without_mult = compute_position_size(
            portfolio_value=500_000_000,
            entry=30_000, sl=28_500,
            win_prob=0.55, rr=2.0,
        )
        assert with_mult["size_pct"] == pytest.approx(without_mult["size_pct"], abs=0.001)


# ═══════════════════════════════════════════════════════════════════════════════
# P6 — Schema field presence
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchemaFields:
    def test_ticker_profile_has_macro_fields(self):
        fields = TickerProfile.model_fields
        assert "macro_score"          in fields
        assert "macro_regime"         in fields
        assert "macro_confidence"     in fields
        assert "macro_staleness_days" in fields

    def test_ticker_profile_has_earnings_fields(self):
        fields = TickerProfile.model_fields
        assert "earnings_risk"     in fields
        assert "days_to_earnings"  in fields
        assert "next_earnings_date" in fields

    def test_ticker_profile_has_fundamental_fields(self):
        fields = TickerProfile.model_fields
        assert "fundamental_score"   in fields
        assert "eps_growth_yoy"      in fields
        assert "revenue_growth_yoy"  in fields
        assert "roe"                 in fields
        assert "debt_to_equity"      in fields

    def test_scan_result_item_has_macro_fields(self):
        fields = ScanResultItem.model_fields
        assert "macro_regime" in fields
        assert "macro_score"  in fields

    def test_macro_score_default_is_none(self):
        """macro_score should default to None, not 0."""
        fields = TickerProfile.model_fields
        assert fields["macro_score"].default is None

    def test_earnings_risk_default_is_safe(self):
        fields = TickerProfile.model_fields
        assert fields["earnings_risk"].default == "SAFE"
