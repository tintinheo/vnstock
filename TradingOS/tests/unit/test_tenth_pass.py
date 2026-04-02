from __future__ import annotations

import inspect
import json

import pandas as pd


def _make_macro_inputs():
    dates = pd.bdate_range("2025-01-02", periods=40)
    usdvnd = pd.DataFrame({
        "date": dates,
        "close": [25000 - i * 5 for i in range(len(dates))],
    })
    bond = pd.DataFrame({
        "date": dates,
        "yield": [3.0 - i * 0.01 for i in range(len(dates))],
    })
    return dates, usdvnd, bond


class TestMacroSeries:
    def test_build_macro_regime_series_returns_one_row_per_date(self):
        from tradingos.core.macro import build_macro_regime_series

        dates, usdvnd, bond = _make_macro_inputs()
        series = build_macro_regime_series(dates, usdvnd_df=usdvnd, bond_yield_df=bond)
        assert len(series) == len(pd.Series(dates).drop_duplicates())
        assert {"date", "macro_score", "macro_regime"}.issubset(series.columns)

    def test_build_macro_regime_series_has_non_empty_regimes(self):
        from tradingos.core.macro import build_macro_regime_series

        dates, usdvnd, bond = _make_macro_inputs()
        series = build_macro_regime_series(dates, usdvnd_df=usdvnd, bond_yield_df=bond)
        assert series["macro_regime"].isin(["ACCOMMODATIVE", "NEUTRAL", "RESTRICTIVE"]).all()


