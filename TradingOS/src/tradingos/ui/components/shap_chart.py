"""SHAP-like feature importance chart (template-based, no ML library required)."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def render_shap_chart(mfpm_result: dict, ticker: str = "") -> None:
    """
    Render SHAP-style contribution bar chart from MFPM result.
    Uses pre-computed component scores as feature contributions.
    """
    sms_comps = mfpm_result.get("components", {})
    mode_a = mfpm_result.get("mode_a_score", 0)
    mode_b = mfpm_result.get("mode_b_score", 0)
    mode_w = mfpm_result.get("mode_w_score", 0)
    mc_prob = mfpm_result.get("mc_win_prob", 0)

    features = {
        "Mode A (Pullback)": mode_a,
        "Mode B (Breakout)": mode_b,
        "Mode W (Whale)": mode_w,
        "SMS: Whale OBV": sms_comps.get("whale_obv", 0) * 2,
        "SMS: M-CVD trend": sms_comps.get("mcvd_trend", 0) * 2,
        "SMS: Stealth accum": sms_comps.get("stealth_bonus", 0) * 3,
        "SMS: Sector INFLOW": sms_comps.get("sector_inflow", 0) * 5,
        "MC win prob": int(mc_prob * 30),
    }

    # Sort by abs value
    sorted_feats = sorted(features.items(), key=lambda x: abs(x[1]), reverse=True)
    names = [f[0] for f in sorted_feats]
    vals = [f[1] for f in sorted_feats]
    colors = ["#00c851" if v >= 0 else "#ff4444" for v in vals]

    fig = go.Figure(go.Bar(
        x=vals,
        y=names,
        orientation="h",
        marker_color=colors,
    ))

    fig.add_vline(x=0, line_color="white", line_width=1)
    fig.update_layout(
        title=f"MFPM Feature Contributions — {ticker}",
        height=max(300, len(names) * 35 + 60),
        margin=dict(t=50, b=20, l=10, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        xaxis=dict(gridcolor="#333"),
    )

    st.plotly_chart(fig, use_container_width=True)
