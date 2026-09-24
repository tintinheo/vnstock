"""tests/unit/test_fourteenth_pass.py

Fourteenth pass — Intraday CVD engine, Order Book Imbalance engine,
and new CVD/OBI schema fields on TickerProfile + ScanResultItem.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tradingos.core.intraday_cvd import compute_intraday_cvd
from tradingos.core.orderbook import compute_order_book_imbalance
from tradingos.data.schemas import ScanResultItem, TickerProfile


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ohlcv_df(n: int = 20, rising: bool = True) -> pd.DataFrame:
    """Minimal OHLCV DataFrame without bu/sd — proxy path."""
    close = np.linspace(10_000, 11_000 if rising else 9_000, n)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    return pd.DataFrame(
        {
            "open":   open_,
            "high":   close + 50,
            "low":    close - 50,
            "close":  close,
            "volume": np.full(n, 100_000),
        }
    )


def _realflow_df(n: int = 20, buy_heavy: bool = True) -> pd.DataFrame:
    """OHLCV + bu/sd DataFrame — real-flow path."""
    df = _ohlcv_df(n, rising=buy_heavy)
    if buy_heavy:
        df["bu"] = 70_000
        df["sd"] = 30_000
    else:
        df["bu"] = 30_000
        df["sd"] = 70_000
    return df


def _bidask_df(bid_vol: float = 500_000, ask_vol: float = 200_000) -> pd.DataFrame:
    """Simple bid/ask DataFrame with bid_vol / ask_vol columns."""
    return pd.DataFrame(
        {
            "bid_vol":   [bid_vol / 5] * 5,
            "ask_vol":   [ask_vol / 5] * 5,
            "bid_price": [10_000, 9_900, 9_800, 9_700, 9_600],
            "ask_price": [10_100, 10_200, 10_300, 10_400, 10_500],
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# TestIntradayCVD
# ─────────────────────────────────────────────────────────────────────────────

class TestIntradayCVD:

    def test_real_flow_uses_bu_sd(self):
        result = compute_intraday_cvd(_realflow_df(buy_heavy=True))
        assert result["data_quality"] == "REAL_FLOW"

    def test_ohlcv_proxy_fallback(self):
        result = compute_intraday_cvd(_ohlcv_df(rising=True))
        assert result["data_quality"] == "OHLCV_PROXY"

    def test_cvd_score_in_range(self):
        for df in [_ohlcv_df(), _realflow_df(), _realflow_df(buy_heavy=False)]:
            result = compute_intraday_cvd(df)
            assert 0.0 <= result["cvd_score"] <= 10.0, f"score out of range: {result['cvd_score']}"

    def test_buying_signal(self):
        result = compute_intraday_cvd(_realflow_df(buy_heavy=True))
        assert result["cvd_signal"] == "BUYING"
        assert result["cvd_raw"] > 0

    def test_distributing_signal(self):
        result = compute_intraday_cvd(_realflow_df(buy_heavy=False))
        assert result["cvd_signal"] == "DISTRIBUTING"
        assert result["cvd_raw"] < 0

    def test_divergence_bullish(self):
        # Price falls, but bu >> sd → bullish divergence
        df = _ohlcv_df(rising=False)  # price falling
        df["bu"] = 80_000            # strong buying hidden
        df["sd"] = 20_000
        result = compute_intraday_cvd(df)
        assert result["cvd_divergence"] == "BULLISH_DIV"

    def test_divergence_bearish(self):
        # Price rises, but sd >> bu → bearish divergence
        df = _ohlcv_df(rising=True)  # price rising
        df["bu"] = 20_000            # hidden selling
        df["sd"] = 80_000
        result = compute_intraday_cvd(df)
        assert result["cvd_divergence"] == "BEARISH_DIV"

    def test_empty_df_returns_defaults(self):
        result = compute_intraday_cvd(pd.DataFrame())
        assert result["cvd_signal"] == "NEUTRAL"
        assert result["data_quality"] == "NONE"
        assert result["cvd_score"] == 5.0

    def test_none_returns_defaults(self):
        result = compute_intraday_cvd(None)  # type: ignore[arg-type]
        assert result["cvd_signal"] == "NEUTRAL"

    def test_buying_pressure_pct_range(self):
        result = compute_intraday_cvd(_realflow_df())
        assert 0.0 <= result["buying_pressure_pct"] <= 100.0

    def test_cvd_score_neutral_balanced(self):
        """Perfectly balanced bu=sd should yield score near 5."""
        df = _realflow_df()
        df["bu"] = 50_000
        df["sd"] = 50_000
        result = compute_intraday_cvd(df)
        assert abs(result["cvd_score"] - 5.0) < 0.5

    def test_required_keys_present(self):
        result = compute_intraday_cvd(_ohlcv_df())
        expected = {"cvd_raw", "cvd_score", "cvd_signal", "cvd_divergence",
                    "buying_pressure_pct", "data_quality", "cvd_trend"}
        assert expected == set(result.keys())


# ─────────────────────────────────────────────────────────────────────────────
# TestOrderBookImbalance
# ─────────────────────────────────────────────────────────────────────────────

class TestOrderBookImbalance:

    def test_buying_pressure(self):
        result = compute_order_book_imbalance(_bidask_df(bid_vol=700_000, ask_vol=300_000))
        assert result["obi_signal"] == "BUYING_PRESSURE"
        assert result["obi_pct"] > 20

    def test_selling_pressure(self):
        result = compute_order_book_imbalance(_bidask_df(bid_vol=300_000, ask_vol=700_000))
        assert result["obi_signal"] == "SELLING_PRESSURE"
        assert result["obi_pct"] < -20

    def test_balanced(self):
        result = compute_order_book_imbalance(_bidask_df(bid_vol=500_000, ask_vol=500_000))
        assert result["obi_signal"] == "BALANCED"
        assert abs(result["obi_pct"]) < 1.0

    def test_obi_formula(self):
        """OBI = (bid - ask) / (bid + ask) * 100."""
        bid, ask = 800_000.0, 200_000.0
        expected_obi = (bid - ask) / (bid + ask) * 100
        result = compute_order_book_imbalance(_bidask_df(bid_vol=bid, ask_vol=ask))
        assert abs(result["obi_pct"] - expected_obi) < 0.1

    def test_empty_df_returns_defaults(self):
        result = compute_order_book_imbalance(pd.DataFrame())
        assert result["obi_pct"] == 0.0
        assert result["obi_signal"] == "BALANCED"

    def test_none_returns_defaults(self):
        result = compute_order_book_imbalance(None)  # type: ignore[arg-type]
        assert result["obi_signal"] == "BALANCED"

    def test_required_keys_present(self):
        result = compute_order_book_imbalance(_bidask_df())
        assert {"obi_pct", "obi_signal", "spread_pct", "bid_ask_depth"} == set(result.keys())

    def test_depth_dict_structure(self):
        result = compute_order_book_imbalance(_bidask_df(bid_vol=600_000, ask_vol=400_000))
        depth = result["bid_ask_depth"]
        assert "total_bid" in depth and "total_ask" in depth
        assert depth["total_bid"] == pytest.approx(600_000, rel=1e-3)
        assert depth["total_ask"] == pytest.approx(400_000, rel=1e-3)


# ─────────────────────────────────────────────────────────────────────────────
# TestNewSchemaFields
# ─────────────────────────────────────────────────────────────────────────────

def _minimal_ticker_profile() -> dict:
    """Minimal required fields to construct a TickerProfile."""
    return {
        "ticker": "HPG",
        "action": "WATCH",
        "confidence": "LOW",
        "signal_mode": "MODE_A",
        "close": 25_000.0,
        "entry_price": 25_000.0,
        "stop_loss": 23_000.0,
        "tp1": 28_000.0,
        "tp2": 31_000.0,
        "rr_ratio": 1.5,
        "sl_pct": 8.0,
        "atr14": 500.0,
        "rsi14": 50.0,
        "sma20": 24_500.0,
        "sma50": 24_000.0,
        "sma200": 22_000.0,
        "ema20": 24_500.0,
        "obv": 1_000_000.0,
        "volume": 1_000_000,
        "avg_volume_20d": 900_000,
        "vqs": 70.0,
        "mfpm_score": 50,
        "mc_win_prob": 0.55,
        "mode_w_score": 0,
        "mode_a_score": 0,
        "mode_b_score": 0,
        "sms_raw": 50,
        "sms_label": "RETAIL_DRIVEN",
        "amd_phase": "RANGING",
        "hmm_state": "BULL",
        "amf_decision": "PASS",
        "best_pattern": "NONE",
        "stealth_accum": False,
        "distribution_warning": "NONE",
        "mcvd_5d": 0.0,
        "mcvd_20d": 0.0,
        "mcvd_trend": "FLAT",
        "exchange": "HOSE",
        "sizing_pct": 0.05,
        "sizing_shares": 1000,
        "advisory_text": "",
        "horizons": [],
    }


class TestNewSchemaFields:

    def test_ticker_profile_has_8_cvd_fields(self):
        p = TickerProfile(**_minimal_ticker_profile())
        # All 8 new CVD/OBI fields should be present with correct defaults
        assert p.cvd_signal == "NEUTRAL"
        assert p.cvd_divergence == "NONE"
        assert p.cvd_buying_pressure_pct == 50.0
        assert p.cvd_score == 5.0
        assert p.cvd_data_quality == "NONE"
        assert p.obi_pct == 0.0
        assert p.obi_signal == "BALANCED"
        assert p.data_source_intraday == "NONE"

    def test_ticker_profile_cvd_fields_assignable(self):
        data = _minimal_ticker_profile()
        data.update(
            cvd_signal="BUYING",
            cvd_divergence="BULLISH_DIV",
            cvd_buying_pressure_pct=72.5,
            cvd_score=7.5,
            cvd_data_quality="REAL_FLOW",
            obi_pct=34.2,
            obi_signal="BUYING_PRESSURE",
            data_source_intraday="FIINQUANT",
        )
        p = TickerProfile(**data)
        assert p.cvd_signal == "BUYING"
        assert p.cvd_data_quality == "REAL_FLOW"
        assert p.data_source_intraday == "FIINQUANT"
        assert p.obi_pct == pytest.approx(34.2)

    def test_scan_result_item_has_cvd_signal(self):
        item = ScanResultItem(
            ticker="VNM",
            action="WATCH",
            confidence="LOW",
            mfpm_score=50,
            mode_w_score=0,
            sms_raw=50,
            signal_mode="MODE_A",
            close=80_000.0,
            entry=80_000.0,
            sl=74_000.0,
            tp1=90_000.0,
            rr=1.5,
            amf_decision="PASS",
            best_pattern="NONE",
            hmm_state="BULL",
        )
        assert item.cvd_signal == "NEUTRAL"

    def test_scan_result_item_cvd_signal_assignable(self):
        item = ScanResultItem(
            ticker="TCB",
            action="BUY",
            confidence="MEDIUM",
            mfpm_score=65,
            mode_w_score=0,
            sms_raw=65,
            signal_mode="MODE_A",
            close=30_000.0,
            entry=30_000.0,
            sl=27_000.0,
            tp1=35_000.0,
            rr=1.7,
            amf_decision="PASS",
            best_pattern="NONE",
            hmm_state="BULL",
            cvd_signal="BUYING",
        )
        assert item.cvd_signal == "BUYING"