class TestSectorFlowLookup:
    def test_infer_sector_name_from_builtin_map(self):
        from tradingos.engines.money_flow_service import infer_sector_name

        assert infer_sector_name("VCB") == "Ngân hàng"
        assert infer_sector_name("SSI") == "Chứng khoán"

    def test_sector_flow_lookup_returns_flow_status(self):
        from tradingos.engines.money_flow_service import sector_flow_lookup

        rotation = {
            "rankings": [
                {"sector": "Ngân hàng", "flow_status": "INFLOW"},
                {"sector": "Chứng khoán", "flow_status": "OUTFLOW"},
            ]
        }
        assert sector_flow_lookup(rotation, "VCB") == "INFLOW"
        assert sector_flow_lookup(rotation, "SSI") == "OUTFLOW"

    def test_load_sector_groups_uses_json_mapping(self, tmp_path, monkeypatch):
        from tradingos.engines import money_flow_service as mfs

        mapping_path = tmp_path / "sector_map.json"
        mapping_path.write_text(json.dumps({
            "ACB": {"industry": "Ngân hàng", "sub_sector": "Ngân hàng"},
            "FTS": {"industry": "Dịch vụ tài chính", "sub_sector": "Chứng khoán"},
        }, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(mfs, "_mapping_file_path", lambda: mapping_path)

        groups = mfs._load_sector_groups()
        assert "ACB" in groups["Ngân hàng"]
        assert "FTS" in groups["Chứng khoán"]

    def test_infer_sector_name_prefers_json_mapping_before_cache(self, tmp_path, monkeypatch):
        from tradingos.engines import money_flow_service as mfs

        mapping_path = tmp_path / "sector_map.json"
        mapping_path.write_text(json.dumps({
            "FOX": {"industry": "Công nghệ", "sub_sector": "Phần mềm"},
        }, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(mfs, "_mapping_file_path", lambda: mapping_path)
        monkeypatch.setattr(mfs.cache, "get_sector", lambda ticker: "HOSE")

        assert mfs.infer_sector_name("FOX") == "Công nghệ"


class TestUISourceWiring:
    def test_profiler_table_shows_overlay_fields(self):
        import tradingos.ui.pages.profiler as profiler

        src = inspect.getsource(profiler._profile_to_row)
        assert '"Macro"' in src
        assert '"BCTC Risk"' in src
        assert '"FundScore"' in src
        assert '"Sàn"' in src

    def test_profiler_detail_has_dedicated_overlay_tab(self):
        import tradingos.ui.pages.profiler as profiler

        src = inspect.getsource(profiler._render_detail)
        assert '"🧭 Overlay"' in src
        assert 'Next earnings date' in src
        assert 'Debt / Equity' in src

    def test_scanner_table_shows_macro_fields(self):
        import tradingos.ui.pages.scanner as scanner

        src = inspect.getsource(scanner.render)
        assert '"Macro"' in src
        assert '"MacroScore"' in src
        assert '"Sector Flow"' in src
        assert '"BCTC Risk"' in src
        assert '"FundScore"' in src

    def test_scanner_ui_exposes_exchange_selector(self):
        import tradingos.ui.pages.scanner as scanner

        src = inspect.getsource(scanner.render)
        assert 'selectbox("Sàn", ["HOSE", "HNX", "UPCOM", "ALL"]' in src
        assert 'exchange=exchange' in src

    def test_signal_card_shows_overlay_details(self):
        import tradingos.ui.components.signal_card as signal_card

        src = inspect.getsource(signal_card.render_signal_card)
        assert 'Sector Flow' in src
        assert 'BCTC Risk' in src
        assert 'Fundamental' in src


class TestBacktestServiceMacroWiring:
    def test_backtest_service_builds_macro_series(self):
        import tradingos.engines.backtest_service as svc

        src = inspect.getsource(svc.BacktestService.run)
        assert 'build_macro_regime_series' in src
        assert 'fetch_usdvnd' in src
        assert 'fetch_vn10y_bond_yield' in src

    def test_compare_modes_still_filters_overlay_signals(self):
        import tradingos.core.backtest as backtest

        src = inspect.getsource(backtest.compare_modes)
        assert '_apply_overlay_signal_filters' in src

    def test_backtest_service_merges_macro_columns_before_compare(self, monkeypatch):
        from tradingos.engines.backtest_service import BacktestService
        from tradingos.data.schemas import BacktestRequest

        df = pd.DataFrame({
            "date": pd.bdate_range("2024-01-02", periods=80),
            "open": [10.0] * 80,
            "high": [10.2] * 80,
            "low": [9.8] * 80,
            "close": [10.0 + i * 0.01 for i in range(80)],
            "volume": [1_000_000.0] * 80,
        })

        monkeypatch.setattr("tradingos.engines.backtest_service.fetch_ohlcv", lambda ticker, days=520: df.copy())
        monkeypatch.setattr("tradingos.engines.backtest_service.fetch_usdvnd", lambda days=110: pd.DataFrame({
            "date": pd.bdate_range("2023-10-01", periods=110),
            "close": [25000.0] * 110,
        }))
        monkeypatch.setattr("tradingos.engines.backtest_service.fetch_vn10y_bond_yield", lambda days=110: pd.DataFrame({
            "date": pd.bdate_range("2023-10-01", periods=110),
            "yield": [3.0] * 110,
        }))

        captured = {}

        def fake_compare_modes(df, ticker="N/A", sl_pct=0.06, tp1_pct=0.08, tp2_pct=0.15):
            captured["columns"] = list(df.columns)
            return {}

        monkeypatch.setattr("tradingos.engines.backtest_service.compare_modes", fake_compare_modes)

        svc = BacktestService()
        svc.run(BacktestRequest(ticker="VCB", start_date="2024-01-02", end_date="2024-06-30", sl_pct=0.06))
        assert "macro_regime" in captured["columns"]
        assert "macro_score" in captured["columns"]


class TestScannerSchemaWiring:
    def test_scan_result_item_has_overlay_fields(self):
        from tradingos.data.schemas import ScanResultItem

        fields = ScanResultItem.model_fields
        assert "sector_flow" in fields
        assert "earnings_risk" in fields
        assert "fundamental_score" in fields

    def test_scan_request_has_exchange_field(self):
        from tradingos.data.schemas import ScanRequest

        assert "exchange" in ScanRequest.model_fields


class TestScannerServiceExchangeWiring:
    def test_scanner_service_uses_request_exchange_for_universe(self):
        from tradingos.engines.scanner_service import ScannerService

        src = inspect.getsource(ScannerService.scan)
        assert 'exchange = str(request.exchange or "HOSE").upper()' in src
        assert 'if exchange == "ALL":' in src
        assert 'fetch_universe("UPCOM")' in src
