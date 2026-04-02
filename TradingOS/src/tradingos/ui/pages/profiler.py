"""Stock Profiler page — full single-ticker analysis."""
from __future__ import annotations

import io
import pandas as pd
import streamlit as st

from tradingos.engines.profiler_service import ProfilerService
from tradingos.engines.audit_service import AuditService
from tradingos.data.schemas import ProfilerRequest
from tradingos.ui.components.signal_card import render_signal_card
from tradingos.ui.components.horizon_table import render_horizon_table
from tradingos.ui.components.shap_chart import render_shap_chart
from tradingos.ui.components.sms_gauge import render_sms_gauge
from tradingos.ui.components.mcvd_chart import render_mcvd_chart

_ALL_ACTIONS = ["ALL", "STRONG_BUY", "BUY", "WATCH", "NO_ACTION", "EXIT", "FORCED_EXIT"]


def _profile_to_row(p) -> dict:
    return {
        "Mã":          p.ticker,
        "Sàn":         p.exchange,
        "Action":      p.action,
        "Conf":        p.confidence,
        "MFPM":        p.mfpm_score,
        "Macro":       p.macro_regime,
        "MacroScore":  p.macro_score,
        "BCTC Risk":   p.earnings_risk,
        "Days→BCTC":   p.days_to_earnings,
        "FundScore":   p.fundamental_score,
        "W-Score":     p.mode_w_score,
        "SMS":         p.sms_raw,
        "SMS Label":   p.sms_label,
        "Mode":        p.signal_mode,
        "Giá":         p.close,
        "Vào lệnh":    p.entry_price,
        "Cắt lỗ":      p.stop_loss,
        "SL%":         round(p.sl_pct, 2),
        "TP1":         p.tp1,
        "TP2":         p.tp2,
        "R:R":         p.rr_ratio,
        "RSI14":       round(p.rsi14, 1),
        "ATR14":       round(p.atr14, 0),
        "SMA20":       round(p.sma20, 0),
        "Vol":         int(p.volume),
        "AvgVol20d":   int(p.avg_volume_20d),
        "M-CVD5d":     p.mcvd_5d,
        "M-CVD Trend": p.mcvd_trend,
        "Stealth":     p.stealth_accum,
        "Dist Warn":   p.distribution_warning,
        "AMD":         p.amd_phase,
        "HMM":         p.hmm_state,
        "AMF":         p.amf_decision,
        "Pattern":     p.best_pattern,
        "Sector Flow": p.sector_flow,
        "PT Net 5d":   p.pt_net_5d,
        "PT Ratio 5d": p.pt_ratio_5d,
        "Sizing%":     round(p.sizing_pct * 100, 2),
        "Sizing Qty":  p.sizing_shares,
        "Sector":      p.sector,
    }


