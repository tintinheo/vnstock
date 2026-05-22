"""UI/UX regression tests for Audit, Scanner, and Performance pages."""
from __future__ import annotations

import inspect

import math
import pandas as pd


class TestAuditReadingGuide:
    def test_audit_has_vn_behavior_reading_guide(self):
        import tradingos.ui.pages.audit as audit_ui

        src = inspect.getsource(audit_ui)
        assert "Cách đọc đúng theo hành vi thị trường Việt Nam" in src
        assert "MFPM + SMS/M-CVD + AMF + T+ Verdict" in src

    def test_audit_has_action_tplus_mapping_affordance(self):
        import tradingos.ui.pages.audit as audit_ui

        src = inspect.getsource(audit_ui)
        assert "Mapping chuẩn giữa Action và T+ Verdict" in src
        assert "A×T+ Ý nghĩa" in src
        assert "T+ Exit" in src

    def test_audit_uses_session_state_and_fixed_labels(self):
        import tradingos.ui.pages.audit as audit_ui

        src = inspect.getsource(audit_ui)
        assert "audit_results" in src
        assert "audit_has_run" in src
        assert "Sự kiện đang hiển thị" in src
        assert "Mã cổ phiếu trong view" in src
        assert "Loại khuyến nghị trong view" in src


class TestAuditTimestampFormatting:
    def test_timestamp_formatter_accepts_datetime_series(self):
        from tradingos.ui.pages.audit import _format_timestamp_display

        series = pd.Series([pd.Timestamp("2026-04-24 09:15:00")])
        result = _format_timestamp_display(series)
        assert result.iloc[0] == "2026-04-24 09:15"

    def test_timestamp_formatter_accepts_string_series(self):
        from tradingos.ui.pages.audit import _format_timestamp_display

        series = pd.Series(["2026-04-24 09:15:00"])
        result = _format_timestamp_display(series)
        assert result.iloc[0] == "2026-04-24 09:15"

    def test_timestamp_formatter_preserves_unparseable_text(self):
        from tradingos.ui.pages.audit import _format_timestamp_display

        series = pd.Series(["not-a-date", None])
        result = _format_timestamp_display(series)
        assert result.iloc[0] == "not-a-date"
        assert result.iloc[1] == ""


class TestScannerFilteredSummary:
    def test_scanner_has_reading_guide_and_view_metrics(self):
        import tradingos.ui.pages.scanner as scanner_ui

        src = inspect.getsource(scanner_ui.render)
        assert "Cách đọc kết quả Scanner" in src
        assert "Mã đang hiển thị" in src
        assert "Cơ hội buy/watch" in src

    def test_scanner_has_action_tplus_mapping_columns(self):
        import tradingos.ui.pages.scanner as scanner_ui

        src = inspect.getsource(scanner_ui.render)
        assert "Mapping chuẩn giữa Action và T+ Verdict" in src
        assert "A×T+ Ý nghĩa" in src
        assert "T+ Exit" in src
        assert "apply(_row_tint, axis=1)" in src


class TestTplusExplainer:
    def test_buy_but_wait_for_confirmation_explanation(self):
        from tradingos.ui.components.tplus_explainer import build_action_tplus_explanation

        text = build_action_tplus_explanation("BUY", "CHO_XAC_NHAN")
        assert "chua den diem kich hoat dep" in text.lower()

    def test_tplus_exit_plan_mentions_targets_and_stop(self):
        from tradingos.ui.components.tplus_explainer import build_tplus_exit_plan

        text = build_tplus_exit_plan("MUA_NGAY", 95, 108, 114, 100, 102)
        assert "SL 95.0" in text
        assert "T+2.5 108.0" in text
        assert "T+5 114.0" in text

    def test_nan_inputs_do_not_crash_explainer(self):
        from tradingos.ui.components.tplus_explainer import build_action_tplus_explanation

        text = build_action_tplus_explanation("BUY", math.nan)
        assert "quan sat" in text.lower() or "tin hieu" in text.lower()

    def test_nan_verdict_does_not_crash_exit_plan(self):
        from tradingos.ui.components.tplus_explainer import build_tplus_exit_plan

        text = build_tplus_exit_plan(math.nan, 95, 108, 114, 100, 102)
        assert "SL 95.0" in text


class TestPerformanceFilteredSummary:
    def test_performance_has_reading_guide_and_view_metrics(self):
        import tradingos.ui.pages.performance as perf_ui

        src = inspect.getsource(perf_ui.render)
        assert "Cách đọc trang Hiệu suất" in src
        assert "Lệnh đang hiển thị" in src
        assert "Win rate trong view" in src

    def test_performance_calibration_mentions_filtered_scope(self):
        import tradingos.ui.pages.performance as perf_ui

        src = inspect.getsource(perf_ui._render_confidence_calibration)
        assert "Đang hiển thị" in src
        assert "calibration" in src.lower()

    def test_performance_calibration_filters_before_plot(self):
        import tradingos.ui.pages.performance as perf_ui

        src = inspect.getsource(perf_ui._render_confidence_calibration)
        assert src.index("calib_df = filter_dataframe") < src.index("fig = go.Figure")
        assert "Không còn nhóm confidence nào sau khi lọc bảng calibration." in src


class TestSharedFilterCopy:
    def test_aggrid_filter_caption_uses_vietnamese_accents(self):
        import tradingos.ui.components.dataframe_filter as filter_ui

        src = inspect.getsource(filter_ui)
        assert "Lọc ngay trên từng cột" in src


class TestProfilerTplusConsistency:
    def test_profiler_has_action_tplus_summary_and_row_tint(self):
        import tradingos.ui.pages.profiler as profiler_ui

        src = inspect.getsource(profiler_ui)
        assert "Mapping chuẩn giữa Action và T+ Verdict" in src
        assert "A×T+ Ý nghĩa" in src
        assert "T+ Exit" in src
        assert "apply(_row_tint, axis=1)" in src

    def test_audit_uses_verdict_row_tint(self):
        import tradingos.ui.pages.audit as audit_ui

        src = inspect.getsource(audit_ui)
        assert "apply(_row_tint, axis=1)" in src