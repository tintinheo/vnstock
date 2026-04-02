"""
Sixth-pass regression tests: Scanner ↔ Profiler parity fixes.

These tests guard against the 8 divergences between scanner_service._score_ticker
and profiler_service.run that caused the same ticker to produce WATCH in Scanner
but EXIT in Profiler.

Issue mapping:
  D1 — scanner fetches days=260 (was 120 — SMA200 was always NaN)
  D2 — scanner uses compute_whale_net_from_pt_deals, not proxy_whale_net_from_daily
  D3 — scanner merges real fol_net via fetch_foreign_flow (not missing)
  D4 — scanner passes real pt_deals_df to compute_smart_money_score (was None)
  D5 — scanner computes distribution_warning via detect_whale_distribution (was "NONE")
  D6 — scanner passes amd_phase to detect_stealth_accumulation (was missing)
  D7 — scanner passes sector_flow to compute_mfpm (was missing)
  D8 — scanner uses sms_result data_source tag for mcvd_detail (was hardcoded)
  D9 — default timeout raised to 60s in _DEFAULT_TICKER_TIMEOUT and strategy.yaml
"""
from __future__ import annotations

import inspect

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# D1 — Scanner fetches 260 days of OHLCV, not 120
# ─────────────────────────────────────────────────────────────────────────────

