"""Money Flow / DTL Dashboard page (FR-6)."""
from __future__ import annotations

import streamlit as st

from tradingos.engines.money_flow_service import MoneyFlowService
from tradingos.ui.components.sms_gauge import render_sms_gauge
from tradingos.ui.components.mcvd_chart import render_mcvd_chart
from tradingos.ui.components.sector_heatmap import render_sector_heatmap
from tradingos.ui.components.dataframe_filter import filter_dataframe


def render() -> None:
    st.title("🐳 Dòng tiền thông minh (DTL)")
    st.caption("M-CVD, SMS, Stealth Accumulation, Sector Rotation — FR-6")

    svc = MoneyFlowService()

    tab1, tab2, tab3 = st.tabs(["🐋 Watchlist SMS", "📊 M-CVD Chart", "🗺 Sector Rotation"])

    # ── Tab 1: Whale watchlist ─────────────────────────────────────────────
    with tab1:
        custom_tickers = st.text_input(
            "Nhập danh sách mã (phân cách dấu phẩy, để trống = từ watchlist):",
            placeholder="VCB,HPG,SSI,VIC"
        )

        if st.button("🔄 Load SMS Watchlist"):
            tickers = [t.strip().upper() for t in custom_tickers.split(",") if t.strip()] or None
            with st.spinner("Đang tính SMS..."):
                df = svc.get_whale_watchlist(tickers)

            if df.empty:
                st.info("Không có dữ liệu.")
            else:
                df = filter_dataframe(df, key_prefix="money_flow")
                st.dataframe(df, use_container_width=True, hide_index=True)
                # Show gauge for top ticker
                if len(df) > 0:
                    top = df.iloc[0]
                    render_sms_gauge(int(top["sms"]), str(top["sms_label"]), f"SMS Top — {top['ticker']}")

    # ── Tab 2: M-CVD chart ────────────────────────────────────────────────
    with tab2:
        col1, col2 = st.columns([3, 1])
        mcvd_ticker = col1.text_input("Mã:", value="VCB", key="mcvd_ticker")
        mcvd_days = col2.number_input("Số ngày", value=20, min_value=5, max_value=60, key="mcvd_days")

        if st.button("📊 Vẽ M-CVD"):
            with st.spinner("Đang lấy dữ liệu..."):
                df = svc.get_mcvd_chart_data(mcvd_ticker.upper(), days=int(mcvd_days))
            render_mcvd_chart(df, mcvd_ticker.upper(), days=int(mcvd_days), key_suffix="_mf")

            # Also show SMS
            sms_data = svc.get_sms(mcvd_ticker.upper())
            sms_col1, sms_col2 = st.columns(2)
            with sms_col1:
                render_sms_gauge(sms_data.get("sms", 0), sms_data.get("sms_label", ""), mcvd_ticker.upper(), key_suffix="_mf")
            with sms_col2:
                stealth = sms_data.get("stealth_detail", {})
                mcvd_d = sms_data.get("mcvd_detail", {})
                st.metric("M-CVD Trend", mcvd_d.get("mcvd_trend", "—"))
                st.metric("Stealth Accum", "✅ Phát hiện" if stealth.get("detected") else "❌")
                dist = svc.get_distribution_status(mcvd_ticker.upper())
                st.metric("Distribution Warning", dist.get("level", "NONE"))

    # ── Tab 3: Sector rotation ────────────────────────────────────────────
    with tab3:
        if st.button("🗺 Tính Sector Rotation"):
            with st.spinner("Đang phân tích sector..."):
                rotation = svc.get_sector_flows()
            render_sector_heatmap(rotation)
            st.markdown(f"**Market Mode:** `{rotation.get('rotation_phase', '—')}`")
