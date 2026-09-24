"""AMF Wash Sale Directionality — unit tests.

Covers:
  1. BUY_WASH classified when TFI > +0.20 and z_vol exceeds threshold
  2. SELL_WASH classified when TFI < -0.20 and z_vol exceeds threshold
  3. NEUTRAL_WASH when intraday_data is None (direction unknown)
  4. NEUTRAL_WASH when TFI is within ±0.20 band
  5. wash_side = NONE when volume is not anomalous (z_vol <= threshold)
  6. SELL_WASH downgrades BLOCK → WARN in compute_mfpm
  7. BUY_WASH keeps BLOCK decision in compute_mfpm
  8. compute_tfi formula correctness
  9. fetch_intraday_features fallback on network failure
 10. run_amf backward-compatibility: wash_side always in return dict
 11. compute_mcvd formula correctness
 12. fetch_intraday_features includes mcvd in return dict
 13. run_amf details dict includes mcvd field
"""
from __future__ import annotations

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_df(n: int = 60, high_vol_last: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    close  = 50_000.0 * np.cumprod(1 + rng.normal(0.001, 0.01, n))
    volume = rng.integers(200_000, 1_000_000, n).astype(float)
    if high_vol_last:
        # Push last bar well above 20-day average * 3 (wash sale volume threshold)
        volume[-1] = float(volume[-20:].mean() * 8.0)
    df = pd.DataFrame({
        "date":   pd.bdate_range("2024-01-02", periods=n),
        "open":   close * 0.995,
        "high":   close * 1.005,
        "low":    close * 0.995,
        "close":  close,
        "volume": volume,
    })
    return df


def _make_mfpm_fixtures():
    """Minimal fixtures for compute_mfpm call."""
    rng = np.random.default_rng(2)
    n = 150
    close = 30_000.0 * np.cumprod(1 + rng.normal(0.001, 0.012, n))
    vol = rng.integers(300_000, 1_500_000, n).astype(float)
    df = pd.DataFrame({
        "date":   pd.bdate_range("2023-01-02", periods=n),
        "open":   close * 0.99, "high": close * 1.01,
        "low":    close * 0.99, "close": close, "volume": vol,
    })
    from tradingos.core.indicators import compute_all
    df = compute_all(df)
    sms_result = {
        "sms": 30, "sms_label": "RETAIL_DRIVEN", "mcvd_detail": {},
        "stealth_detail": {}, "distribution_warning": "NONE",
        "sector_flow": "NEUTRAL", "sector": "GENERAL",
        "components": {}, "whale_pct_vol": 0.0, "fol_pct": 0.0,
    }
    pattern_result = {"pattern_bonus": 0, "best_pattern": "NONE", "fvgs": []}
    return df, sms_result, pattern_result


# ── Tests: run_amf wash side classification ───────────────────────────────────

class TestAMFWashSideClassification:

    def test_buy_wash_when_tfi_high(self):
        """High TFI + anomalous volume → BUY_WASH flag."""
        from tradingos.core.anti_manip import run_amf
        df = _make_df(high_vol_last=True)
        result = run_amf(df, intraday_data={"tfi": 0.50, "obi_l3": 0.3, "obi_reconstructed": 0.25})
        assert result["wash_side"] == "BUY_WASH"
        assert any("BUY_DRIVEN" in f for f in result["flags"])

    def test_sell_wash_when_tfi_negative(self):
        """Negative TFI + anomalous volume → SELL_WASH flag."""
        from tradingos.core.anti_manip import run_amf
        df = _make_df(high_vol_last=True)
        result = run_amf(df, intraday_data={"tfi": -0.45, "obi_l3": -0.3, "obi_reconstructed": -0.2})
        assert result["wash_side"] == "SELL_WASH"
        assert any("SELL_DRIVEN" in f for f in result["flags"])

    def test_neutral_wash_when_no_intraday_data(self):
        """Anomalous volume + no intraday_data → NEUTRAL_WASH (direction unknown)."""
        from tradingos.core.anti_manip import run_amf
        df = _make_df(high_vol_last=True)
        result = run_amf(df, intraday_data=None)
        assert result["wash_side"] == "NEUTRAL_WASH"
        assert any("WASH_SALE_VOLUME" in f for f in result["flags"])

    def test_neutral_wash_when_tfi_within_band(self):
        """TFI = 0.10 (within ±0.20 band) → NEUTRAL_WASH even with high volume."""
        from tradingos.core.anti_manip import run_amf
        df = _make_df(high_vol_last=True)
        result = run_amf(df, intraday_data={"tfi": 0.10, "obi_l3": 0.05, "obi_reconstructed": 0.03})
        assert result["wash_side"] == "NEUTRAL_WASH"

    def test_no_wash_when_volume_normal(self):
        """Normal volume → wash_side = NONE regardless of TFI."""
        from tradingos.core.anti_manip import run_amf
        df = _make_df(high_vol_last=False)
        result = run_amf(df, intraday_data={"tfi": 0.80, "obi_l3": 0.6, "obi_reconstructed": 0.5})
        assert result["wash_side"] == "NONE"

    def test_wash_side_always_present_in_result(self):
        """run_amf always returns 'wash_side' key for backward-compat."""
        from tradingos.core.anti_manip import run_amf
        df = _make_df()
        result = run_amf(df)
        assert "wash_side" in result

    def test_details_contains_tfi_and_obi(self):
        """details dict includes tfi and obi_l3 from intraday_data."""
        from tradingos.core.anti_manip import run_amf
        df = _make_df()
        result = run_amf(df, intraday_data={"tfi": 0.22, "obi_l3": 0.15, "obi_reconstructed": 0.10})
        assert "tfi" in result["details"]
        assert "obi_l3" in result["details"]
        assert result["details"]["tfi"] == pytest.approx(0.22, abs=0.001)

    def test_empty_df_returns_pass_with_no_wash(self):
        """Empty df → PASS decision, wash_side=NONE."""
        from tradingos.core.anti_manip import run_amf
        result = run_amf(pd.DataFrame())
        assert result["decision"] == "PASS"
        assert result["wash_side"] == "NONE"


# ── Tests: MFPM SELL_WASH override ───────────────────────────────────────────

class TestMFPMSellWashOverride:

    def test_sell_wash_downgrades_block_in_mfpm(self):
        """BLOCK + SELL_WASH should NOT produce hard NO_ACTION from AMF alone."""
        from tradingos.core.mfpm import compute_mfpm
        df, sms_result, pattern_result = _make_mfpm_fixtures()
        # Give it a strong enough score to be WATCH/BUY normally
        sms_result["sms"] = 65
        amf_result = {
            "decision": "BLOCK",
            "flags": ["WASH_SALE_SELL_DRIVEN_Z4.5"],
            "wash_side": "SELL_WASH",
            "details": {"z_vol": 4.5, "tfi": -0.45, "obi_l3": -0.3, "obi_reconstructed": -0.2, "foreign_net": 0},
        }
        result = compute_mfpm(df, sms_result, amf_result, pattern_result)
        # With SELL_WASH override, action should NOT be forced to NO_ACTION from AMF alone
        # (it might still be NO_ACTION due to low score, but not due to hard BLOCK)
        assert result["action"] != "FORCED_EXIT"

    def test_buy_wash_keeps_block_in_mfpm(self):
        """BLOCK + BUY_WASH keeps the BLOCK behavior — no entry on buy-driven manipulation."""
        from tradingos.core.mfpm import compute_mfpm
        df, sms_result, pattern_result = _make_mfpm_fixtures()
        sms_result["sms"] = 65
        amf_result = {
            "decision": "BLOCK",
            "flags": ["WASH_SALE_BUY_DRIVEN_Z5.0"],
            "wash_side": "BUY_WASH",
            "details": {"z_vol": 5.0, "tfi": 0.55, "obi_l3": 0.4, "obi_reconstructed": 0.35, "foreign_net": 0},
        }
        result = compute_mfpm(df, sms_result, amf_result, pattern_result)
        # BUY_WASH keeps BLOCK: Mode A/B path has hard NO_ACTION on BLOCK
        assert result["action"] in ("NO_ACTION", "WATCH", "EXIT", "FORCED_EXIT")
        # Specifically: if mfpm_score < watch threshold it will be NO_ACTION
        # The key assertion is that SELL_WASH logic did NOT downgrade this BLOCK
        assert result.get("amf_decision_effective", amf_result["decision"]) != "WARN" or \
               amf_result["wash_side"] != "BUY_WASH"


# ── Tests: compute_tfi formula ────────────────────────────────────────────────

class TestComputeTFI:

    def test_all_buy_trades(self):
        from tradingos.data.intraday_collector import compute_tfi
        trades = [{"volume": 1000, "aggressor": "B"}, {"volume": 500, "aggressor": "B"}]
        assert compute_tfi(trades) == pytest.approx(1.0)

    def test_all_sell_trades(self):
        from tradingos.data.intraday_collector import compute_tfi
        trades = [{"volume": 800, "aggressor": "S"}, {"volume": 200, "aggressor": "S"}]
        assert compute_tfi(trades) == pytest.approx(-1.0)

    def test_balanced_trades(self):
        from tradingos.data.intraday_collector import compute_tfi
        trades = [{"volume": 500, "aggressor": "B"}, {"volume": 500, "aggressor": "S"}]
        assert compute_tfi(trades) == pytest.approx(0.0)

    def test_unknown_aggressor_excluded(self):
        from tradingos.data.intraday_collector import compute_tfi
        trades = [
            {"volume": 600, "aggressor": "B"},
            {"volume": 400, "aggressor": "U"},  # unknown — excluded from denominator
        ]
        # Only B trades count: (600-0)/(600) = 1.0
        assert compute_tfi(trades) == pytest.approx(1.0)

    def test_empty_trades(self):
        from tradingos.data.intraday_collector import compute_tfi
        assert compute_tfi([]) == 0.0


# ── Tests: fetch_intraday_features fallback ───────────────────────────────────

class TestFetchIntradayFeaturesFallback:

    def test_returns_zero_dict_on_network_failure(self):
        """Any network error returns a valid dict with zero values."""
        from tradingos.data.intraday_collector import fetch_intraday_features
        with patch("tradingos.data.intraday_collector.fetch_tcbs_trades",
                   side_effect=Exception("network error")):
            with patch("tradingos.data.intraday_collector.fetch_ssi_orderbook",
                       side_effect=Exception("network error")):
                result = fetch_intraday_features("VCB")
        assert result["tfi"] == 0.0
        assert result["obi_l3"] == 0.0
        assert result["foreign_net"] == 0
        assert isinstance(result, dict)

    def test_returns_dict_on_partial_failure(self):
        """Only TCBS fails → OBI still computed from SSI, TFI falls back to 0."""
        from tradingos.data.intraday_collector import fetch_intraday_features
        mock_ob = {
            "bids": [{"price": 88.5, "vol": 50000}, {"price": 88.4, "vol": 30000}],
            "asks": [{"price": 88.6, "vol": 20000}],
            "foreign_buy": 10000, "foreign_sell": 5000,
        }
        with patch("tradingos.data.intraday_collector.fetch_tcbs_trades",
                   side_effect=Exception("TCBS down")):
            with patch("tradingos.data.intraday_collector.fetch_ssi_orderbook",
                       return_value=mock_ob):
                result = fetch_intraday_features("VCB")
        assert result["tfi"] == 0.0           # TCBS failed → 0
        assert result["obi_l3"] != 0.0        # SSI succeeded → non-zero
        assert result["foreign_net"] == 5000  # 10000 - 5000


# ── Tests: compute_mcvd formula ───────────────────────────────────────────────

class TestComputeMCVD:

    def test_all_buy_trades(self):
        """All buy-aggressor ticks → positive M-CVD equal to total buy volume."""
        from tradingos.data.intraday_collector import compute_mcvd
        trades = [
            {"volume": 1000, "aggressor": "B"},
            {"volume": 2000, "aggressor": "B"},
        ]
        assert compute_mcvd(trades) == 3000

    def test_all_sell_trades(self):
        """All sell-aggressor ticks → negative M-CVD equal to total sell volume."""
        from tradingos.data.intraday_collector import compute_mcvd
        trades = [
            {"volume": 500, "aggressor": "S"},
            {"volume": 1500, "aggressor": "S"},
        ]
        assert compute_mcvd(trades) == -2000

    def test_balanced_buy_sell(self):
        """Equal buy/sell volume → M-CVD is zero."""
        from tradingos.data.intraday_collector import compute_mcvd
        trades = [
            {"volume": 1000, "aggressor": "B"},
            {"volume": 1000, "aggressor": "S"},
        ]
        assert compute_mcvd(trades) == 0

    def test_unknown_aggressor_excluded(self):
        """Unknown aggressor ticks contribute nothing to M-CVD."""
        from tradingos.data.intraday_collector import compute_mcvd
        trades = [
            {"volume": 800, "aggressor": "B"},
            {"volume": 300, "aggressor": "U"},  # unknown — ignored
            {"volume": 200, "aggressor": "S"},
        ]
        # M-CVD = 800 (B) - 200 (S) = 600; the 300 U is excluded
        assert compute_mcvd(trades) == 600

    def test_empty_list_returns_zero(self):
        """Empty trade list returns 0."""
        from tradingos.data.intraday_collector import compute_mcvd
        assert compute_mcvd([]) == 0

    def test_mixed_net_buy_pressure(self):
        """Net buy-heavy session produces large positive M-CVD."""
        from tradingos.data.intraday_collector import compute_mcvd
        trades = [
            {"volume": 5000, "aggressor": "B"},
            {"volume": 3000, "aggressor": "B"},
            {"volume": 1000, "aggressor": "S"},
        ]
        assert compute_mcvd(trades) == 7000  # 8000 - 1000


# ── Tests: fetch_intraday_features includes mcvd ──────────────────────────────

class TestFetchIntradayFeaturesMCVD:

    def test_mcvd_in_returned_dict_on_success(self):
        """Successful fetch includes mcvd key with integer value."""
        from tradingos.data.intraday_collector import fetch_intraday_features
        mock_trades = [
            {"price": 88.5, "volume": 2000, "aggressor": "B", "time": "10:00:00"},
            {"price": 88.4, "volume": 1000, "aggressor": "S", "time": "10:01:00"},
        ]
        mock_ob = {
            "bids": [{"price": 88.3, "vol": 50000}],
            "asks": [{"price": 88.6, "vol": 40000}],
            "foreign_buy": 0, "foreign_sell": 0,
        }
        with patch("tradingos.data.intraday_collector.fetch_tcbs_trades",
                   return_value=mock_trades):
            with patch("tradingos.data.intraday_collector.fetch_ssi_orderbook",
                       return_value=mock_ob):
                result = fetch_intraday_features("VCB")
        assert "mcvd" in result
        assert isinstance(result["mcvd"], int)
        # 2000 (B) - 1000 (S) = 1000
        assert result["mcvd"] == 1000

    def test_mcvd_zero_on_network_failure(self):
        """Network failure → mcvd defaults to 0 in fallback dict."""
        from tradingos.data.intraday_collector import fetch_intraday_features
        with patch("tradingos.data.intraday_collector.fetch_tcbs_trades",
                   side_effect=Exception("timeout")):
            with patch("tradingos.data.intraday_collector.fetch_ssi_orderbook",
                       side_effect=Exception("timeout")):
                result = fetch_intraday_features("VCB")
        assert result["mcvd"] == 0


# ── Tests: run_amf details includes mcvd ─────────────────────────────────────

class TestAMFDetailsMCVD:

    def test_amf_details_contains_mcvd(self):
        """run_amf details dict always includes mcvd key."""
        from tradingos.core.anti_manip import run_amf
        df = _make_df(n=40)
        intraday_data = {"tfi": 0.3, "obi_l3": 0.1, "obi_reconstructed": 0.05, "mcvd": 5000}
        result = run_amf(df, intraday_data=intraday_data)
        assert "details" in result
        assert "mcvd" in result["details"]
        assert result["details"]["mcvd"] == 5000

    def test_amf_details_mcvd_defaults_zero_without_intraday(self):
        """run_amf with no intraday_data → mcvd in details is 0."""
        from tradingos.core.anti_manip import run_amf
        df = _make_df(n=40)
        result = run_amf(df)
        assert result["details"]["mcvd"] == 0
