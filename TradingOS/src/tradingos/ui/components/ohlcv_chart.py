"""OHLCV Candlestick chart component with Entry/SL/TP overlay."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from tradingos.data.cache import cache


def render_ohlcv_chart(
    ticker: str,
    entry_price: float = 0.0,
    stop_loss: float = 0.0,
    tp1: float = 0.0,
    tp2: float = 0.0,
    sma20: float = 0.0,
    sma50: float = 0.0,
    days: int = 20,
    key_suffix: str = "",
) -> None:
    """
    Render a candlestick chart for *ticker* with Entry/SL/TP horizontal lines
    and optional SMA20/SMA50 overlays.  Volume subplot is shown below.
    """
    try:
        end = date.today()
        start = end - timedelta(days=days * 2)  # fetch extra to ensure we have enough
        df = cache.get_ohlcv(ticker, start, end)
    except Exception:
        df = pd.DataFrame()

    if df.empty or len(df) < 3:
        st.info(f"📉 Chưa có dữ liệu OHLCV cho {ticker} — chart không hiển thị được.")
        return

    df = df.tail(days).copy()
    date_col = "trade_date" if "trade_date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col]).dt.strftime("%d/%m")

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    # ── Candlestick ───────────────────────────────────────────────────────────
    fig.add_trace(
        go.Candlestick(
            x=df[date_col],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            increasing_line_color="#22c55e",
            decreasing_line_color="#ef4444",
            name="OHLCV",
            showlegend=False,
        ),
        row=1, col=1,
    )

    # ── SMA lines ─────────────────────────────────────────────────────────────
    if "SMA20" in df.columns:
        fig.add_trace(
            go.Scatter(x=df[date_col], y=df["SMA20"], mode="lines",
                       line=dict(color="#f59e0b", width=1.5, dash="dot"),
                       name="SMA20", showlegend=True),
            row=1, col=1,
        )
    elif sma20 > 0:
        fig.add_hline(y=sma20, line=dict(color="#f59e0b", width=1, dash="dot"),
                      annotation_text=f"SMA20 {sma20:,.0f}", annotation_position="right",
                      row=1, col=1)

    if "SMA50" in df.columns:
        fig.add_trace(
            go.Scatter(x=df[date_col], y=df["SMA50"], mode="lines",
                       line=dict(color="#3b82f6", width=1.5, dash="dot"),
                       name="SMA50", showlegend=True),
            row=1, col=1,
        )
    elif sma50 > 0:
        fig.add_hline(y=sma50, line=dict(color="#3b82f6", width=1, dash="dot"),
                      annotation_text=f"SMA50 {sma50:,.0f}", annotation_position="right",
                      row=1, col=1)

    # ── Entry / SL / TP horizontal lines ─────────────────────────────────────
    if entry_price > 0:
        fig.add_hline(
            y=entry_price,
            line=dict(color="#22c55e", width=1.5, dash="solid"),
            annotation_text=f"Entry {entry_price:,.0f}",
            annotation_position="right",
            annotation_font=dict(color="#22c55e", size=11),
            row=1, col=1,
        )
    if stop_loss > 0:
        fig.add_hline(
            y=stop_loss,
            line=dict(color="#ef4444", width=1.5, dash="dash"),
            annotation_text=f"SL {stop_loss:,.0f}",
            annotation_position="right",
            annotation_font=dict(color="#ef4444", size=11),
            row=1, col=1,
        )
    if tp1 > 0:
        fig.add_hline(
            y=tp1,
            line=dict(color="#f59e0b", width=1.2, dash="dash"),
            annotation_text=f"TP1 {tp1:,.0f}",
            annotation_position="right",
            annotation_font=dict(color="#f59e0b", size=11),
            row=1, col=1,
        )
    if tp2 > 0:
        fig.add_hline(
            y=tp2,
            line=dict(color="#ffffff", width=1, dash="dot"),
            annotation_text=f"TP2 {tp2:,.0f}",
            annotation_position="right",
            annotation_font=dict(color="#ffffff", size=11),
            row=1, col=1,
        )

    # ── Volume bars ───────────────────────────────────────────────────────────
    vol_colors = [
        "#22c55e" if c >= o else "#ef4444"
        for c, o in zip(df["close"], df["open"])
    ]
    fig.add_trace(
        go.Bar(
            x=df[date_col],
            y=df["volume"],
            marker_color=vol_colors,
            name="Volume",
            showlegend=False,
        ),
        row=2, col=1,
    )

    fig.update_layout(
        title=f"{ticker} — {days} phiên gần nhất",
        height=360,
        margin=dict(t=40, b=20, l=10, r=80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0f0f1a",
        font_color="white",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis2=dict(showgrid=False),
        yaxis=dict(gridcolor="#1e293b", tickformat=",.0f"),
        yaxis2=dict(gridcolor="#1e293b", tickformat=".2s"),
    )

    _key = f"ohlcv_{ticker}" + key_suffix
    st.plotly_chart(fig, use_container_width=True, key=_key)
