"""Signal Card component — render TickerProfile as styled Streamlit card."""
from __future__ import annotations

import streamlit as st

from tradingos.core.nlp import generate_f0_explanation


_ACTION_COLOR = {
    "STRONG_BUY": "#00c851",
    "BUY":        "#33b5e5",
    "WATCH":      "#ffbb33",
    "NO_ACTION":  "#aaaaaa",
    "EXIT":       "#ff4444",
    "FORCED_EXIT":"#cc0000",
}

_CONFIDENCE_BADGE = {
    "HIGH":   "🟢 HIGH",
    "MEDIUM": "🟡 MEDIUM",
    "LOW":    "🔴 LOW",
    "—":      "⚪ —",
}


def render_signal_card(profile) -> None:
    """Render a TickerProfile as a styled Streamlit card."""
    action = profile.action
    color = _ACTION_COLOR.get(action, "#888")
    badge = _CONFIDENCE_BADGE.get(profile.confidence, profile.confidence)

    with st.container():
        st.markdown(
            f"""
            <div style="border-left: 5px solid {color}; padding: 12px 16px;
                        border-radius: 6px; background: #1e1e2e; margin-bottom: 12px;">
              <h3 style="margin:0; color:{color};">{profile.ticker} — {action}</h3>
              <p style="margin:4px 0; color:#aaa;">{badge} &nbsp;|&nbsp; Mode: {profile.signal_mode}
                 &nbsp;|&nbsp; MFPM: <b>{profile.mfpm_score}</b></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Vào lệnh", f"{profile.entry_price:,.0f} đ")
    col2.metric("Cắt lỗ", f"{profile.stop_loss:,.0f} đ", delta=f"-{profile.sl_pct:.1%}")
    col3.metric("TP1 / TP2", f"{profile.tp1:,.0f} / {profile.tp2:,.0f}")
    col4.metric("R:R", f"1:{profile.rr_ratio:.1f}")

    # ── Quick-glance signal badges ────────────────────────────────────────────
    tw       = getattr(profile, "trend_warning", "NONE") or "NONE"
    tw_vi    = getattr(profile, "trend_warning_vi", "") or ""
    fc_vote  = getattr(profile, "fc_overall_vote", "") or ""
    fc_conf  = getattr(profile, "fc_overall_conf", 0.0) or 0.0
    verdict  = getattr(profile, "tplus_verdict", "") or ""
    vd_vi    = getattr(profile, "tplus_verdict_vi", "") or verdict
    tplus_conf = getattr(profile, "tplus_confidence", 0.0) or 0.0

    _TW_COLOR = {
        "UPTREND_STRENGTHENING":     "#22c55e",
        "DOWNTREND_STRENGTHENING":   "#ef4444",
        "UPTREND_EXHAUSTING":        "#f59e0b",
        "DOWNTREND_EXHAUSTING":      "#6366f1",
        "RANGE_COMPRESSION":         "#94a3b8",
        "BREAKOUT_EMERGING":         "#3b82f6",
        "REVERSAL_WARNING_LOW_CONF": "#f97316",
        "REVERSAL_WARNING_CONFIRMED":"#dc2626",
        "NONE":                      "#475569",
        "INSUFFICIENT_DATA":         "#475569",
    }
    _TW_LABEL = {
        "UPTREND_STRENGTHENING":     "Tăng mạnh",
        "DOWNTREND_STRENGTHENING":   "Giảm mạnh",
        "UPTREND_EXHAUSTING":        "Tăng cạn kiệt",
        "DOWNTREND_EXHAUSTING":      "Giảm đảo chiều",
        "RANGE_COMPRESSION":         "Tích lũy",
        "BREAKOUT_EMERGING":         "Sắp bứt phá",
        "REVERSAL_WARNING_LOW_CONF": "Cảnh báo đảo chiều",
        "REVERSAL_WARNING_CONFIRMED":"Đảo chiều ✓",
        "NONE":                      "Bình thường",
        "INSUFFICIENT_DATA":         "Thiếu dữ liệu",
    }
    _VOTE_COLOR   = {"TĂNG": "#22c55e", "GIẢM": "#ef4444", "TRUNG LẬP": "#94a3b8"}
    _VERDICT_COLOR = {
        "MUA_NGAY":      "#22c55e",
        "CHO_XAC_NHAN": "#f59e0b",
        "THEO_DOI":     "#94a3b8",
        "TRANH_XA":     "#ef4444",
    }

    tw_col = _TW_COLOR.get(tw, "#475569")
    fc_col = _VOTE_COLOR.get(fc_vote, "#475569")
    vd_col = _VERDICT_COLOR.get(verdict, "#475569")
    tw_display = _TW_LABEL.get(tw, tw_vi or tw)

    def _badge(label: str, value: str, color: str, sub: str = "") -> str:
        sub_html = f'<div style="font-size:10px;color:#64748b;margin-top:1px;">{sub}</div>' if sub else ""
        return (
            f'<div style="background:{color}15;border:1px solid {color}40;border-radius:8px;'
            f'padding:7px 10px;text-align:center;">'
            f'<div style="font-size:10px;color:#94a3b8;margin-bottom:2px;">{label}</div>'
            f'<div style="font-size:13px;font-weight:700;color:{color};line-height:1.2;">{value}</div>'
            f'{sub_html}</div>'
        )

    b1, b2, b3, b4 = st.columns(4)
    b1.markdown(_badge("⚠️ Trend Warning", tw_display, tw_col), unsafe_allow_html=True)
    b2.markdown(
        _badge("🔭 Dự báo", fc_vote or "—", fc_col, f"{fc_conf:.0f}% tin cậy" if fc_conf > 0 else ""),
        unsafe_allow_html=True,
    )
    b3.markdown(_badge("🎯 T+ Verdict", vd_vi or "—", vd_col), unsafe_allow_html=True)
    b4.markdown(
        _badge("📊 T+ Conf", f"{tplus_conf:.0f}%" if tplus_conf > 0 else "—", vd_col),
        unsafe_allow_html=True,
    )
    st.write("")

    with st.expander("📊 Chi tiết tín hiệu", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**SMS:** {profile.sms_raw} ({profile.sms_label})")
            st.markdown(f"**M-CVD trend:** {profile.mcvd_trend}")
            st.markdown(f"**Stealth Accum:** {'✅' if profile.stealth_accum else '❌'} ({profile.stealth_confidence})")
            st.markdown(f"**Distribution:** {profile.distribution_warning}")
        with c2:
            st.markdown(f"**HMM State:** {profile.hmm_state}")
            st.markdown(f"**AMD Phase:** {profile.amd_phase}")
            st.markdown(f"**AMF:** {profile.amf_decision}")
            st.markdown(f"**Pattern:** {profile.best_pattern}")
            st.markdown(f"**Sector Flow:** {getattr(profile, 'sector_flow', 'NEUTRAL')}")
            st.markdown(f"**Macro:** {getattr(profile, 'macro_regime', '—')} ({getattr(profile, 'macro_score', '—')})")
            st.markdown(f"**BCTC Risk:** {getattr(profile, 'earnings_risk', 'SAFE')}")
            st.markdown(f"**Fundamental:** {getattr(profile, 'fundamental_score', '—')}")

    if profile.entry_window and profile.entry_window != "—":
        st.info(f"⏰ Cửa sổ vào lệnh khuyến nghị: **{profile.entry_window}**")

    if profile.advisory_text:
        _nlp_expanded = profile.action in ("STRONG_BUY", "BUY")
        with st.expander("📝 Phân tích & Lý giải tín hiệu (NLP)", expanded=_nlp_expanded):
            st.markdown(profile.advisory_text)

    with st.expander("🔰 Giải thích dành cho nhà đầu tư mới (F0)", expanded=False):
        st.caption("Ngôn ngữ đơn giản — 6 mục: Kết luận, Lý do, Tín hiệu ủng hộ, Rủi ro, Kế hoạch, Khuyến nghị.")
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
