"""Audit page — event log browser."""
from __future__ import annotations

import streamlit as st

from tradingos.engines.audit_service import AuditService
from tradingos.ui.components.audit_timeline import render_audit_timeline, render_audit_stats


def render() -> None:
    st.title("🗂 Audit Log")
    st.caption("Lịch sử tín hiệu và sự kiện — truy xuất từ DuckDB.")

    svc = AuditService()

    with st.form("audit_form"):
        col1, col2, col3 = st.columns(3)
        ticker = col1.text_input("Lọc mã (để trống = tất cả)", "")
        event_type = col2.selectbox("Loại sự kiện", ["", "PROFILE", "SCAN", "BACKTEST", "POSITION_OPEN"], index=0)
        days_back = col3.number_input("Số ngày", value=30, min_value=1, max_value=365)
        submitted = st.form_submit_button("🔍 Tìm kiếm")

    if submitted:
        df = svc.query_events(
            ticker=ticker.upper() if ticker.strip() else None,
            event_type=event_type if event_type else None,
            days_back=int(days_back),
        )
        st.subheader(f"📋 {len(df)} sự kiện")
        render_audit_timeline(df)

    st.divider()
    st.subheader("📊 Thống kê 30 ngày gần nhất")
    stats = svc.summary_stats(days_back=30)
    render_audit_stats(stats)