def _render_detail(profile, svc_label: str = "") -> None:
    render_signal_card(profile)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Horizon", "📊 SMS / M-CVD", "🔬 SHAP", "🧭 Overlay", "📈 Chỉ số"])

    with tab1:
        render_horizon_table(profile.horizons)

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            render_sms_gauge(profile.sms_raw, profile.sms_label, f"SMS – {profile.ticker}")
        with col2:
            st.markdown(f"**M-CVD 5d:** {profile.mcvd_5d:+,.0f}")
            st.markdown(f"**M-CVD 20d:** {profile.mcvd_20d:+,.0f}")
            st.markdown(f"**Trend:** {profile.mcvd_trend}")
            st.markdown(f"**Distribution:** {profile.distribution_warning}")
            st.markdown(f"**PT Net 5d:** {profile.pt_net_5d:+,.0f}")
            st.markdown(f"**PT Ratio 5d:** {profile.pt_ratio_5d:.3f}")
        try:
            from tradingos.engines.money_flow_service import MoneyFlowService
            mf_svc = MoneyFlowService()
            mcvd_df = mf_svc.get_mcvd_chart_data(profile.ticker, days=20)
            render_mcvd_chart(mcvd_df, profile.ticker)
        except Exception:
            pass

    with tab3:
        render_shap_chart({
            "mode_a_score": 0,
            "mode_b_score": 0,
            "mode_w_score": profile.mode_w_score,
            "mc_win_prob": profile.mc_win_prob,
            "components": {},
        }, profile.ticker)

    with tab4:
        c1, c2, c3 = st.columns(3)
        c1.metric("Macro regime", profile.macro_regime or "—", delta=f"score={profile.macro_score:.1f}" if profile.macro_score is not None else None)
        c2.metric("BCTC risk", profile.earnings_risk, delta=f"{profile.days_to_earnings} ngày" if profile.days_to_earnings is not None else None)
        c3.metric("Fundamental", f"{profile.fundamental_score:.1f}" if profile.fundamental_score is not None else "—")
        st.markdown(f"**Next earnings date:** {profile.next_earnings_date or '—'}")
        st.markdown(f"**EPS growth YoY:** {profile.eps_growth_yoy:.1f}%" if profile.eps_growth_yoy is not None else "**EPS growth YoY:** —")
        st.markdown(f"**Revenue growth YoY:** {profile.revenue_growth_yoy:.1f}%" if profile.revenue_growth_yoy is not None else "**Revenue growth YoY:** —")
        st.markdown(f"**ROE:** {profile.roe:.1f}%" if profile.roe is not None else "**ROE:** —")
        st.markdown(f"**Debt / Equity:** {profile.debt_to_equity:.2f}" if profile.debt_to_equity is not None else "**Debt / Equity:** —")
        st.markdown(f"**Sector flow:** {profile.sector_flow}")

    with tab5:
        c1, c2, c3 = st.columns(3)
        c1.metric("Giá đóng cửa", f"{profile.close:,.0f}")
        c2.metric("RSI 14", f"{profile.rsi14:.1f}")
        c3.metric("ATR 14", f"{profile.atr14:,.0f}")
        c1.metric("SMA 20", f"{profile.sma20:,.0f}")
        c2.metric("SMA 50", f"{profile.sma50:,.0f}")
        c3.metric("SMA 200", f"{profile.sma200:,.0f}")
        c1.metric("Volume", f"{profile.volume:,.0f}", delta=f"avg={profile.avg_volume_20d:,.0f}")
        c2.metric("Sizing", f"{profile.sizing_shares:,} cp", delta=f"{profile.sizing_pct:.1%} danh mục")
        c3.metric("Entry window", profile.entry_window)


