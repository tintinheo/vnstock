"""
ui/components.py — NewTradingOS v14.0
Shared Streamlit UI helpers: charts, metric cards, score badges.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from config import TIMEFRAME_CONFIG
from core.market_calendar import future_trading_dates as vn_future_trading_dates

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

# Dark-mode row highlight styles derived from ACTION_COLORS (single source of truth)
ACTION_ROW_STYLE: dict[str, str] = {
    "STRONG BUY": "background-color: #1a5e2a; color: #ffffff",
    "BUY":        "background-color: #1a4a2a; color: #7ecc7e",
    "HOLD":       "background-color: #3a3010; color: #ffeb9c",
    "WATCH":      "background-color: #0f1c2e; color: #7eb8ff",
    "SELL":       "background-color: #3a1010; color: #ff9999",
}

# Maximum contribution of each score breakdown component (for bar scaling)
_BREAKDOWN_MAXES: dict[str, float] = {
    "Trend": 25, "Momentum": 20, "RSI": 15, "Volume": 20,
    "Foreign": 5, "Macro": 10, "ADX": 5,
}

REGIME_COLORS = {
    "bull":     GREEN,
    "sideways": YELLOW,
    "bear":     RED,
}


def render_section_header(title: str, subtitle: str | None = None) -> None:
    st.subheader(title)
    if subtitle:
        st.caption(subtitle)


def render_decision_panel(
    title: str,
    primary: str,
    secondary: str | None = None,
    *,
    metrics: list[tuple[str, str, str | None]] | None = None,
    tone: str = "info",
) -> None:
    accents = {
        "info": (BLUE, "#0f1724", "🧭"),
        "success": (GREEN, "#0f1c16", "✅"),
        "warning": (YELLOW, "#1f1a11", "⚠️"),
    }
    accent, background, icon = accents.get(tone, accents["info"])
    st.markdown(
        (
            f"<div style='border:1px solid {accent}55;border-left:4px solid {accent};"
            f"border-radius:14px;padding:0.9rem 1rem;margin:0.15rem 0 0.85rem 0;background:{background};'>"
            f"<div style='font-size:0.84rem;color:#9db0c9;margin-bottom:0.3rem;'>{icon} {title}</div>"
            f"<div style='font-size:1.15rem;font-weight:700;color:#fafafa;'>{primary}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    if secondary:
        st.caption(secondary)
    if metrics:
        cols = st.columns(len(metrics))
        for col, (label, value, delta) in zip(cols, metrics):
            if delta is None:
                col.metric(label, value)
            else:
                col.metric(label, value, delta)


def render_trust_ribbon(items: list[tuple[str, str]]) -> None:
    if not items:
        return
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        col.caption(f"{label}: {value}")


def render_guidance_callout(title: str, body: str, tone: str = "info") -> None:
    message = f"**{title}** — {body}" if body else f"**{title}**"
    renderer = {
        "warning": st.warning,
        "success": st.success,
        "info": st.info,
    }.get(tone, st.info)
    renderer(message)


def apply_dark_chart_layout(
    fig: go.Figure,
    *,
    height: int | None = None,
    margin: dict | None = None,
    title: str | dict | None = None,
    showlegend: bool | None = None,
    transparent: bool = False,
    **extra_layout,
) -> go.Figure:
    background = "rgba(0,0,0,0)" if transparent else "#0e1117"
    layout: dict = {
        "template": "plotly_dark",
        "paper_bgcolor": background,
        "plot_bgcolor": background,
    }
    if height is not None:
        layout["height"] = height
    if margin is not None:
        layout["margin"] = margin
    if title is not None:
        layout["title"] = title
    if showlegend is not None:
        layout["showlegend"] = showlegend
    layout.update(extra_layout)
    fig.update_layout(**layout)
    return fig


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


def score_breakdown_bar(label: str, value: float, max_val: float | None = None) -> str:
    """Return an HTML mini progress bar for one score breakdown component.

    Renders as: [label 80px] [colored bar] [value right-aligned]
    Falls back to GREY bar when max_val is unknown.
    """
    effective_max = max_val if (max_val and max_val > 0) else _BREAKDOWN_MAXES.get(label, 10.0)
    pct = min(100, max(0, int(value / effective_max * 100)))
    if pct >= 75:
        bar_color = GREEN
    elif pct >= 40:
        bar_color = YELLOW
    else:
        bar_color = RED
    return (
        f"<div style='display:flex;align-items:center;gap:8px;margin:2px 0;'>"
        f"<span style='width:76px;font-size:11px;color:#9db0c9;flex-shrink:0;'>{label}</span>"
        f"<div style='flex:1;background:#1e2533;border-radius:3px;height:7px;'>"
        f"<div style='width:{pct}%;background:{bar_color};border-radius:3px;height:7px;'></div>"
        f"</div>"
        f"<span style='width:34px;text-align:right;font-size:11px;color:#ccc;flex-shrink:0;'>{value:.1f}</span>"
        f"</div>"
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
        fut_dates  = vn_future_trading_dates(last_date, n_days)
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

    return apply_dark_chart_layout(
        fig,
        height=450,
        margin=dict(l=40, r=40, t=50, b=30),
        showlegend=False,
    )


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
    return apply_dark_chart_layout(
        fig,
        height=300,
        title=dict(text=title, font=dict(size=13)),
        margin=dict(l=30, r=30, t=50, b=10),
        polar=dict(
            bgcolor="#0e1117",
            radialaxis=dict(visible=True, range=[0, 10], color=GREY),
        ),
    )


# ─────────────────────────────────────────────────────────────
# WORLD MARKET SPARKLINES
# ─────────────────────────────────────────────────────────────
def world_sparkline(prices: list[float], color: str = BLUE) -> go.Figure:
    fig = go.Figure(go.Scatter(
        y=prices, mode="lines",
        line=dict(color=color, width=1.5),
    ))
    return apply_dark_chart_layout(
        fig,
        height=60,
        margin=dict(l=0, r=0, t=0, b=0),
        transparent=True,
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
