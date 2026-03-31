"""Sector heatmap component — sector rotation visualization."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_sector_heatmap(sector_rotation_result: dict) -> None:
    """
    Render sector rotation result as a heatmap/bar chart.
    sector_rotation_result from detect_sector_rotation().
    """
    rankings = sector_rotation_result.get("rankings", [])
    if not rankings:
        st.info("Không có dữ liệu sector rotation.")
        return

    df = pd.DataFrame(rankings)
    if "sector" not in df.columns or "score" not in df.columns:
        st.info("Dữ liệu sector không hợp lệ.")
        return

    df = df.sort_values("score", ascending=True)
    colors = ["#00c851" if s >= 60 else "#ffbb33" if s >= 40 else "#ff4444" for s in df["score"]]

    fig = go.Figure(go.Bar(
        x=df["score"],
        y=df["sector"],
        orientation="h",
        marker_color=colors,
        text=df.get("flow_label", df["score"].round(0)),
        textposition="outside",
    ))

    market_mode = sector_rotation_result.get("market_mode", "")
    fig.update_layout(
        title=f"Sector Rotation — {market_mode}",
        height=max(300, len(df) * 40),
        margin=dict(t=50, b=20, l=20, r=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        xaxis=dict(range=[0, 110], showgrid=True, gridcolor="#333"),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Top inflow / top outflow summary
    if "top_inflow" in sector_rotation_result and sector_rotation_result["top_inflow"]:
        st.success(f"🔼 Dòng tiền vào: **{', '.join(sector_rotation_result['top_inflow'][:3])}**")
    if "top_outflow" in sector_rotation_result and sector_rotation_result["top_outflow"]:
        st.error(f"🔽 Dòng tiền ra: **{', '.join(sector_rotation_result['top_outflow'][:3])}**")
