"""M-CVD bar chart component."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_mcvd_chart(mcvd_df: pd.DataFrame, ticker: str = "", days: int = 20, key_suffix: str = "") -> None:
    """
    Render M-CVD net whale flow as bar chart.
    mcvd_df must have columns: date (or index), whale_net.
    """
    if mcvd_df.empty:
        st.info("Không có dữ liệu M-CVD.")
        return

    df = mcvd_df.copy().tail(days)

    # [BUG-B5 FIX] Guard against missing whale_net column to prevent KeyError crash
    if "whale_net" not in df.columns:
        st.warning("⚠️ M-CVD: cột whale_net không tồn tại trong dữ liệu được cung cấp.")
        return

    if "date" not in df.columns:
        df = df.reset_index()
        date_col = df.columns[0]
        df = df.rename(columns={date_col: "date"})

    dates = df["date"].astype(str)
    values = df["whale_net"].fillna(0)
    colors = ["#00c851" if v >= 0 else "#ff4444" for v in values]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=dates,
        y=values,
        marker_color=colors,
        name="Whale Net Flow",
    ))

    if "whale_net_cumulative" in df.columns:
        fig.add_trace(go.Scatter(
            x=dates,
            y=df["whale_net_cumulative"],
            mode="lines",
            line=dict(color="#ffdd57", width=2),
            name="Cumulative",
            yaxis="y2",
        ))
        fig.update_layout(
            yaxis2=dict(overlaying="y", side="right", showgrid=False),
        )

    fig.update_layout(
        title=f"M-CVD — {ticker} ({days}d)",
        height=300,
        margin=dict(t=40, b=20, l=40, r=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="#333"),
        showlegend=True,
    )

    _key = (f"mcvd_chart_{ticker}" if ticker else "mcvd_chart") + key_suffix
    st.plotly_chart(fig, use_container_width=True, key=_key)
