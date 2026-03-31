"""Signal Card component — render TickerProfile as styled Streamlit card."""
from __future__ import annotations

import streamlit as st


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

    if profile.advisory_text:
        st.markdown(profile.advisory_text)

    if profile.entry_window and profile.entry_window != "—":
        st.info(f"⏰ Cửa sổ vào lệnh khuyến nghị: **{profile.entry_window}**")