def render() -> None:
    st.title("🔍 Stock Profiler")
    st.caption("Phân tích toàn diện một hoặc nhiều mã chứng khoán — MFPM, SMS, M-CVD, Horizon.")

    audit_svc = AuditService()

    # ── Input form ────────────────────────────────────────────────────────────
    with st.form("profiler_form"):
        col1, col2 = st.columns([3, 1])

        ticker_input = col1.text_area(
            "Mã chứng khoán (mỗi mã một dòng, hoặc dán dạng CSV)",
            value=st.session_state.get("profiler_ticker", "VCB"),
            height=120,
            placeholder="VCB\nHPG\nSSI",
        )

        mode = col2.selectbox("Mode", ["FULL", "QUICK", "HORIZON_ONLY"], index=0)
        portfolio_val = col2.number_input(
            "Vốn (VND)", value=300_000_000, step=10_000_000, format="%d"
        )
        max_workers = col2.slider("Workers (batch)", 1, 16, 8)
        submitted = st.form_submit_button("🚀 Phân tích", use_container_width=True)

    if not submitted:
        return

    # Parse tickers — support newline, comma, space separation
    raw = ticker_input.replace(",", "\n").replace(" ", "\n")
    tickers = [t.strip().upper() for t in raw.split("\n") if t.strip()]
    if not tickers:
        st.warning("Vui lòng nhập ít nhất một mã.")
        return

    svc = ProfilerService(portfolio_value=portfolio_val)
    profiles: list = []
    errors: list[tuple[str, str]] = []

    progress = st.progress(0.0, text=f"0 / {len(tickers)}")
    for i, ticker in enumerate(tickers):
        progress.progress((i + 1) / len(tickers), text=f"{ticker}  ({i + 1}/{len(tickers)})")
        try:
            profile = svc.run(ProfilerRequest(ticker=ticker, mode=mode))
            profiles.append(profile)
            # Log to audit
            audit_svc.log_event(
                event_type="PROFILE",
                ticker=ticker,
                action=profile.action,
                mfpm_score=profile.mfpm_score,
                sms_raw=profile.sms_raw,
                confidence=profile.confidence,
                extra={
                    "signal_mode": profile.signal_mode,
                    "close": profile.close,
                    "entry_price": profile.entry_price,
                    "stop_loss": profile.stop_loss,
                    "tp1": profile.tp1,
                    "rr_ratio": profile.rr_ratio,
                    "best_pattern": profile.best_pattern,
                    "pt_net_5d": profile.pt_net_5d,
                },
            )
        except Exception as e:
            errors.append((ticker, str(e)))

    progress.empty()

    if errors:
        with st.expander(f"⚠️ {len(errors)} mã lỗi"):
            for sym, msg in errors:
                st.error(f"**{sym}**: {msg}")

    if not profiles:
        st.warning("Không có kết quả.")
        return

    # ── Summary table with signal filter ─────────────────────────────────────
    st.subheader(f"📋 Kết quả — {len(profiles)} mã")

    filter_col, export_col = st.columns([3, 1])
    with filter_col:
        selected_actions = st.multiselect(
            "Lọc theo tín hiệu (Action)",
            options=["STRONG_BUY", "BUY", "WATCH", "NO_ACTION", "EXIT", "FORCED_EXIT"],
            default=[],
            placeholder="Chọn tín hiệu — để trống = hiển thị tất cả",
            key="profiler_action_filter",
        )

    rows = [_profile_to_row(p) for p in profiles]
    df_all = pd.DataFrame(rows)

    df_show = (
        df_all[df_all["Action"].isin(selected_actions)]
        if selected_actions else df_all
    )

    with export_col:
        csv_bytes = df_show.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Xuất CSV",
            data=csv_bytes,
            file_name="profiler_results.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Colour-code Action column
    def _colour_action(val: str) -> str:
        colours = {
            "STRONG_BUY": "background-color:#004d1a; color:#00c851",
            "BUY":        "background-color:#002d40; color:#33b5e5",
            "WATCH":      "background-color:#3d3000; color:#ffbb33",
            "NO_ACTION":  "color:#888",
            "EXIT":       "background-color:#3d0000; color:#ff4444",
            "FORCED_EXIT":"background-color:#260000; color:#cc0000",
        }
        return colours.get(val, "")

    styled = df_show.style.applymap(_colour_action, subset=["Action"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Signal breakdown ──────────────────────────────────────────────────────
    breakdown = df_all["Action"].value_counts()
    cols = st.columns(min(len(breakdown), 6))
    _icons = {"STRONG_BUY": "🚀", "BUY": "🟢", "WATCH": "👀", "NO_ACTION": "⏸", "EXIT": "🔴", "FORCED_EXIT": "⚠️"}
    for i, (action, count) in enumerate(breakdown.items()):
        cols[i % len(cols)].metric(f"{_icons.get(action, '📋')} {action}", count)

    st.divider()

    # ── Per-ticker detail expanders (filtered) ────────────────────────────────
    visible_tickers = set(df_show["Mã"].tolist())
    for profile in profiles:
        if profile.ticker not in visible_tickers:
            continue
        with st.expander(
            f"📈 {profile.ticker} — {profile.action} | MFPM {profile.mfpm_score} | SMS {profile.sms_raw}",
            expanded=(len(visible_tickers) == 1),
        ):
            _render_detail(profile)