class TestD1OHLCVWindow:
    def test_score_ticker_fetches_260_days(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        assert "days=260" in src, (
            "_score_ticker must fetch 260 days (not 120) so SMA200/ATR/AMD are reliable"
        )
        assert "days=120" not in src, (
            "old days=120 fetch must be removed from _score_ticker"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D2 — Scanner uses real PT deal flow, not proxy OHLCV
# ─────────────────────────────────────────────────────────────────────────────

class TestD2RealPTFlow:
    def test_score_ticker_uses_compute_whale_net_from_pt_deals(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        assert "compute_whale_net_from_pt_deals" in src, (
            "_score_ticker must use compute_whale_net_from_pt_deals (real PT data), "
            "not proxy_whale_net_from_daily"
        )
        # Check for the function *call*, not just the word (which may appear in comments)
        assert "proxy_whale_net_from_daily(" not in src, (
            "proxy_whale_net_from_daily() must not be called in _score_ticker; "
            "use real PT deals instead"
        )

    def test_proxy_whale_not_imported_in_scanner(self):
        import tradingos.engines.scanner_service as svc
        src = inspect.getsource(svc)
        # The import line must not bring in proxy_whale_net_from_daily
        import_section = "\n".join(
            line for line in src.splitlines() if line.startswith("from") or line.startswith("import")
        )
        assert "proxy_whale_net_from_daily" not in import_section, (
            "proxy_whale_net_from_daily must no longer be imported in scanner_service"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D3 — Scanner calls fetch_foreign_flow
# ─────────────────────────────────────────────────────────────────────────────

class TestD3ForeignFlowFetch:
    def test_score_ticker_calls_fetch_foreign_flow(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        assert "fetch_foreign_flow" in src, (
            "_score_ticker must call fetch_foreign_flow to get real fol_net data"
        )

    def test_fol_net_merged_into_flow_df(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        assert "fol_net" in src, (
            "_score_ticker must merge fol_net column into flow_df"
        )

    def test_fetch_foreign_flow_imported(self):
        import tradingos.engines.scanner_service as svc
        src = inspect.getsource(svc)
        import_section = "\n".join(
            line for line in src.splitlines() if line.startswith("from") or line.startswith("import")
        )
        assert "fetch_foreign_flow" in import_section, (
            "fetch_foreign_flow must be imported in scanner_service"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D4 — Scanner passes real pt_deals_df (not None) to compute_smart_money_score
# ─────────────────────────────────────────────────────────────────────────────

class TestD4RealPTDeals:
    def test_fetch_put_through_deals_called(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        assert "fetch_put_through_deals" in src, (
            "_score_ticker must call fetch_put_through_deals to get real PT data"
        )

    def test_pt_deals_df_not_none_in_sms_call(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        assert "pt_deals_df=None" not in src, (
            "compute_smart_money_score must receive real pt_deals_df, not None"
        )
        assert "pt_deals_df=pt_deals_df" in src, (
            "compute_smart_money_score must be called with pt_deals_df=pt_deals_df"
        )

    def test_fetch_put_through_deals_imported(self):
        import tradingos.engines.scanner_service as svc
        src = inspect.getsource(svc)
        import_section = "\n".join(
            line for line in src.splitlines() if line.startswith("from") or line.startswith("import")
        )
        assert "fetch_put_through_deals" in import_section, (
            "fetch_put_through_deals must be imported in scanner_service"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D5 — distribution_warning computed, not hardcoded "NONE"
# ─────────────────────────────────────────────────────────────────────────────

class TestD5DistributionWarning:
    def test_detect_whale_distribution_called(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        assert "detect_whale_distribution" in src, (
            '_score_ticker must call detect_whale_distribution() to compute dist_warning; '
            'hardcoded "NONE" means WHALE_DISTRIBUTING signals are silently ignored'
        )

    def test_distribution_warning_not_hardcoded(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        assert '"distribution_warning": "NONE"' not in src and \
               "'distribution_warning': 'NONE'" not in src, (
            '"distribution_warning": "NONE" must be replaced with the result of '
            'detect_whale_distribution()'
        )

    def test_detect_whale_distribution_imported(self):
        # Verify that detect_whale_distribution is importable from the scanner module's
        # namespace (handles both single-line and multi-line from..import blocks).
        from tradingos.engines import scanner_service
        assert hasattr(scanner_service, "detect_whale_distribution") or \
               "detect_whale_distribution" in inspect.getsource(scanner_service), (
            "detect_whale_distribution must be imported in scanner_service"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D6 — detect_stealth_accumulation receives amd_phase
# ─────────────────────────────────────────────────────────────────────────────

class TestD6StealthAMDPhase:
    def test_stealth_call_passes_amd_phase(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        # The call must include amd_phase keyword arg
        assert "detect_stealth_accumulation(df, flow_df, amd_phase=amd)" in src, (
            "detect_stealth_accumulation must receive amd_phase=amd; "
            "without it, thresholds ignore the market phase (matches Profiler)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D7 — sector_flow passed to compute_mfpm
# ─────────────────────────────────────────────────────────────────────────────

class TestD7SectorFlow:
    def test_sector_flow_extracted_from_sms(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        assert 'sms_result.get("sector_flow"' in src, (
            '_score_ticker must extract sector_flow from sms_result '
            '(matches Profiler: sector_flow = sms_result.get("sector_flow", "NEUTRAL"))'
        )

    def test_sector_flow_passed_to_compute_mfpm(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        assert "sector_flow=sector_flow" in src, (
            "compute_mfpm must receive sector_flow=sector_flow in _score_ticker"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D8 — mcvd_detail data_source uses real tag, not hardcoded "PROXY_OHLCV"
# ─────────────────────────────────────────────────────────────────────────────

class TestD8DataSourceTag:
    def test_mcvd_data_source_from_sms_result(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        assert 'sms_result.get("data_source"' in src, (
            'mcvd_detail data_source must use sms_result.get("data_source", "PROXY_OHLCV"), '
            'not the hardcoded string "PROXY_OHLCV" — when PT data is available the '
            'tag is "PARTIAL_PROXY" and the confidence penalty should be lower'
        )

    def test_mcvd_data_not_hardcoded_proxy_ohlcv(self):
        from tradingos.engines.scanner_service import ScannerService
        src = inspect.getsource(ScannerService._score_ticker)
        # Should not contain the hardcoded pattern from the old code
        assert '"data_source": "PROXY_OHLCV"' not in src and \
               "'data_source': 'PROXY_OHLCV'" not in src, (
            'hardcoded "data_source": "PROXY_OHLCV" must be replaced '
            'with sms_result.get("data_source", "PROXY_OHLCV")'
        )


# ─────────────────────────────────────────────────────────────────────────────
# D9 — Timeout updated to 60s in constant and strategy.yaml
# ─────────────────────────────────────────────────────────────────────────────

class TestD9TimeoutUpdated:
    def test_default_timeout_is_60(self):
        import tradingos.engines.scanner_service as svc
        assert svc._DEFAULT_TICKER_TIMEOUT == 60, (
            "_DEFAULT_TICKER_TIMEOUT must be 60 (was 25); 3 API calls per ticker now"
        )

    def test_strategy_yaml_has_scanner_section(self):
        from tradingos.utils.config import cfg
        val = cfg.strategy("scanner", "per_ticker_timeout_s", default=None)
        assert val is not None, (
            "strategy.yaml must define scanner.per_ticker_timeout_s"
        )
        assert int(val) >= 60, (
            f"scanner.per_ticker_timeout_s must be >= 60, got {val}"
        )
