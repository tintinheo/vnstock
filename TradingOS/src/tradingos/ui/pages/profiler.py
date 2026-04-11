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
from tradingos.core.nlp import generate_indicator_explanation, generate_f0_explanation

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
    # ── Real-time price header ────────────────────────────────────────────────
    if profile.rt_price:
        pct = profile.rt_pct_change or 0.0
        pct_color = "#22c55e" if pct >= 0 else "#ef4444"
        pct_sign  = "+" if pct >= 0 else ""
        rt_html = (
            f'<div style="display:flex;gap:20px;align-items:center;'
            f'padding:8px 12px;background:#1e293b;border-radius:8px;'
            f'margin-bottom:12px;flex-wrap:wrap;">'
            f'<span style="font-size:22px;font-weight:800;color:#f1f5f9;">'
            f'{profile.rt_price:,.0f} VND</span>'
            f'<span style="font-size:16px;font-weight:600;color:{pct_color};">'
            f'{pct_sign}{pct:.2f}%</span>'
        )
        if profile.rt_reference:
            rt_html += (
                f'<span style="color:#94a3b8;font-size:13px;">'
                f'Tham chiếu: {profile.rt_reference:,.0f}</span>'
            )
        if profile.rt_ceiling:
            rt_html += (
                f'<span style="color:#f59e0b;font-size:13px;">'
                f'Trần: {profile.rt_ceiling:,.0f}</span>'
            )
        if profile.rt_floor:
            rt_html += (
                f'<span style="color:#6366f1;font-size:13px;">'
                f'Sàn: {profile.rt_floor:,.0f}</span>'
            )
        rt_html += '</div>'
        st.markdown(rt_html, unsafe_allow_html=True)
        if profile.rt_at_ceiling:
            st.warning("⚠️ Giá đang ở TRẦN — áp lực chốt lời cao, tránh mua đuổi")
        if profile.rt_at_floor:
            st.success("✅ Giá đang ở SÀN — có thể có cơ hội bắt đáy ngắn hạn")

    render_signal_card(profile)

    tab1, tab2, tab3, tab4, tab5, tab_nlp, tab_f0, tab_t25, tab_tw, tab_fc, tab_tplus = st.tabs([
        "📋 Horizon", "📊 SMS / M-CVD", "🔬 SHAP", "🧭 Overlay",
        "📈 Chỉ số", "📝 NLP Insights", "🔰 Giải thích F0", "⚡ T+2.5",
        "⚠️ Trend Warning", "🔭 Dự báo", "🎯 T+ Setup",
    ])

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
            "mode_a_score": profile.mode_a_score,
            "mode_b_score": profile.mode_b_score,
            "mode_w_score": profile.mode_w_score,
            "mc_win_prob":  profile.mc_win_prob,
            "components":   profile.sms_components,
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

        st.divider()
        st.markdown("#### 📐 Moving Averages (ngắn hạn → dài hạn)")
        _ma_display = [
            ("SMA 3",   profile.sma3),
            ("SMA 5",   profile.sma5),
            ("SMA 7",   profile.sma7),
            ("SMA 10",  profile.sma10),
            ("EMA 50",  profile.ema50),
            ("EMA 200", profile.ema200),
        ]
        _ma_cols = st.columns(6)
        for i, (label, val) in enumerate(_ma_display):
            if val and val > 0:
                _ma_cols[i].metric(label, f"{val:,.0f}")
            else:
                _ma_cols[i].metric(label, "—")

        st.divider()
        st.markdown("#### 🔍 Gap Analysis")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Gap Type", profile.gap_type)
        g2.metric("Gap %", f"{profile.gap_pct:+.2f}%")
        g3.metric("Avg Gap 20d", f"{profile.avg_gap_pct:.2f}%")
        g4.metric("Gap Fill Rate", f"{profile.gap_fill_pct:.0f}%")

        st.divider()
        st.markdown("#### 📊 VWAP")
        v1, v2, v3 = st.columns(3)
        v1.metric(
            "VWAP Daily (20-bar)",
            f"{profile.vwap_daily_val:,.0f}",
            delta=f"{profile.price_vs_vwap_pct:+.2f}% vs VWAP",
        )
        v2.metric("Position", profile.vwap_dev)
        if profile.vwap_intraday:
            v3.metric(
                "VWAP Intraday",
                f"{profile.vwap_intraday:,.0f}",
                delta=f"{profile.vwap_intraday_dev} | slope={profile.vwap_intraday_slope:+.0f}",
            )
        else:
            v3.metric("VWAP Intraday", "—", delta="outside market hours")

        st.divider()
        st.markdown("#### 💬 Giải thích chỉ số")
        ind_insights = generate_indicator_explanation(
            rsi14=profile.rsi14,
            close=profile.close,
            sma20=profile.sma20,
            sma50=profile.sma50,
            sma200=profile.sma200,
            atr14=profile.atr14,
            volume=profile.volume,
            avg_volume_20d=profile.avg_volume_20d,
            macd=profile.macd,
        )
        for insight in ind_insights:
            st.markdown(insight)

    with tab_t25:
        st.markdown("#### ⚡ VN-Swing Alpha T+2.5 Entry Score")
        st.caption(
            "Điểm vào lệnh ngắn hạn T+2.5 — kết hợp Momentum, Cấu trúc MA và Xác nhận "
            "để nhận diện cửa sổ vào lệnh tối ưu trong phiên."
        )
        _T25_COLOR = {
            "T25_BUY":     "#22c55e",
            "T25_WATCH":   "#3b82f6",
            "T25_NEUTRAL": "#94a3b8",
            "T25_AVOID":   "#ef4444",
        }
        if profile.t25_score is not None:
            _sig = profile.t25_signal
            _col = _T25_COLOR.get(_sig, "#94a3b8")
            st.markdown(
                f'<div style="padding:10px 16px;border-left:4px solid {_col};'
                f'background:{_col}18;border-radius:6px;margin-bottom:12px;">'
                f'<span style="color:{_col};font-size:22px;font-weight:800;">'
                f'{_sig.replace("T25_", "")}  {profile.t25_score:.1f}/100'
                f'</span></div>',
                unsafe_allow_html=True,
            )
            a1, a2, a3 = st.columns(3)
            a1.metric("Momentum (A)", f"{profile.t25_momo_score:.1f} / 20")
            a2.metric("Structure (B)", f"{profile.t25_struct_score:.1f} / 20")
            a3.metric("Confirm (C)",   f"{profile.t25_conf_score:.1f} / 10")
            if profile.t25_confirms:
                st.markdown("**Confirmations:** " + " · ".join(profile.t25_confirms[:8]))
            if _sig == "T25_BUY":
                st.success("⏰ Cửa sổ lý tưởng: **10:00–11:00** (tốt nhất) · 13:30–14:00 (thay thế) · **TRÁNH ATO/ATC**")
            elif _sig == "T25_AVOID":
                st.error("⚠️ Cấu trúc yếu — không phải thời điểm tốt để vào lệnh.")
            elif _sig == "T25_WATCH":
                st.info("👀 Cần thêm xác nhận — theo dõi breakout hoặc volume spike.")
        else:
            st.info("T+2.5 chưa được tính (thiếu dữ liệu chỉ số).")

        # ── Multi-frame session windows ───────────────────────────────────
        if profile.t25_morning_score > 0 or profile.t25_midday_score > 0:
            st.divider()
            st.markdown("#### 🕐 Phân tích theo cửa sổ phiên giao dịch")
            w1, w2, w3 = st.columns(3)
            w1.metric("🌅 Sáng (9:15–11:30)", f"{profile.t25_morning_score:.0f}/100",
                      delta="Breakout / Momentum")
            w2.metric("☀️ Giữa phiên (12:45–13:15)", f"{profile.t25_midday_score:.0f}/100",
                      delta="T+2.5 Settlement")
            w3.metric("🌇 Chiều (13:00–14:30)", f"{profile.t25_afternoon_score:.0f}/100",
                      delta="Continuation / ATC")
            if profile.t25_best_window:
                _win_labels = {
                    "morning":   "🌅 Sáng (9:15–11:30)",
                    "midday":    "☀️ Giữa phiên (12:45–13:15)",
                    "afternoon": "🌇 Chiều (13:00–14:30)",
                }
                st.info(f"**Cửa sổ tốt nhất hôm nay:** {_win_labels.get(profile.t25_best_window, profile.t25_best_window)}")
            if profile.t25_mf_reasons:
                st.markdown("**Lý do:** " + " · ".join(profile.t25_mf_reasons))

    with tab_tw:
        st.markdown("#### ⚠️ Trend Warning Engine")
        st.caption("Phân loại cấu trúc thị trường hiện tại và đưa ra cảnh báo xu hướng sớm.")
        _TW_COLORS = {
            "UPTREND_STRENGTHENING":    "#22c55e",
            "DOWNTREND_STRENGTHENING":  "#ef4444",
            "UPTREND_EXHAUSTING":       "#f59e0b",
            "DOWNTREND_EXHAUSTING":     "#6366f1",
            "RANGE_COMPRESSION":        "#94a3b8",
            "BREAKOUT_EMERGING":        "#3b82f6",
            "REVERSAL_WARNING_LOW_CONF":"#f97316",
            "REVERSAL_WARNING_CONFIRMED":"#dc2626",
            "NONE":                     "#64748b",
            "INSUFFICIENT_DATA":        "#475569",
        }
        tw = profile.trend_warning or "NONE"
        tw_vi = profile.trend_warning_vi or ("Không có cảnh báo" if tw == "NONE" else tw)
        tw_col = _TW_COLORS.get(tw, "#94a3b8")
        tw_conf_pct = int(profile.trend_warning_conf * 100)
        st.markdown(
            f'<div style="padding:12px 18px;border-left:5px solid {tw_col};'
            f'background:{tw_col}18;border-radius:8px;margin-bottom:16px;">'
            f'<div style="color:{tw_col};font-size:20px;font-weight:800;">{tw_vi}</div>'
            f'<div style="color:#94a3b8;font-size:13px;margin-top:4px;">'
            f'Tín hiệu: {tw} · Độ tin cậy: {tw_conf_pct}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if tw_conf_pct > 0:
            st.progress(tw_conf_pct)
        if profile.trend_warning_reasons:
            st.markdown("**Lý do phân tích:**")
            for r in profile.trend_warning_reasons:
                st.markdown(f"- {r}")
        elif tw == "NONE":
            st.info("Không có cảnh báo cấu trúc đặc biệt — xu hướng bình thường.")

    with tab_fc:
        st.markdown("#### 🔭 Dự báo đa khung thời gian")
        st.caption(
            "Nhận định xác suất tăng/giảm/trung lập theo 3 khung: "
            "Ngắn hạn (3–5 phiên) · Trung hạn (~1 tháng) · Dài hạn (3–6 tháng)."
        )
        _VOTE_COLOR = {"TĂNG": "#22c55e", "GIẢM": "#ef4444", "TRUNG LẬP": "#94a3b8", "": "#64748b"}

        def _fc_card(title: str, vote: str, conf: float, reasons: list) -> None:
            col_v = _VOTE_COLOR.get(vote, "#94a3b8")
            st.markdown(
                f'<div style="border:1px solid {col_v}44;border-radius:10px;'
                f'padding:14px;background:{col_v}0d;">'
                f'<div style="font-size:13px;color:#94a3b8;margin-bottom:4px;">{title}</div>'
                f'<div style="font-size:24px;font-weight:800;color:{col_v};">{vote or "—"}</div>'
                f'<div style="font-size:13px;color:#cbd5e1;margin-top:4px;">'
                f'Độ tin cậy: {conf:.0f}%</div></div>',
                unsafe_allow_html=True,
            )
            if conf > 0:
                st.progress(min(100, int(conf)))
            if reasons:
                for r in reasons[:4]:
                    st.markdown(f"  - {r}")

        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            _fc_card(
                "📅 Ngắn hạn (3–5 phiên)",
                profile.fc_short_vote, profile.fc_short_conf,
                profile.fc_short_reasons,
            )
        with fc2:
            _fc_card(
                "📆 Trung hạn (~1 tháng)",
                profile.fc_mid_vote, profile.fc_mid_conf,
                profile.fc_mid_reasons,
            )
        with fc3:
            _fc_card(
                "📊 Dài hạn (3–6 tháng)",
                profile.fc_long_vote, profile.fc_long_conf,
                profile.fc_long_reasons,
            )

        if profile.fc_overall_vote:
            st.divider()
            ov_col = _VOTE_COLOR.get(profile.fc_overall_vote, "#94a3b8")
            st.markdown(
                f'<div style="text-align:center;padding:10px;">'
                f'<span style="font-size:15px;color:#94a3b8;">Tổng hợp: </span>'
                f'<span style="font-size:20px;font-weight:800;color:{ov_col};">'
                f'{profile.fc_overall_vote}</span>'
                f'<span style="font-size:14px;color:#94a3b8;"> · {profile.fc_overall_conf:.0f}%</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Dự báo chưa được tính — cần ít nhất 20 phiên dữ liệu.")

    with tab_tplus:
        st.markdown("#### 🎯 Phân tích T+ Setup — Giao dịch trong ngày / T+2.5")
        st.caption(
            "Phân loại cơ hội T+ hiện tại, đề xuất vùng vào lệnh, mục tiêu chốt T+2.5 / T+5, "
            "điểm cắt lỗ, phiên vào lệnh tốt nhất và mức độ tin cậy."
        )

        _VERDICT_COLOR = {
            "MUA_NGAY":      "#22c55e",
            "CHO_XAC_NHAN": "#f59e0b",
            "THEO_DOI":     "#94a3b8",
            "TRANH_XA":     "#ef4444",
        }

        verdict    = profile.tplus_verdict
        verdict_vi = profile.tplus_verdict_vi
        setup      = profile.tplus_setup
        setup_vi   = profile.tplus_setup_vi
        conf       = profile.tplus_confidence
        vc         = _VERDICT_COLOR.get(verdict, "#94a3b8")

        # Verdict banner
        st.markdown(
            f'<div style="border:2px solid {vc}55;border-radius:12px;padding:16px;'
            f'background:{vc}11;margin-bottom:16px;">'
            f'<div style="font-size:12px;color:#94a3b8;margin-bottom:4px;">Phán quyết T+</div>'
            f'<div style="font-size:26px;font-weight:900;color:{vc};">{verdict_vi or verdict}</div>'
            f'<div style="font-size:13px;color:#cbd5e1;margin-top:6px;">'
            f'Setup: <b>{setup_vi or setup}</b> &nbsp;·&nbsp; Tin cậy: <b>{conf:.0f}%</b></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if conf > 0:
            st.progress(min(100, int(conf)))

        if setup not in ("T_NO_SETUP", "T_AVOID", ""):
            st.divider()
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.markdown("**📥 Vùng vào lệnh**")
                st.markdown(
                    f"Thấp: **{profile.tplus_entry_low:,.0f}**  \n"
                    f"Cao: **{profile.tplus_entry_high:,.0f}**"
                )
                st.caption(profile.tplus_entry_trigger)
            with col_b:
                st.markdown("**🎯 Mục tiêu**")
                st.markdown(
                    f"T+2.5: **{profile.tplus_target_t25:,.0f}**  \n"
                    f"T+5 : **{profile.tplus_target_t5:,.0f}**"
                )
            with col_c:
                st.markdown("**🛑 Cắt lỗ & R:R**")
                st.markdown(
                    f"SL: **{profile.tplus_stop:,.0f}**  \n"
                    f"R:R: **{profile.tplus_rr:.2f}**"
                )

            st.divider()
            st.markdown(f"**⏰ Phiên vào lệnh:** {profile.tplus_session_vi or profile.tplus_session}")

            if profile.tplus_reasons:
                st.markdown("**✅ Lý do ủng hộ setup T+:**")
                for r in profile.tplus_reasons:
                    st.markdown(f"- {r}")

        if profile.tplus_risks:
            st.markdown("**⚠️ Rủi ro cần lưu ý:**")
            for r in profile.tplus_risks:
                st.markdown(f"- {r}")

        if setup in ("T_NO_SETUP", ""):
            st.info(
                "Chưa phát hiện setup T+ rõ ràng — "
                "quan sát khi có thêm tín hiệu khối lượng hoặc nến xác nhận."
            )
        elif setup == "T_AVOID":
            st.warning(
                "Hệ thống phát hiện tín hiệu phân phối hoặc xu hướng bất lợi. "
                "Không khuyến nghị giao dịch T+ cho mã này."
            )

    with tab_nlp:
        st.markdown("#### 🤖 Phân tích toàn diện bằng ngôn ngữ tự nhiên")
        st.caption(
            "Toàn bộ lý do hệ thống đưa ra tín hiệu — bao gồm phân tích mode, "
            "điểm số, cổng quyết định (gate pass/fail), và các mức giá giao dịch."
        )
        if profile.advisory_text:
            st.markdown(profile.advisory_text)
        else:
            st.info("Không có nội dung NLP cho mã này.")

    with tab_f0:
        st.markdown("#### 🔰 Giải thích dành cho nhà đầu tư mới (F0)")
        st.caption(
            "Phân tích bằng ngôn ngữ đơn giản, không cần kiến thức chuyên sâu. "
            "Bao gồm 6 mục: Kết luận → Lý do điểm → Tín hiệu ủng hộ → Rủi ro → Kế hoạch giao dịch → Khuyến nghị hành động."
        )
        f0_text = generate_f0_explanation(
            ticker=profile.ticker,
            action=profile.action,
            mfpm_score=profile.mfpm_score,
            signal_mode=profile.signal_mode,
            confidence=profile.confidence,
            close=profile.close,
            entry_price=profile.entry_price,
            stop_loss=profile.stop_loss,
            sl_pct=profile.sl_pct,
            tp1=profile.tp1,
            tp2=profile.tp2,
            rr_ratio=profile.rr_ratio,
            rsi14=profile.rsi14,
            sms_raw=profile.sms_raw,
            sms_label=profile.sms_label,
            stealth_accum=profile.stealth_accum,
            distribution_warning=profile.distribution_warning,
            hmm_state=profile.hmm_state,
            amd_phase=profile.amd_phase,
            amf_decision=profile.amf_decision,
            best_pattern=profile.best_pattern,
            mcvd_trend=profile.mcvd_trend,
            mc_win_prob=profile.mc_win_prob,
            mode_w_score=profile.mode_w_score,
            macro_regime=getattr(profile, "macro_regime", ""),
            earnings_risk=getattr(profile, "earnings_risk", "SAFE"),
            sma20=profile.sma20,
            sma50=profile.sma50,
            sma200=profile.sma200,
            volume=profile.volume,
            avg_volume_20d=profile.avg_volume_20d,
            atr14=profile.atr14,
        )
        st.markdown(f0_text)


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
