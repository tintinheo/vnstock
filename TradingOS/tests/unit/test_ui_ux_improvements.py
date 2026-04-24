"""UI/UX regression tests for Audit, Scanner, and Performance pages."""
from __future__ import annotations

import inspect


class TestAuditReadingGuide:
    def test_audit_has_vn_behavior_reading_guide(self):
        import tradingos.ui.pages.audit as audit_ui

        src = inspect.getsource(audit_ui)
        assert "Cách đọc đúng theo hành vi thị trường Việt Nam" in src
        assert "MFPM + SMS/M-CVD + AMF + T+ Verdict" in src


class TestScannerFilteredSummary:
    def test_scanner_has_reading_guide_and_view_metrics(self):
        import tradingos.ui.pages.scanner as scanner_ui

        src = inspect.getsource(scanner_ui.render)
        assert "Cách đọc kết quả Scanner" in src
        assert "Mã đang hiển thị" in src
        assert "Cơ hội buy/watch" in src


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