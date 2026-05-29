"""
ui/components.py — NewTradingOS v14.0
Shared Streamlit UI helpers: charts, metric cards, score badges.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import TIMEFRAME_CONFIG

# ─── Colour constants ────────────────────────────────────────
GREEN  = "#00cc66"
RED    = "#ff4444"
YELLOW = "#ffaa33"
BLUE   = "#7eb8ff"
PURPLE = "#bb7eff"
GREY   = "#888888"

ACTION_COLORS = {
    "STRONG BUY": GREEN,
    "BUY":        "#55cc88",
    "HOLD":       YELLOW,
    "WATCH":      "#aaaaaa",
    "SELL":       RED,
}

REGIME_COLORS = {
    "bull":     GREEN,
    "sideways": YELLOW,
    "bear":     RED,
}


# ─────────────────────────────────────────────────────────────
# SCORE BADGE HTML
# ─────────────────────────────────────────────────────────────
def score_badge(score: float, action: str) -> str:
    color = ACTION_COLORS.get(action, GREY)
    return (
        f'<span style="background:{color}22;color:{color};'
        f'border:1px solid {color};border-radius:4px;'
        f'padding:2px 8px;font-weight:bold;font-size:13px;">'
        f'{action} {score:.0f}</span>'
    )


def regime_badge(regime: str, prob: float) -> str:
    color = REGIME_COLORS.get(regime, GREY)
    emoji = {"bull": "🟢", "sideways": "🟡", "bear": "🔴"}.get(regime, "⚪")
    label = {"bull": "Tăng", "sideways": "Đi ngang", "bear": "Giảm"}.get(regime, regime)
    return (
        f'<span style="background:{color}22;color:{color};'
        f'border:1px solid {color};border-radius:4px;'
        f'padding:3px 10px;font-weight:bold;">'
        f'{emoji} {label} ({prob:.0%})</span>'
    )


def source_badge(source: str) -> str:
    colors = {
        "DNSE":   ("#1a3a6e", "#7eb8ff"),
        "SSI":    ("#1a4a1a", "#7ecc7e"),
        "CafeF":  ("#2a1a4a", "#bb7eff"),
        "NONE":   ("#3a1a1a", "#cc7e7e"),
    }
    bg, fg = colors.get(source, ("#222", "#aaa"))
    return (
        f'<span style="background:{bg};color:{fg};'
        f'border-radius:3px;padding:1px 6px;font-size:11px;font-weight:bold;">'
        f'{source}</span>'
    )


# ─────────────────────────────────────────────────────────────
# CANDLESTICK + INDICATORS CHART
# ─────────────────────────────────────────────────────────────
def candlestick_chart(
    df: pd.DataFrame,
    ticker: str,
    tf: str,
    signal=None,           # SignalResult optional
    forecast=None,         # ForecastResult optional
    height: int = 700,
) -> go.Figure:
    cfg   = TIMEFRAME_CONFIG[tf]

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.5, 0.15, 0.18, 0.17],
        subplot_titles=(f"{ticker} ({tf})", "Volume", "MACD", "RSI"),
    )

    # ── Candlestick ───────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name="Price", increasing_fillcolor=GREEN,
        decreasing_fillcolor=RED,
    ), row=1, col=1)

    # SMAs
    for col, color, label in [
        ("SMA_fast", BLUE,   f"SMA{cfg['sma_fast']}"),
        ("SMA_slow", YELLOW, f"SMA{cfg['sma_slow']}"),
    ]:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col], name=label,
                line=dict(color=color, width=1.2), opacity=0.8,
            ), row=1, col=1)

    # Bollinger Bands
    if "BB_upper" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_upper"], name="BB Upper",
            line=dict(color=GREY, width=0.7, dash="dot"), showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_lower"], name="BB Lower",
            line=dict(color=GREY, width=0.7, dash="dot"), showlegend=False,
            fill="tonexty", fillcolor="rgba(150,150,150,0.05)",
        ), row=1, col=1)

    # Signal markers
    if signal is not None and signal.score > 0:
        last_date  = df.index[-1]
        last_price = signal.price
        marker_color = ACTION_COLORS.get(signal.action, GREY)
        fig.add_trace(go.Scatter(
            x=[last_date], y=[last_price],
            mode="markers",
            marker=dict(symbol="triangle-up" if "BUY" in signal.action else "triangle-down",
                        color=marker_color, size=14),
            name=signal.action, showlegend=True,
        ), row=1, col=1)
        # Stop / Target horizontal lines (last 20 bars)
        last_20 = df.index[-20:]
        fig.add_hline(y=signal.stop_loss,   line_color=RED,   line_dash="dash",
                      line_width=1, row=1, col=1)
        fig.add_hline(y=signal.take_profit, line_color=GREEN, line_dash="dash",
                      line_width=1, row=1, col=1)

    # Forecast overlay
    if forecast is not None and forecast.prices:
        last_date  = df.index[-1]
        n_days     = len(forecast.prices)
        # Use business day offset
        fut_dates  = pd.bdate_range(start=last_date, periods=n_days + 1)[1:]
        fig.add_trace(go.Scatter(
            x=list(fut_dates), y=forecast.prices,
            name="Ensemble", line=dict(color=PURPLE, width=2, dash="dot"),
        ), row=1, col=1)
        if forecast.prices_bull and forecast.prices_bear:
            fig.add_trace(go.Scatter(
                x=list(fut_dates), y=forecast.prices_bull,
                name="Bull (P75)", line=dict(color=GREEN, width=1, dash="dot"),
                showlegend=True, opacity=0.5,
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=list(fut_dates), y=forecast.prices_bear,
                name="Bear (P25)", line=dict(color=RED, width=1, dash="dot"),
                fill="tonexty", fillcolor="rgba(100,100,200,0.07)",
                showlegend=True, opacity=0.5,
            ), row=1, col=1)

    # ── Volume ────────────────────────────────────────────────
    vol_colors = [
        GREEN if c >= o else RED
        for o, c in zip(df["Open"], df["Close"])
    ]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"], name="Volume",
        marker_color=vol_colors, opacity=0.7,
    ), row=2, col=1)
    if "Vol_ratio" in df.columns:
        # Highlight volume spikes
        spike_mask = df["Vol_ratio"] > 2
        if spike_mask.any():
            fig.add_trace(go.Bar(
                x=df.index[spike_mask], y=df["Volume"][spike_mask],
                name="Vol Spike", marker_color=YELLOW, opacity=0.9,
            ), row=2, col=1)

    # ── MACD ─────────────────────────────────────────────────
    if "MACD" in df.columns:
        hist_colors = [GREEN if v >= 0 else RED for v in df["MACD_hist"].fillna(0)]
        fig.add_trace(go.Bar(
            x=df.index, y=df["MACD_hist"], name="MACD Hist",
            marker_color=hist_colors, opacity=0.7,
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MACD"], name="MACD",
            line=dict(color=BLUE, width=1.2),
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MACD_signal"], name="Signal",
            line=dict(color=RED, width=1.2),
        ), row=3, col=1)

    # ── RSI ───────────────────────────────────────────────────
    if "RSI" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["RSI"], name="RSI",
            line=dict(color=PURPLE, width=1.5),
        ), row=4, col=1)
        fig.add_hline(y=70, line_color=RED,   line_dash="dash", line_width=0.8, row=4, col=1)
        fig.add_hline(y=30, line_color=GREEN, line_dash="dash", line_width=0.8, row=4, col=1)
        fig.add_hrect(y0=30, y1=70, fillcolor="rgba(100,100,200,0.04)",
                      line_width=0, row=4, col=1)

    # ── Layout ────────────────────────────────────────────────
    fig.update_layout(
        height=height,
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=40),
        font=dict(size=11),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# EQUITY CURVE CHART
# ─────────────────────────────────────────────────────────────
def equity_chart(
    equity_curve: list[float],
    initial_capital: float,
    title: str = "Equity Curve",
) -> go.Figure:
    n    = len(equity_curve)
    x    = list(range(n))
    eq   = np.array(equity_curve)
    peak = np.maximum.accumulate(eq)
    dd   = (eq - peak) / peak * 100

    fig  = make_subplots(rows=2, cols=1, shared_xaxes=True,
                          vertical_spacing=0.03, row_heights=[0.7, 0.3],
                          subplot_titles=(title, "Drawdown %"))

    # Equity line
    colors = [GREEN if v >= initial_capital else RED for v in eq]
    fig.add_trace(go.Scatter(
        x=x, y=eq, name="Capital", line=dict(color=BLUE, width=2),
        fill="tozeroy", fillcolor="rgba(126,184,255,0.07)",
    ), row=1, col=1)
    fig.add_hline(y=initial_capital, line_color=GREY, line_dash="dot",
                  line_width=1, row=1, col=1)

    # Drawdown
    fig.add_trace(go.Scatter(
        x=x, y=dd, name="Drawdown %", line=dict(color=RED, width=1.2),
        fill="tozeroy", fillcolor="rgba(255,68,68,0.12)",
    ), row=2, col=1)

    fig.update_layout(
        height=450, template="plotly_dark",
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        margin=dict(l=40, r=40, t=50, b=30),
        showlegend=False,
    )
    return fig


# ─────────────────────────────────────────────────────────────
# SCORE BREAKDOWN RADAR
# ─────────────────────────────────────────────────────────────
def score_radar(breakdown: dict, title: str = "") -> go.Figure:
    cats   = list(breakdown.keys())
    vals   = [breakdown[c] for c in cats]
    maxes  = {"Trend": 25, "Momentum": 20, "RSI": 15, "Volume": 20,
               "Foreign": 5, "Macro": 10, "ADX": 5}
    norm   = [v / maxes.get(c, 10) * 10 for c, v in zip(cats, vals)]
    norm  += [norm[0]]   # close polygon
    cats  += [cats[0]]

    fig = go.Figure(go.Scatterpolar(
        r=norm, theta=cats, fill="toself",
        fillcolor="rgba(126,184,255,0.2)",
        line=dict(color=BLUE, width=2),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="#0e1117",
            radialaxis=dict(visible=True, range=[0, 10], color=GREY),
        ),
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        height=300,
        title=dict(text=title, font=dict(size=13)),
        margin=dict(l=30, r=30, t=50, b=10),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# WORLD MARKET SPARKLINES
# ─────────────────────────────────────────────────────────────
def world_sparkline(prices: list[float], color: str = BLUE) -> go.Figure:
    fig = go.Figure(go.Scatter(
        y=prices, mode="lines",
        line=dict(color=color, width=1.5),
    ))
    fig.update_layout(
        height=60, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig
