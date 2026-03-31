"""Stock Profiler page — full single-ticker analysis."""
from __future__ import annotations

import streamlit as st

from tradingos.engines.profiler_service import ProfilerService
from tradingos.data.schemas import ProfilerRequest
from tradingos.ui.components.signal_card import render_signal_card
from tradingos.ui.components.horizon_table import render_horizon_table
from tradingos.ui.components.shap_chart import render_shap_chart
from tradingos.ui.components.sms_gauge import render_sms_gauge
from tradingos.ui.components.mcvd_chart import render_mcvd_chart


def render() -> None:
    st.title("🔍 Stock Profiler")
    st.caption("Phân tích toàn diện một mã chứng khoán — MFPM, SMS, M-CVD, Horizon.")

    with st.form("profiler_form"):
        col1, col2 = st.columns([3, 1])
        ticker_input = col1.text_area(
            "Mã chứng khoán (mỗi mã một dòng)",
            value="VCB",
            height=100,
            placeholder="VCB\nHPG\nSSI",
        )
        mode = col2.selectbox("Mode", ["FULL", "QUICK", "HORIZON_ONLY"], index=0)
        portfolio_val = col2.number_input(
            "Vốn (VND)", value=300_000_000, step=10_000_000, format="%d"
        )
        submitted = st.form_submit_button("🚀 Phân tích", use_container_width=True)

    if submitted:
        tickers = [t.strip().upper() for t in ticker_input.split("\n") if t.strip()]
        if not tickers:
            st.warning("Vui lòng nhập ít nhất một mã.")
            return

        svc = ProfilerService(portfolio_value=portfolio_val)

        for ticker in tickers:
            with st.spinner(f"Đang phân tích {ticker}..."):
                try:
                    request = ProfilerRequest(ticker=ticker, mode=mode)
                    profile = svc.run(request)
                except Exception as e:
                    st.error(f"{ticker}: {e}")
                    continue

            with st.expander(f"📈 {ticker} — {profile.action} | MFPM {profile.mfpm_score}", expanded=(len(tickers) == 1)):
                render_signal_card(profile)

                tab1, tab2, tab3, tab4 = st.tabs(["📋 Horizon", "📊 SMS / M-CVD", "🔬 SHAP", "📈 Chỉ số"])

                with tab1:
                    render_horizon_table(profile.horizons)

                with tab2:
                    col1, col2 = st.columns(2)
                    with col1:
                        render_sms_gauge(profile.sms_raw, profile.sms_label, f"SMS – {ticker}")
                    with col2:
                        st.markdown(f"**M-CVD 5d:** {profile.mcvd_5d:+,.0f}")
                        st.markdown(f"**M-CVD 20d:** {profile.mcvd_20d:+,.0f}")
                        st.markdown(f"**Trend:** {profile.mcvd_trend}")
                        st.markdown(f"**Distribution:** {profile.distribution_warning}")

                    try:
                        from tradingos.engines.money_flow_service import MoneyFlowService
                        mf_svc = MoneyFlowService()
                        mcvd_df = mf_svc.get_mcvd_chart_data(ticker, days=20)
                        render_mcvd_chart(mcvd_df, ticker)
                    except Exception:
                        pass

                with tab3:
                    render_shap_chart({
                        "mode_a_score": 0,
                        "mode_b_score": 0,
                        "mode_w_score": profile.mode_w_score,
                        "mc_win_prob": profile.mc_win_prob,
                        "components": {},
                    }, ticker)

                with tab4:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Giá đóng cửa", f"{profile.close:,.0f}")
                    c2.metric("RSI 14", f"{profile.rsi14:.1f}")
                    c3.metric("ATR 14", f"{profile.atr14:,.0f}")
                    c1.metric("SMA 20", f"{profile.sma20:,.0f}")
                    c2.metric("SMA 50", f"{profile.sma50:,.0f}")
                    c3.metric("SMA 200", f"{profile.sma200:,.0f}")
                    st.metric("Volume hôm nay", f"{profile.volume:,.0f}", delta=f"avg={profile.avg_volume_20d:,.0f}")

            st.divider()
        st.markdown(f"**Sizing:** {profile.sizing_shares:,} cổ phiếu ({profile.sizing_pct:.1%} danh mục)")
