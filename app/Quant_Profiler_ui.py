#!/usr/bin/env python3
"""
Quant_Profiler_ui.py  —  Streamlit Web UI for Quant Profiler  v1.0
════════════════════════════════════════════════════════════════════
Run:
    streamlit run Quant_Profiler_ui.py
    -- or --
    python Quant_Profiler.py --web
"""

import os
import sys
import json
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ─── Import core logic from same directory ────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from Quant_Profiler import (
    fetch_ohlcv,
    fetch_ssi_realtime,
    calculate_indicators,
    analyse_ticker,
    async_fetch_many,
    save_profiler_audit,
    calculate_csad,
    compute_rolling_beta_5d,
    compute_market_breadth,
    HISTORY_DAYS,
    _last,
)
from portfolio_engine import (
    parse_portfolio_csv,
    classify_settlement_status,
    calculate_performance,
    build_portfolio_summary,
    T25ExitManager,
    generate_t_plus_recommendation,
    compute_ssi_score,
    _T_REC_GRADES,
    _T_REC_COLORS,
)
from forecast_engine import (
    promethee_ii_ranking,
    monte_carlo_projection,
    multi_horizon_forecast,
    train_lstm_model,
    _KERAS_AVAILABLE,
    _KERAS_BACKEND,
)
from smart_money_engine import (
    compute_smart_money_index,
    detect_vsa_patterns,
    detect_wyckoff_phase,
    forecast_weekly_direction,
)
from trend_warning_engine import (
    compute_trend_warning,
    UPTREND_STRENGTHENING, UPTREND_EXHAUSTING,
    DOWNTREND_STRENGTHENING, DOWNTREND_EXHAUSTING,
    RANGE_COMPRESSION, BREAKOUT_EMERGING,
    REVERSAL_WARNING_LOW_CONF, REVERSAL_WARNING_CONFIRMED,
    INSUFFICIENT_DATA,
)

# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Quant Profiler · VN Stock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Quant Profiler — Vietnam Stock Technical Analyser v1.0"},
)

# ═══════════════════════════════════════════════════════════════════════════════
#  CUSTOM CSS — trading terminal dark theme
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Variables ── */
:root {
  --bg:     #0e1117;
  --card:   #1a1f2e;
  --card2:  #141824;
  --border: #2d3347;
  --text:   #e2e8f0;
  --muted:  #94a3b8;
  --dim:    #475569;
  --green:  #22c55e;
  --red:    #ef4444;
  --orange: #f97316;
  --blue:   #3b82f6;
  --purple: #a855f7;
  --cyan:   #06b6d4;
  --gold:   #fbbf24;
  --mono:   'JetBrains Mono', 'Cascadia Code', Consolas, monospace;
}

/* ── Core ── */
body, .stApp { background: var(--bg); }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 1.2rem; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
  background: var(--card2);
  border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] .stButton button {
  border-radius: 6px;
  font-weight: 700;
  letter-spacing: .3px;
}

/* ── Tabs ── */
/* Prevent tabs from being clipped — allow the tab strip to scroll horizontally */
.stTabs [data-baseweb="tab-list"] {
  gap: 4px;
  background: transparent;
  flex-wrap: nowrap !important;   /* single row */
  overflow-x: auto !important;    /* scroll instead of clip */
  overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
  padding-bottom: 2px;            /* room for scrollbar on Chrome */
  -webkit-overflow-scrolling: touch;
}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { height: 4px; }
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-thumb {
  background: var(--border); border-radius: 2px;
}
.stTabs [data-baseweb="tab"] {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px 6px 0 0;
  padding: 7px 16px;
  font-weight: 600;
  font-size: 13px;
  letter-spacing: .4px;
  white-space: nowrap;          /* don't word-wrap ticker names */
  flex-shrink: 0;               /* don't shrink — allow scroll instead */
}
.stTabs [aria-selected="true"] {
  background: var(--card2) !important;
  border-bottom-color: var(--card2) !important;
}

/* ── Ticker chips bar (above tabs) ── */
.ticker-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  padding: 10px 2px 4px;
  margin-bottom: 4px;
}
.ticker-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: .4px;
  border: 1px solid var(--border);
  background: var(--card);
  cursor: default;
}
.chip-buy    { border-color:#16a34a; background:#14532d22; color:#4ade80; }
.chip-watchup{ border-color:#2563eb; background:#1e3a5f22; color:#60a5fa; }
.chip-neutral{ border-color:#334155; background:#1e1e2e22; color:#94a3b8; }
.chip-watchdn{ border-color:#ea580c; background:#43140722; color:#fb923c; }
.chip-sell   { border-color:#dc2626; background:#450a0a22; color:#f87171; }
.chip-err    { border-color:#475569; background:transparent; color:#64748b; }

/* ── Signal badges ── */
.badge {
  display: inline-block;
  padding: 4px 13px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .5px;
  vertical-align: middle;
}
.badge-buy    { background:#14532d; color:#4ade80; border:1px solid #16a34a; }
.badge-watchup{ background:#1e3a5f; color:#60a5fa; border:1px solid #2563eb; }
.badge-neutral{ background:#1e1e2e; color:#94a3b8; border:1px solid #334155; }
.badge-watchdn{ background:#431407; color:#fb923c; border:1px solid #ea580c; }
.badge-sell   { background:#450a0a; color:#f87171; border:1px solid #dc2626; }

/* ── Price header ── */
.price-header {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 22px;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 28px;
  flex-wrap: wrap;
}
.ph-label  { font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--muted); margin-bottom:3px; }
.ph-price  { font-size:30px; font-weight:800; font-family:var(--mono); letter-spacing:-1px; }
.ph-delta  { font-size:18px; font-weight:700; font-family:var(--mono); }
.col-pos   { color: var(--green); }
.col-neg   { color: var(--red);   }
.col-flat  { color: var(--muted); }
.warn-ceil { color:#ef4444; font-size:12px; font-weight:700; background:#450a0a44; border:1px solid #dc2626; border-radius:5px; padding:2px 8px; }
.ok-floor  { color:#22c55e; font-size:12px; font-weight:700; background:#14532d44; border:1px solid #16a34a; border-radius:5px; padding:2px 8px; }

/* ── Indicator cards ── */
.ind-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 13px 16px;
  text-align: center;
  min-height: 90px;
  height: auto;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  box-sizing: border-box;
  overflow: visible;
}
.ind-label { font-size:10px; text-transform:uppercase; letter-spacing:.7px; color:var(--muted); margin-bottom:5px; }
.ind-value { font-size:22px; font-weight:700; font-family:var(--mono); line-height:1; }
.ind-note  { font-size:11px; color:var(--muted); margin-top:4px; }
.col-green  { color: var(--green);  }
.col-red    { color: var(--red);    }
.col-orange { color: var(--orange); }
.col-blue   { color: var(--blue);   }
.col-purple { color: var(--purple); }
.col-cyan   { color: var(--cyan);   }
.col-white  { color: var(--text);   }
.col-gold   { color: var(--gold);   }
.col-pos    { color: var(--green);  }
.col-neg    { color: var(--red);    }
.col-flat   { color: var(--muted);  }

/* ── MA table ── */
.ma-table { width:100%; border-collapse:collapse; font-size:13px; }
.ma-table th {
  background: var(--card);
  padding: 8px 12px;
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .8px;
  color: var(--muted);
  border-bottom: 2px solid var(--border);
}
.ma-table td { padding: 8px 12px; border-bottom: 1px solid #1e2535; font-family: var(--mono); }
.ma-table tr:last-child td { border-bottom: none; }
.ma-table tr:hover td { background: rgba(255,255,255,.025); }

/* ── Trade plan ── */
.trade-box {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.trade-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #1e2535;
  font-size: 13.5px;
}
.trade-row:last-child { border-bottom: none; }
.trade-lbl { color: var(--muted); font-size: 12px; }
.trade-val { font-weight: 700; font-family: var(--mono); }

/* ── Commentary ── */
.commentary {
  background: var(--card2);
  border-left: 3px solid var(--blue);
  border-radius: 0 8px 8px 0;
  padding: 14px 18px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--text);
}
.conf-badge {
  display: inline-block;
  background: #1e3a5f;
  color: #93c5fd;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 11px;
  font-weight: 600;
  margin: 2px 3px 6px 0;
}

/* ── Summary table ── */
.sum-table { width:100%; border-collapse:collapse; font-size:13px; }
.sum-table th {
  background: var(--card);
  padding: 10px 14px;
  text-align: left;
  font-size: 11px;
  letter-spacing: .8px;
  text-transform: uppercase;
  color: var(--muted);
  border-bottom: 2px solid var(--border);
}
.sum-table td { padding: 10px 14px; border-bottom: 1px solid #1e2535; }
.sum-table td:nth-child(2),
.sum-table td:nth-child(3),
.sum-table td:nth-child(4),
.sum-table td:nth-child(5),
.sum-table td:nth-child(6),
.sum-table td:nth-child(7) { font-family: var(--mono); }
.sum-table tr:last-child td { border-bottom:none; }
.sum-table tr:hover td { background: rgba(255,255,255,.025); }

/* ── Welcome screen ── */
.welcome-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  max-width: 720px;
  margin: 28px auto 0;
}
.welcome-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px;
}
.welcome-icon { font-size:28px; margin-bottom:8px; }
.welcome-title { font-weight:700; margin-bottom:6px; }
.welcome-body { font-size:13px; color:var(--muted); line-height: 1.7; }

/* ── Divider ── */
hr { border-color: var(--border); }

/* ── Streamlit wrapper overrides ── */
/* Remove default bottom margin Streamlit adds inside columns/markdown */
[data-testid="stMarkdownContainer"] {
  width: 100%;
}
[data-testid="stMarkdownContainer"] > div {
  margin-bottom: 0 !important;
}
/* Neutralise Streamlit's own <p> margin inside our custom HTML cards */
[data-testid="stMarkdownContainer"] .ind-card p,
[data-testid="stMarkdownContainer"] .trade-box p,
[data-testid="stMarkdownContainer"] .commentary p {
  margin: 0 !important;
  padding: 0 !important;
}

/* ── Block container — tighten side padding in wide layout ── */
.block-container {
  padding-top: 1.2rem !important;
  padding-left: 1rem !important;
  padding-right: 1rem !important;
  max-width: 100% !important;
}

/* ── Override Streamlit default table CSS with higher specificity ── */
[data-testid="stMarkdownContainer"] table.ma-table {
  width: 100% !important;
  border-collapse: collapse !important;
  font-size: 13px !important;
  background: transparent !important;
  margin: 0 !important;
}
[data-testid="stMarkdownContainer"] table.ma-table th {
  background: var(--card) !important;
  padding: 8px 12px !important;
  text-align: left !important;
  font-size: 11px !important;
  text-transform: uppercase;
  letter-spacing: .8px;
  color: var(--muted) !important;
  border: none !important;
  border-bottom: 2px solid var(--border) !important;
}
[data-testid="stMarkdownContainer"] table.ma-table td {
  padding: 8px 12px !important;
  border: none !important;
  border-bottom: 1px solid #1e2535 !important;
  font-family: var(--mono) !important;
  background: transparent !important;
}
[data-testid="stMarkdownContainer"] table.ma-table tr:last-child td {
  border-bottom: none !important;
}
[data-testid="stMarkdownContainer"] table.sum-table {
  width: 100% !important;
  border-collapse: collapse !important;
  font-size: 13px !important;
  background: transparent !important;
  margin: 0 !important;
}
[data-testid="stMarkdownContainer"] table.sum-table th {
  background: var(--card) !important;
  padding: 10px 14px !important;
  text-align: left !important;
  font-size: 11px !important;
  letter-spacing: .8px;
  text-transform: uppercase;
  color: var(--muted) !important;
  border: none !important;
  border-bottom: 2px solid var(--border) !important;
}
[data-testid="stMarkdownContainer"] table.sum-table td {
  padding: 10px 14px !important;
  border: none !important;
  border-bottom: 1px solid #1e2535 !important;
  background: transparent !important;
}
[data-testid="stMarkdownContainer"] table.sum-table tr:last-child td {
  border-bottom: none !important;
}
/* ── Filterable-table: per-column filter row ────────────────────── */
tr.flt-row th { padding: 3px 2px !important; background: #0d1224; }
tr.flt-row th input {
  width: 100%;
  min-width: 30px;
  background: #141824;
  border: 1px solid #2d3347;
  border-radius: 4px;
  color: #e2e8f0;
  font-size: 10px;
  padding: 3px 5px;
  outline: none;
  box-sizing: border-box;
}
tr.flt-row th input::placeholder { color: #475569; font-size: 10px; }
tr.flt-row th input:focus { border-color: #3b82f6; }
tr.tbl-hidden { display: none !important; }
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def cached_analyse(symbol: str, days: int) -> tuple:
    """Fetch + indicators + signal. Cached 5 min. Returns (result_dict, df)."""
    result, df = analyse_ticker(symbol, days, verbose=False, return_df=True)
    return result, df


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _badge(signal: str) -> str:
    _cls = {
        "MUA":           "badge-buy",
        "THEO DÕI–TĂNG": "badge-watchup",
        "TRUNG LẬP":     "badge-neutral",
        "THEO DÕI–GIẢM": "badge-watchdn",
        "BÁN / TRÁNH":   "badge-sell",
    }
    return f'<span class="badge {_cls.get(signal, "badge-neutral")}">{signal}</span>'


_T25_COLOR = {
    "T25_BUY":     "#22c55e",
    "T25_WATCH":   "#3b82f6",
    "T25_NEUTRAL": "#94a3b8",
    "T25_AVOID":   "#ef4444",
}


def _t25_badge(signal: str, score) -> str:
    """Render a colored pill badge for a T+2.5 signal."""
    _label = {"T25_BUY": "MUA", "T25_WATCH": "THEO DÕI", "T25_NEUTRAL": "TB", "T25_AVOID": "TRÁNH"}
    c = _T25_COLOR.get(signal, "#475569")
    lbl = _label.get(signal, signal or "–")
    sc_str = f" {int(score)}" if score is not None and signal in ("T25_BUY", "T25_WATCH") else ""
    return (
        f'<span style="background:{c}22;border:1px solid {c};color:{c};'
        f'border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700;">'
        f'{lbl}{sc_str}</span>'
    )


def _f(v, d=0) -> str:
    if v is None: return "–"
    return f"{v:,.{d}f}"


def _pct(v) -> str:
    if v is None: return ""
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


def _pct_cls(v) -> str:
    if v is None or v == 0: return "col-flat"
    return "col-pos" if v > 0 else "col-neg"


def _rsi_cls(v) -> str:
    if v is None: return "col-white"
    if v < 30:    return "col-green"
    if v < 40:    return "col-blue"
    if v > 70:    return "col-red"
    if v > 60:    return "col-orange"
    return "col-white"


def _stoch_cls(v) -> str:
    if v is None: return "col-white"
    if v < 20:    return "col-green"
    if v > 80:    return "col-red"
    return "col-white"


def _adx_cls(adx, pdi, ndi) -> str:
    if adx is None: return "col-white"
    if adx > 25:
        return "col-green" if (pdi or 0) > (ndi or 0) else "col-red"
    return "col-orange"


def _safe(s: str) -> str:
    """Sanitize a string for safe insertion into unsafe_allow_html HTML blocks."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ═══════════════════════════════════════════════════════════════════════════════
#  CHART
# ═══════════════════════════════════════════════════════════════════════════════
def build_chart(
    df: pd.DataFrame,
    result: dict,
    show_bb: bool = True,
    show_ema: bool = False,
    show_levels: bool = True,
) -> go.Figure:
    """4-panel: Candlestick+MA  /  Volume  /  RSI  /  MACD."""
    df_c = df.tail(180).copy()  # last 180 bars for clarity

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.018,
        row_heights=[0.54, 0.15, 0.155, 0.155],
        subplot_titles=["", "Volume", "RSI (14)", "MACD (12·26·9)"],
    )

    # ── Row 1: Candlestick ───────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df_c.index, open=df_c["Open"], high=df_c["High"],
        low=df_c["Low"], close=df_c["Close"],
        name="Price",
        increasing_line_color="#22c55e", increasing_fillcolor="#22c55e",
        decreasing_line_color="#ef4444", decreasing_fillcolor="#ef4444",
        line_width=1,
    ), row=1, col=1)

    # SMA lines
    _sma_cfg = [(20, "#f97316", 1.5), (50, "#3b82f6", 1.5), (200, "#a855f7", 2.0)]
    for period, color, width in _sma_cfg:
        col = f"SMA{period}"
        if col in df_c.columns:
            fig.add_trace(go.Scatter(
                x=df_c.index, y=df_c[col],
                name=f"SMA{period}", line=dict(color=color, width=width), opacity=0.9,
            ), row=1, col=1)

    # EMA lines (optional)
    if show_ema:
        _ema_cfg = [("EMA9", "#06b6d4", 1.0, "dot"), ("EMA21", "#f43f5e", 1.0, "dot")]
        for col, color, width, dash in _ema_cfg:
            if col in df_c.columns:
                fig.add_trace(go.Scatter(
                    x=df_c.index, y=df_c[col],
                    name=col, line=dict(color=color, width=width, dash=dash), opacity=0.75,
                ), row=1, col=1)

    # Bollinger Bands (optional)
    if show_bb and "BB_Upper" in df_c.columns:
        fig.add_trace(go.Scatter(
            x=df_c.index, y=df_c["BB_Upper"],
            name="BB+", line=dict(color="rgba(148,163,184,0.45)", width=1),
            showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df_c.index, y=df_c["BB_Lower"],
            name="BB–", line=dict(color="rgba(148,163,184,0.45)", width=1),
            fill="tonexty", fillcolor="rgba(148,163,184,0.06)",
            showlegend=False,
        ), row=1, col=1)

    # Entry / SL / TP horizontal lines  (yref="y" = price subplot axis)
    if show_levels:
        _levels = [
            (result.get("entry"), "#fbbf24", "Entry"),
            (result.get("sl"),    "#ef4444", "SL"),
            (result.get("tp1"),   "#22c55e", "TP1"),
            (result.get("tp2"),   "#4ade80", "TP2"),
        ]
        for y_val, color, label in _levels:
            if y_val:
                # xref="paper" spans full width; yref="y" pins to price-panel y axis
                fig.add_shape(
                    type="line",
                    xref="paper", yref="y",
                    x0=0, x1=1, y0=y_val, y1=y_val,
                    line=dict(color=color, width=1, dash="dash"),
                )
                fig.add_annotation(
                    xref="paper", yref="y",
                    x=1.002, y=y_val,
                    text=f"{label}  {y_val:,.0f}",
                    showarrow=False,
                    xanchor="left", yanchor="middle",
                    font=dict(color=color, size=10),
                )

    # ── Row 2: Volume ────────────────────────────────────────────────────────
    vol_colors = [
        "#22c55e" if df_c["Close"].iloc[i] >= df_c["Open"].iloc[i] else "#ef4444"
        for i in range(len(df_c))
    ]
    fig.add_trace(go.Bar(
        x=df_c.index, y=df_c["Volume"],
        name="Vol", marker_color=vol_colors, opacity=0.65, showlegend=False,
    ), row=2, col=1)
    if "Vol_MA20" in df_c.columns:
        fig.add_trace(go.Scatter(
            x=df_c.index, y=df_c["Vol_MA20"],
            name="Vol MA", line=dict(color="#f97316", width=1.2), showlegend=False,
        ), row=2, col=1)

    # ── Row 3: RSI ───────────────────────────────────────────────────────────
    if "RSI" in df_c.columns:
        fig.add_trace(go.Scatter(
            x=df_c.index, y=df_c["RSI"],
            name="RSI", line=dict(color="#e879f9", width=1.5), showlegend=False,
        ), row=3, col=1)
        for lvl, clr in [(70, "rgba(239,68,68,0.35)"), (30, "rgba(34,197,94,0.35)"),
                         (50, "rgba(148,163,184,0.2)")]:
            fig.add_hline(y=lvl, line_dash="dash", line_color=clr, row=3, col=1)
        fig.add_hrect(y0=30, y1=70, fillcolor="rgba(251,191,36,0.03)", row=3, col=1)

    # ── Row 4: MACD ──────────────────────────────────────────────────────────
    if "MACD" in df_c.columns and "MACD_Signal" in df_c.columns:
        hist = df_c["MACD_Hist"].fillna(0)
        hist_colors = ["#22c55e" if v >= 0 else "#ef4444" for v in hist]
        fig.add_trace(go.Bar(
            x=df_c.index, y=hist,
            marker_color=hist_colors, opacity=0.7, showlegend=False,
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=df_c.index, y=df_c["MACD"],
            name="MACD", line=dict(color="#06b6d4", width=1.5), showlegend=False,
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=df_c.index, y=df_c["MACD_Signal"],
            name="Sig", line=dict(color="#f97316", width=1.2), showlegend=False,
        ), row=4, col=1)

    # ── Layout ───────────────────────────────────────────────────────────────
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0d1117",
        # Disable rangeslider on all x axes (shared_xaxes=True layout uses xaxis1..4)
        xaxis_rangeslider_visible=False,
        xaxis2_rangeslider_visible=False,
        xaxis3_rangeslider_visible=False,
        xaxis4_rangeslider_visible=False,
        height=700,
        margin=dict(l=10, r=150, t=30, b=10),
        font=dict(family="JetBrains Mono, Consolas, monospace", size=11, color="#94a3b8"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)", font=dict(size=11),
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1a1f2e", bordercolor="#2d3347", font_size=12),
    )
    for i in range(1, 5):
        fig.update_xaxes(
            showgrid=True, gridcolor="#1a2030", gridwidth=1,
            zeroline=False, showline=False, tickfont=dict(size=10),
            row=i, col=1,
        )
        fig.update_yaxes(
            showgrid=True, gridcolor="#1a2030", gridwidth=1,
            zeroline=False, showline=False, tickfont=dict(size=10),
            side="right", row=i, col=1,
        )
    # Also enforce rangeslider=False via bulk update (belt-and-braces)
    fig.update_xaxes(rangeslider_visible=False)
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)
    fig.update_xaxes(showticklabels=False, row=3, col=1)
    fig.update_yaxes(range=[0, 100], row=3, col=1)

    # Subplot title style
    for ann in fig.layout.annotations:
        ann.font.update(size=10, color="#475569")
        ann.x = 0.01
        ann.xanchor = "left"

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION RENDERERS
# ═══════════════════════════════════════════════════════════════════════════════

def render_price_header(r: dict) -> None:
    price = r.get("price")
    pct   = r.get("pct_change", 0.0)
    ref   = r.get("reference")
    ceil_ = r.get("ceiling")
    flr   = r.get("floor")
    atr   = r.get("atr")
    src   = r.get("ohlcv_src", "–")
    bars  = r.get("bars", 0)
    ldate = r.get("last_date", "")
    sig   = r.get("signal", "")

    p_cls = _pct_cls(pct)
    ceil_flag = '<span class="warn-ceil">⚠ TẠI TRẦN</span>' if r.get("at_ceiling") else ""
    flr_flag  = '<span class="ok-floor">✅ TẠI SÀN</span>'  if r.get("at_floor")   else ""
    _rkey       = r.get("regime", "")
    _rcss       = {"BULL_TREND": "col-green", "BEAR_TREND": "col-red",
                   "HIGH_VOL":   "col-orange", "SIDEWAYS":   "col-white"}.get(_rkey, "")
    regime_html = (f'<span class="{_rcss}" style="font-size:12px;font-weight:600;">'
                   f'【{r.get("regime_label", "")}】</span>') if r.get("regime_label") else ""
    conf_flag   = ('<span style="font-size:11px;color:#f97316;font-weight:600;">⚡ Chưa xác nhận</span>'
                   if not r.get("signal_confirmed", True) else "")

    # ── Phase 5: new indicator chips ─────────────────────────────────────────
    _rs_r   = int(r.get("rs_rating") or 0)
    _rs_c   = "#22c55e" if _rs_r >= 70 else "#f97316" if _rs_r >= 50 else "#ef4444"
    _rs_chip = (f'<span style="background:{_rs_c}22;border:1px solid {_rs_c};color:{_rs_c};'
                f'border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700;">'
                f'RS {_rs_r}</span>') if _rs_r else ""
    _sl     = r.get("structure_label", "")
    _sl_c   = "#22c55e" if "HH+HL" in _sl else "#ef4444" if "LH+LL" in _sl else "#94a3b8"
    _sl_chip = (f'<span style="background:{_sl_c}22;border:1px solid {_sl_c};color:{_sl_c};'
                f'border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700;">'
                f'{_sl}</span>') if _sl else ""
    _gtype  = r.get("gap_type", "NO_GAP")
    _gp_pct = float(r.get("gap_pct") or 0)
    _gp_c   = "#22c55e" if _gtype == "GAP_UP" else "#ef4444" if _gtype == "GAP_DOWN" else "#64748b"
    _gp_chip = (f'<span style="background:{_gp_c}22;border:1px solid {_gp_c};color:{_gp_c};'
                f'border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700;">'
                f'{_gtype} {_gp_pct:+.1f}%</span>') if _gtype != "NO_GAP" else ""
    _ssi    = compute_ssi_score(r)
    _ssi_v  = _ssi.get("ssi", 0)
    _ssi_col= _ssi.get("ssi_color", "#94a3b8")
    _ssi_g  = _ssi.get("ssi_grade", "?")
    _ssi_chip = (f'<span style="background:{_ssi_col}22;border:1px solid {_ssi_col};color:{_ssi_col};'
                 f'border-radius:999px;padding:2px 10px;font-size:11px;font-weight:800;">'
                 f'SSI {_ssi_v} · {_ssi_g}</span>')
    _new_chips_html = (
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px;">'
        f'{_rs_chip}{_sl_chip}{_gp_chip}{_ssi_chip}</div>'
    )

    st.markdown(f"""
<div class="price-header">
  <div>
    <div class="ph-label">Mã · Tín hiệu</div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:3px;">
      <span style="font-size:26px;font-weight:800;">{_safe(r['ticker'])}</span>
      {_badge(sig)} {regime_html} {conf_flag} {ceil_flag}{flr_flag}
    </div>
    {_new_chips_html}
  </div>
  <div>
    <div class="ph-label">Giá hiện tại</div>
    <div class="ph-price">{_f(price)}</div>
  </div>
  <div>
    <div class="ph-label">Thay đổi</div>
    <div class="ph-delta {p_cls}">{_pct(pct)}</div>
  </div>
  <div>
    <div class="ph-label">Tham chiếu</div>
    <div style="font-size:17px;font-weight:700;font-family:var(--mono);">{_f(ref)}</div>
  </div>
  <div>
    <div class="ph-label">Trần / Sàn</div>
    <div style="font-size:15px;font-family:var(--mono);">
      <span class="col-red">{_f(ceil_)}</span>
      <span style="color:var(--dim);"> / </span>
      <span class="col-green">{_f(flr)}</span>
    </div>
  </div>
  <div>
    <div class="ph-label">ATR (14)</div>
    <div style="font-size:15px;font-weight:600;font-family:var(--mono);color:var(--cyan);">{_f(atr)}</div>
  </div>
  <div style="margin-left:auto;text-align:right;">
    <div class="ph-label">Nguồn · Nến</div>
    <div style="font-size:12px;color:var(--muted);">{src} · {bars} bars</div>
    <div style="font-size:11px;color:var(--dim);">{ldate}</div>
  </div>
</div>
""", unsafe_allow_html=True)


def render_indicator_cards(r: dict) -> None:
    """Two rows of 4 indicator cards each."""
    rsi     = r.get("rsi")
    stk     = r.get("stoch_k")
    std     = r.get("stoch_d")
    adx     = r.get("adx")
    pdi     = r.get("pdi", 0) or 0
    ndi     = r.get("ndi", 0) or 0
    macd    = r.get("macd", 0) or 0
    mac_s   = r.get("macd_signal", 0) or 0
    atr     = r.get("atr")
    wr      = r.get("williams_r")
    cci     = r.get("cci")
    bull_p  = r.get("bull_pct", 50)
    kl      = r.get("kl_ratio")

    # Derived labels
    rsi_note  = ("Quá bán↑" if rsi and rsi < 30 else "Gần QBán"  if rsi and rsi < 40
                 else "Quá mua↓" if rsi and rsi > 70 else "Gần QMua"  if rsi and rsi > 60
                 else "Trung tính")
    stk_note  = ("Quá bán↑" if stk and stk < 20 else "Quá mua↓" if stk and stk > 80
                 else f"D = {_f(std, 1)}")
    adx_note  = ("↑ Xu hướng tăng" if adx and adx > 25 and pdi > ndi
                 else "↓ Xu hướng giảm" if adx and adx > 25 and ndi >= pdi
                 else "Đang hình thành" if adx and adx > 20 else "Đi ngang")
    macd_up   = macd > mac_s
    macd_lbl  = f"{'↑ Dương' if macd_up else '↓ Âm'}"
    macd_cls  = "col-green" if macd_up else "col-red"
    wr_note   = "Quá bán↑" if wr and wr < -80 else "Quá mua↓" if wr and wr > -20 else "Bình thường"
    cci_note  = "Quá bán↑" if cci and cci < -100 else "Quá mua↓" if cci and cci > 100 else "Trung tính"
    cci_cls   = "col-green" if cci and cci < -100 else "col-red" if cci and cci > 100 else "col-white"
    wr_cls    = "col-green" if wr and wr < -80 else "col-red" if wr and wr > -20 else "col-white"
    bull_color = ("#22c55e" if bull_p >= 60 else "#ef4444" if bull_p <= 40 else "#f97316")
    kl_str    = f"{kl:.1f}×" if kl else "–"
    kl_cls    = "col-green" if kl and kl >= 1.5 else "col-orange" if kl and kl >= 1.0 else "col-red"

    def _card(label, val_html, note=""):
        return f"""<div class="ind-card">
  <div class="ind-label">{label}</div>
  <div class="ind-value">{val_html}</div>
  <div class="ind-note">{note}</div>
</div>"""

    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    r2c1, r2c2, r2c3, r2c4 = st.columns(4)

    with r1c1:
        st.markdown(_card("RSI (14)",
            f'<span class="{_rsi_cls(rsi)}">{_f(rsi, 1)}</span>', rsi_note),
            unsafe_allow_html=True)
    with r1c2:
        st.markdown(_card("Stoch %K",
            f'<span class="{_stoch_cls(stk)}">{_f(stk, 1)}</span>', stk_note),
            unsafe_allow_html=True)
    with r1c3:
        st.markdown(_card("ADX (14)",
            f'<span class="{_adx_cls(adx, pdi, ndi)}">{_f(adx, 1)}</span>', adx_note),
            unsafe_allow_html=True)
    with r1c4:
        st.markdown(_card("MACD",
            f'<span class="{macd_cls}">{macd_lbl}</span>',
            f"Hist = {_f(r.get('macd_hist'), 0)}"),
            unsafe_allow_html=True)

    with r2c1:
        st.markdown(_card("ATR (14)",
            f'<span class="col-cyan">{_f(atr, 0)}</span>', "Biến động/ngày"),
            unsafe_allow_html=True)
    with r2c2:
        st.markdown(_card("Williams %R",
            f'<span class="{wr_cls}">{_f(wr, 1)}</span>', wr_note),
            unsafe_allow_html=True)
    with r2c3:
        st.markdown(_card("CCI (20)",
            f'<span class="{cci_cls}">{_f(cci, 0)}</span>', cci_note),
            unsafe_allow_html=True)
    with r2c4:
        st.markdown(_card("KL / Vol MA20",
            f'<span class="{kl_cls}">{kl_str}</span>',
            f"Bull {bull_p:.0f}% / Bear {100-bull_p:.0f}%"),
            unsafe_allow_html=True)

    # Row 3 — VSA (Wyckoff Volume Spread Analysis)
    vsa_state = r.get("vsa_state", "NEUTRAL") or "NEUTRAL"
    vsa_score = r.get("vsa_score", 0) or 0
    vsa_css = {
        "ACCUM":     "col-green",
        "NO_SUPPLY": "col-cyan",
        "DISTRIB":   "col-red",
        "NO_DEMAND": "col-orange",
        "NEUTRAL":   "col-white",
    }.get(vsa_state, "col-white")
    vsa_note = {
        "ACCUM":     "Tích lũy (Wyckoff) — bullish",
        "DISTRIB":   "Phân phối (Wyckoff) — bearish",
        "NO_DEMAND": "Không có cầu — fade rally",
        "NO_SUPPLY": "Cạn cung — hỗ trợ pullback",
        "NEUTRAL":   "Không có tín hiệu VSA rõ",
    }.get(vsa_state, "")
    r3c1, r3c2, r3c3, r3c4 = st.columns(4)
    with r3c1:
        st.markdown(_card("VSA (Wyckoff)",
            f'<span class="{vsa_css}">{vsa_state}</span>',
            vsa_note),
            unsafe_allow_html=True)
    with r3c2:
        vsa_score_cls = "col-green" if vsa_score > 0 else "col-red" if vsa_score < 0 else "col-white"
        st.markdown(_card("VSA Score",
            f'<span class="{vsa_score_cls}">{vsa_score:+.1f}</span>',
            "−1 (distrib) → +1 (accum)"),
            unsafe_allow_html=True)
    with r3c3:
        _rk   = r.get("regime", "UNKNOWN")
        _rl   = r.get("regime_label") or "–"
        _rs   = r.get("regime_score", 0) or 0
        _reg_css = {"BULL_TREND": "col-green", "BEAR_TREND": "col-red",
                    "HIGH_VOL": "col-orange", "SIDEWAYS": "col-white"
                    }.get(_rk, "col-white")
        st.markdown(_card("🌍 Xu hưới thị trường",
            f'<span class="{_reg_css}" style="font-size:16px;">{_rl}</span>',
            f"Score: {_rs:+d} (−2 BEAR → +2 BULL)"),
            unsafe_allow_html=True)
    with r3c4:
        _slope = r.get("sma200_slope", 0.0) or 0.0
        _scls  = "col-green" if _slope > 0.3 else "col-red" if _slope < -0.3 else "col-orange"
        _snote = "↑ Tăng" if _slope > 0.3 else "↓ Giảm" if _slope < -0.3 else "→ Đi ngang"
        st.markdown(_card("SMA200 Slope",
            f'<span class="{_scls}">{_slope:+.2f}%</span>',
            f"{_snote} (20 phiên)"),
            unsafe_allow_html=True)

    # Row 4 — VWAP, RS Rating, Price Structure, SSI
    r4c1, r4c2, r4c3, r4c4 = st.columns(4)
    with r4c1:
        _vwap_v = r.get("vwap")
        _pvp    = float(r.get("price_vs_vwap_pct") or 0)
        _vwap_c = "col-green" if _pvp > 0 else "col-red"
        st.markdown(_card("VWAP (20-bar)",
            f'<span class="col-cyan">{_f(_vwap_v, 0) if _vwap_v else "–"}</span>',
            f"Giá {'trên' if _pvp>0 else 'dưới'} VWAP {abs(_pvp):.1f}%"),
            unsafe_allow_html=True)
    with r4c2:
        _rs_rat = int(r.get("rs_rating") or 0)
        _rs_c   = "col-green" if _rs_rat >= 70 else "col-orange" if _rs_rat >= 50 else "col-red"
        st.markdown(_card("RS Rating (1-99)",
            f'<span class="{_rs_c}">{_rs_rat}</span>',
            "vs VNINDEX 90 ngày"),
            unsafe_allow_html=True)
    with r4c3:
        _stl   = r.get("structure_label", "NEUTRAL") or "NEUTRAL"
        _stc   = "col-green" if "HH+HL" in _stl else "col-red" if "LH+LL" in _stl else "col-white"
        _stbar = r.get("structure_bars", 10) or 10
        st.markdown(_card("Cấu trúc giá",
            f'<span class="{_stc}">{_stl}</span>',
            f"lookback {_stbar} nến"),
            unsafe_allow_html=True)
    with r4c4:
        _ssi_d = compute_ssi_score(r)
        _sv    = _ssi_d.get("ssi", 0)
        _sg    = _ssi_d.get("ssi_grade", "?")
        _sc_s  = _ssi_d.get("ssi_color", "#94a3b8")
        st.markdown(_card("SSI (F15)",
            f'<span style="color:{_sc_s};font-weight:900;font-size:22px;">{_sv}</span>',
            f"Grade: {_sg} | Swing Strength"),
            unsafe_allow_html=True)


def render_ma_table(r: dict) -> None:
    price = r.get("price") or 0
    rows  = ""
    for lbl, key in [
        ("SMA 20",  "sma20"), ("SMA 50",  "sma50"), ("SMA 200", "sma200"),
        ("EMA 9",   "ema9"),  ("EMA 21",  "ema21"),
        ("BB Trên", "bb_upper"), ("BB Mid", "bb_mid"), ("BB Dưới", "bb_lower"),
    ]:
        v = r.get(key)
        if v is None:
            continue
        pct_v = (v - price) / price * 100 if price else 0
        pos   = "↑ Trên" if price > v else "↓ Dưới"
        pcls  = "col-green" if price > v else "col-red"
        rows += (
            f'<tr><td style="color:var(--muted);">{lbl}</td>'
            f'<td>{v:,.0f}</td>'
            f'<td class="{pcls}">{pct_v:+.2f}%</td>'
            f'<td class="{pcls}">{pos}</td></tr>'
        )
    st.markdown(f"""
<table class="ma-table">
  <thead><tr><th>MA</th><th>Giá trị</th><th>vs Giá</th><th>Vị trí</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
""", unsafe_allow_html=True)


def render_trade_plan(r: dict) -> None:
    entry = r.get("entry")
    sl    = r.get("sl")
    tp1   = r.get("tp1")
    tp2   = r.get("tp2")
    rr    = r.get("rr1")

    if not (entry and sl and tp1):
        st.markdown("_Không đủ dữ liệu ATR để tính Entry / SL / TP._")
        return

    def _row(lbl, val, vcls="col-white"):
        return (f'<div class="trade-row"><span class="trade-lbl">{lbl}</span>'
                f'<span class="trade-val {vcls}">{val:,.0f}</span></div>')

    rr_str = f"{rr:.1f} : 1" if rr else "–"
    atr    = r.get("atr", 0)

    st.markdown(f"""
<div class="trade-box">
  {_row("📍 Entry  (giá hiện tại)", entry, "col-gold")}
  {_row("🛑 SL  (Entry − ATR × 1.5)",  sl,   "col-red")}
  {_row("🎯 TP1  (Entry + ATR × 2.0)", tp1,  "col-cyan")}
  {_row("🎯 TP2  (Entry + ATR × 3.5)", tp2,  "col-green")}
  <div class="trade-row">
    <span class="trade-lbl">⚖ Risk / Reward</span>
    <span class="trade-val col-cyan">{rr_str}</span>
  </div>
  <div class="trade-row" style="border-bottom:none;">
    <span class="trade-lbl">📐 ATR (14)</span>
    <span class="trade-val col-white">{_f(atr, 0)}</span>
  </div>
</div>
""", unsafe_allow_html=True)


def render_commentary(r: dict) -> None:
    confirms = r.get("confirmations", [])
    text     = r.get("commentary", "")
    conf_html = "".join(f'<span class="conf-badge">{c}</span>' for c in confirms)
    body = "<br>".join(text.split("\n"))
    st.markdown(f"""
<div class="commentary">
  <div style="margin-bottom:8px;">{conf_html}</div>
  {body}
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  MONTE CARLO FAN CHART
# ═══════════════════════════════════════════════════════════════════════════════


def render_monte_carlo(r: dict, df: pd.DataFrame) -> None:
    """Monte Carlo 10 000-path fan chart for the next 5 trading days."""
    price = r.get("price") or 0
    atr   = r.get("atr")   or 0
    if price <= 0 or atr <= 0:
        return

    mc = monte_carlo_projection(price, atr, days=5, sims=10_000)
    pp = mc.get("percentile_paths", {})
    if not pp:
        return

    days_x = [f"T+{d+1}" for d in range(5)]
    p5  = [price] + pp["p5"]
    p50 = [price] + pp["p50"]
    p95 = [price] + pp["p95"]
    x_axis = ["T+0"] + days_x

    fig = go.Figure()
    # P5-P95 band
    fig.add_trace(go.Scatter(
        x=x_axis + x_axis[::-1],
        y=p95 + p5[::-1],
        fill="toself",
        fillcolor="rgba(59,130,246,0.12)",
        line=dict(color="rgba(0,0,0,0)"),
        showlegend=True,
        name="Dải P5–P95",
    ))
    # P5 line
    fig.add_trace(go.Scatter(
        x=x_axis, y=p5,
        line=dict(color="#ef4444", width=1.5, dash="dot"),
        name=f"P5 (xấu nhất): {mc['p5_downside']:,.0f}",
    ))
    # P50 median
    fig.add_trace(go.Scatter(
        x=x_axis, y=p50,
        line=dict(color="#60a5fa", width=2),
        name=f"P50 (kỳ vọng): {mc['expected_price']:,.0f}",
    ))
    # P95 line
    fig.add_trace(go.Scatter(
        x=x_axis, y=p95,
        line=dict(color="#22c55e", width=1.5, dash="dot"),
        name=f"P95 (tốt nhất): {mc['p95_upside']:,.0f}",
    ))
    # Current price reference
    fig.add_hline(
        y=price,
        line=dict(color="#94a3b8", width=1, dash="dash"),
        annotation_text=f"Hiện tại: {price:,.0f}",
        annotation_position="bottom left",
    )
    fig.update_layout(
        title=dict(
            text=f"🎲 Monte Carlo — 10,000 kịch bản  ·  {r['ticker']}  ·  MDD P5: {mc['max_drawdown_p5']:+.1f}%",
            font=dict(size=13),
        ),
        height=280,
        margin=dict(t=40, b=30, l=10, r=10),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="#e2e8f0", size=11),
        legend=dict(orientation="h", y=-0.15),
        xaxis=dict(gridcolor="#1e2535"),
        yaxis=dict(gridcolor="#1e2535", tickformat=",.0f"),
    )
    with st.expander(
        f"🎲 Monte Carlo Projection  ·  P5={mc['p5_downside']:,.0f}  P50={mc['expected_price']:,.0f}  P95={mc['p95_upside']:,.0f}  ·  Vol={mc['vol_used']:.2f}%/ngày",
        expanded=False,
    ):
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                        key=f"mc_{r['ticker']}")
        st.caption(
            "⚠️ Phương pháp: Geometric Brownian Motion (GBM). "
            "Vol = ATR/Giá (độ biến động ngày). Không tính drift (giả định trung lập). "
            "P5 dùng làm ngưỡng cắt lỗ xác suất cao nhất. Bố tế bào: 10.000 đường giá."
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  MULTI-HORIZON FORECAST PANEL
# ═══════════════════════════════════════════════════════════════════════════════

_HORIZON_CSS = """
<style>
.horizon-card {
  background: #141824;
  border: 1px solid #2d3347;
  border-radius: 10px;
  padding: 16px;
  height: 100%;
}
.horizon-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #94a3b8;
  margin-bottom: 10px;
}
.horizon-vote {
  font-size: 17px;
  font-weight: 800;
  margin-bottom: 6px;
}
.horizon-conf-bar {
  height: 6px;
  border-radius: 3px;
  background: #2d3347;
  margin-bottom: 10px;
}
.horizon-conf-fill {
  height: 6px;
  border-radius: 3px;
}
.horizon-reason {
  font-size: 11.5px;
  color: #94a3b8;
  line-height: 1.7;
  margin-bottom: 3px;
}
.lstm-box {
  background: #0e1117;
  border: 1px solid #2d3347;
  border-radius: 6px;
  padding: 8px 12px;
  margin-top: 10px;
  font-size: 12px;
}
</style>
"""


def _conf_color(conf: float) -> str:
    if conf >= 65:
        return "#22c55e"
    if conf >= 50:
        return "#3b82f6"
    if conf >= 35:
        return "#f97316"
    return "#ef4444"


def render_forecast_horizons(r: dict, df: pd.DataFrame) -> None:
    """3-column multi-horizon forecast panel with vote + confidence bars."""
    from pathlib import Path as _Path
    _ticker     = r.get("ticker", "")
    _mdl_path   = _Path(os.path.join(_DIR, "data", "models", f"{_ticker}_lstm.keras"))
    _mdl_exists = _mdl_path.exists()

    # ── Keras unavailability warning ─────────────────────────────────────────
    if not _KERAS_AVAILABLE:
        st.warning(
            "⚠️ **Keras chưa được cài đặt** — dự báo ML đang dùng **Ridge fallback**. "
            f"Cài đặt: `pip install tensorflow`"
            + (f"  *(backend phát hiện: `{_KERAS_BACKEND}`)*" if _KERAS_BACKEND else ""),
            icon="⚠️",
        )

    # ── LSTM status + Train/Retrain control ──────────────────────────────────
    _lc1, _lc2, _lc3 = st.columns([3, 2, 3])
    with _lc1:
        if not _KERAS_AVAILABLE:
            _badge_html = '❌ <b style="color:#ef4444;">Keras N/A</b> — Ridge fallback'
        elif _mdl_exists:
            _badge_html = f'🧠 <b style="color:#22c55e;">LSTM model</b> — {_ticker}_lstm.keras'
        else:
            _badge_html = f'📊 <b style="color:#f97316;">Ridge ML</b> — chưa có LSTM model cho {_ticker}'
        st.markdown(
            f'<div style="font-size:13px;padding:6px 0;">{_badge_html}</div>',
            unsafe_allow_html=True,
        )
    with _lc2:
        _retrain_btn = st.button(
            "🔄 Retrain LSTM" if _mdl_exists else "🧠 Train LSTM ngay",
            key=f"lstm_train_{_ticker}",
            type="secondary" if _mdl_exists else "primary",
            use_container_width=True,
            disabled=not _KERAS_AVAILABLE,
            help=(
                "Huấn luyện lại model LSTM với toàn bộ dữ liệu lịch sử."
                if _mdl_exists else
                "Huấn luyện model LSTM cục bộ. Mất ~10–20 giây (CPU). "
                "Sau khi xong, dự báo sẽ dùng LSTM thay Ridge."
            ),
        )
    with _lc3:
        if _mdl_exists:
            _ts     = _mdl_path.stat().st_mtime
            _ts_str = __import__("datetime").datetime.fromtimestamp(_ts).strftime("%d/%m/%Y %H:%M")
            st.caption(f"📅 Lần train cuối: {_ts_str}")
        elif _KERAS_AVAILABLE:
            st.caption("💡 Train LSTM để tăng độ chính xác dự báo.")

    # ── Live training with per-epoch progress bar ────────────────────────────
    if _retrain_btn and df is not None and not df.empty:
        _prog_placeholder = st.empty()
        _prog_placeholder.progress(0, text="⏳ Đang khởi tạo model...")

        def _on_epoch(epoch: int, total: int, logs: dict) -> None:
            pct      = min(int(epoch / total * 100), 99)
            mae_str  = (
                f"  ·  val_mae: {logs['val_mae']:.4f}"
                if "val_mae" in logs else ""
            )
            loss_str = (
                f"  ·  val_loss: {logs['val_loss']:.4f}"
                if "val_loss" in logs else ""
            )
            _prog_placeholder.progress(
                pct,
                text=f"🧠 Epoch {epoch}/{total}{loss_str}{mae_str}",
            )

        _trained = train_lstm_model(_ticker, df, force=True, progress_callback=_on_epoch)

        if _trained is not None:
            _prog_placeholder.progress(100, text="✅ Hoàn thành!")
            _ep    = getattr(_trained, "_train_epochs",  "?")
            _mae   = getattr(_trained, "_train_val_mae", None)
            _n     = getattr(_trained, "_train_samples",  "?")
            _mae_s = f"  ·  Val MAE: **{_mae:.4f}%**" if _mae is not None else ""
            st.success(
                f"✅ **LSTM huấn luyện xong!**  {_ep} epochs  ·  {_n} samples{_mae_s}  "
                f"·  Đã lưu: `data/models/{_ticker}_lstm.keras`"
            )
            st.rerun()
        else:
            _prog_placeholder.empty()
            _backend_hint = (
                f" *(backend: `{_KERAS_BACKEND}`)*" if _KERAS_BACKEND else ""
            )
            st.error(
                f"❌ **Huấn luyện thất bại**{_backend_hint}.  "
                "Kiểm tra: `pip install tensorflow`  |  dữ liệu >= 30 phiên  |  xem log console."
            )

    # ── Forecast computation + expander ─────────────────────────────────────
    fc = multi_horizon_forecast(r, df)
    _lstm_src_label = (
        "🧠 LSTM" if fc["lstm_source"] == "lstm"
        else "📊 Ridge" if fc["lstm_source"] == "ridge"
        else "⚪ N/A"
    )
    _lstm_val_label = (
        f"{fc['lstm_pred_pct']:+.2f}%" if fc["lstm_pred_pct"] is not None else "---"
    )
    with st.expander(
        f"🔭 Dự báo Đa Khung Thời gian  ·  Tổng hợp: {fc['overall_vote']}  ({fc['overall_conf']:.0f}%)"
        f"  ·  {_lstm_src_label}: {_lstm_val_label}",
        expanded=False,
    ):
        st.markdown(_HORIZON_CSS, unsafe_allow_html=True)

        # Overall summary banner
        ov_color = _conf_color(fc["overall_conf"])
        lstm_txt = ""
        if fc["lstm_pred_pct"] is not None:
            src_lbl = "LSTM" if fc["lstm_source"] == "lstm" else "Ridge ML"
            lstm_txt = (
                f'<div class="lstm-box">'
                f'🧠 {src_lbl} 5 ngày: '
                f'<b style="color:{"#22c55e" if fc["lstm_pred_pct"] >= 0 else "#ef4444"};font-size:15px;">'
                f'{fc["lstm_pred_pct"]:+.2f}%</b>'
                f'&nbsp;&nbsp;<span style="color:#64748b;font-size:10px;">({src_lbl})</span>'
                f'</div>'
            )
        st.markdown(
            f'<div style="background:#141824;border:1px solid {ov_color};border-radius:8px;'
            f'padding:12px 18px;margin-bottom:14px;">'
            f'<span style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;">Kết luận tổng hợp</span><br>'
            f'<span style="font-size:18px;font-weight:800;color:{ov_color};">{fc["overall_vote"]}</span>'
            f'&nbsp;&nbsp;<span style="color:#64748b;font-size:12px;">({fc["overall_conf"]:.0f}% xác tín)</span>'
            f'{lstm_txt}'
            f'</div>',
            unsafe_allow_html=True,
        )

        cols = st.columns(3)
        horizons = [
            ("⏱ Ngắn hạn (3–5 ngày)", fc["short_vote"], fc["short_conf"], fc["short_reasons"]),
            ("📅 Trung hạn (1 tháng)",   fc["mid_vote"],   fc["mid_conf"],   fc["mid_reasons"]),
            ("📈 Dài hạn (3–6 tháng)",     fc["long_vote"],  fc["long_conf"],  fc["long_reasons"]),
        ]
        for col, (title, vote, conf, reasons) in zip(cols, horizons):
            with col:
                color     = _conf_color(conf)
                fill_pct  = max(0, min(100, conf))
                reasons_html = "".join(
                    f'<div class="horizon-reason">• {rr}</div>'
                    for rr in reasons
                )
                st.markdown(
                    f'<div class="horizon-card">'
                    f'<div class="horizon-title">{title}</div>'
                    f'<div class="horizon-vote" style="color:{color};">{vote}</div>'
                    f'<div class="horizon-conf-bar">'
                    f'  <div class="horizon-conf-fill" style="width:{fill_pct}%;background:{color};"></div>'
                    f'</div>'
                    f'<div style="font-size:11px;color:#64748b;margin-bottom:10px;">{conf:.0f}% xác tín</div>'
                    f'{reasons_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # Pivot + Fibonacci details
        pivots = fc.get("mid_pivots", {})
        fib    = fc.get("mid_fib", {})
        if pivots or fib:
            st.markdown("---")
            pc1, pc2 = st.columns(2)
            if pivots:
                with pc1:
                    st.markdown("··· **Pivot Points (20 phiên gần nhất)**")
                    piv_html = "".join(
                        f'<tr><td>{k.replace("monthly_","").upper()}</td>'
                        f'<td style="font-family:monospace;text-align:right;">{v:,.0f}</td></tr>'
                        for k, v in pivots.items()
                    )
                    st.markdown(
                        f'<table class="ma-table"><thead><tr><th>Mức</th><th>Giá</th></tr></thead>'
                        f'<tbody>{piv_html}</tbody></table>',
                        unsafe_allow_html=True,
                    )
            if fib:
                with pc2:
                    st.markdown("··· **Fibonacci Retracement**")
                    fib_html = "".join(
                        f'<tr><td>{k.replace("fib_","").upper().replace("SWING_HIGH","Swing High").replace("SWING_LOW","Swing Low")}</td>'
                        f'<td style="font-family:monospace;text-align:right;">{v:,.0f}</td></tr>'
                        for k, v in fib.items()
                    )
                    st.markdown(
                        f'<table class="ma-table"><thead><tr><th>Mức Fib</th><th>Giá</th></tr></thead>'
                        f'<tbody>{fib_html}</tbody></table>',
                        unsafe_allow_html=True,
                    )


# ═══════════════════════════════════════════════════════════════════════════════
#  BACKTEST
# ═══════════════════════════════════════════════════════════════════════════════


def render_backtest(r: dict) -> None:
    """Walk-forward backtest stats for 3 / 5 / 7 / 10-day timeframes."""
    _TIMEFRAMES = [
        ("bt3",  "3 ngày"),
        ("bt5",  "5 ngày"),
        ("bt7",  "7 ngày"),
        ("bt10", "10 ngày"),
    ]
    # Collect available timeframes
    available = [(pfx, lbl) for pfx, lbl in _TIMEFRAMES if r.get(f"{pfx}_signals")]
    if not available:
        return

    total_signals = r.get(f"{available[0][0]}_signals", 0)
    # Read threshold from first available backtest result (all share same threshold)
    bt_thr = r.get(f"{available[0][0]}_threshold", 65.0)
    is_bear_adj = bt_thr > 65.0
    with st.expander(f"📊 Walk-Forward Backtest  ·  {total_signals} tín hiệu BUY  ·  {len(available)} khung thời gian"):
        # Header row of metric columns
        cols = st.columns(len(available))
        for col, (pfx, lbl) in zip(cols, available):
            win = r.get(f"{pfx}_win_rate", 0)
            avg = r.get(f"{pfx}_avg_return", 0)
            col.metric(
                f"Win% — {lbl}",
                f"{win:.1f}%",
                delta=f"avg {avg:+.2f}%",
                delta_color="normal",
            )

        # Detail table
        rows_html = ""
        for pfx, lbl in available:
            n   = r.get(f"{pfx}_signals",         0)
            win = r.get(f"{pfx}_win_rate",         0)
            avg = r.get(f"{pfx}_avg_return",       0)
            aw  = r.get(f"{pfx}_avg_win",          0)
            al  = r.get(f"{pfx}_avg_loss",         0)
            ml  = r.get(f"{pfx}_max_loss_streak",  0)
            w_c = "color:#22c55e" if win >= 55 else "color:#f97316" if win >= 45 else "color:#ef4444"
            a_c = "color:#22c55e" if avg >= 0 else "color:#ef4444"
            rows_html += (
                f'<tr><td><b>{lbl}</b></td>'
                f'<td>{n}</td>'
                f'<td style="{w_c};font-weight:600">{win:.1f}%</td>'
                f'<td style="{a_c}">{avg:+.2f}%</td>'
                f'<td style="color:#22c55e">{aw:+.2f}%</td>'
                f'<td style="color:#ef4444">{al:+.2f}%</td>'
                f'<td>{ml}</td></tr>'
            )
        st.markdown(
            f'<table class="sum-table"><thead><tr>'
            f'<th>Khung</th><th>Tín hiệu</th><th>Win%</th>'
            f'<th>Avg%</th><th>Avg Thắng</th><th>Avg Thua</th><th>Thua liên tiếp tối đa</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"🎯 Ngưỡng BUY: bull% ≥ {bt_thr:.0f}%"
            + (" (nâng lên do BEAR_TREND — khớp với tín hiệu live)" if is_bear_adj else " (tiêu chuẩn)")
            + "  —  Chỉ dùng MA + RSI + MACD. Không tính phí, slippage, thanh khoản."
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  KELLY POSITION SIZING
# ═══════════════════════════════════════════════════════════════════════════════

def render_position_sizing(r: dict) -> None:
    """
    Quarter-Kelly position sizing calculator driven by walk-forward backtest stats.
    Prefers 5-day backtest; falls back to 7 → 10 → 3.
    f* = (p·b − q) / b  where p=win_rate, q=1-p, b=avg_win/avg_loss.
    Shows position value, share lot (round-down to 100), and risk in ₫.
    """
    # Pick best available backtest prefix
    bt_pfx = next(
        (p for p in ("bt5", "bt7", "bt10", "bt3") if r.get(f"{p}_win_rate")),
        None,
    )
    if not bt_pfx:
        bars = r.get("bars") or 0
        if bars > 0:
            # Data was loaded but backtest produced <5 signals — tell the user why
            with st.expander("💰 Kelly Position Sizing  ·  Không đủ dữ liệu backtest",
                             expanded=False):
                st.caption(
                    f"⚠️ Cần ≥ 220 nến và ≥ 5 tín hiệu BUY trong lịch sử để tính Kelly. "
                    f"Dữ liệu hiện có: {bars} nến. Tăng số ngày lịch sử lên 400–600 ngày "
                    f"hoặc chọn các mã có thanh khoản cao hơn."
                )
        return

    win_rate = (r.get(f"{bt_pfx}_win_rate") or 0) / 100
    avg_win  = r.get(f"{bt_pfx}_avg_win")  or 0
    avg_loss = abs(r.get(f"{bt_pfx}_avg_loss") or 0)
    price    = r.get("price") or 0

    # Guard: need valid inputs for meaningful output
    if avg_loss == 0 or price <= 0 or win_rate <= 0:
        return

    b         = avg_win / avg_loss           # win/loss magnitude ratio
    q         = 1.0 - win_rate
    f_full    = (win_rate * b - q) / b       # full Kelly fraction (can be negative)
    f_quarter = max(0.0, f_full * 0.25)      # ¼ Kelly, floor at 0 (never short)
    bt_lbl    = {"bt3": "3 ngày", "bt5": "5 ngày", "bt7": "7 ngày", "bt10": "10 ngày"}[bt_pfx]

    with st.expander(
        f"💰 Kelly Position Sizing  ·  Backtest {bt_lbl}  ·  "
        f"¼ Kelly = {f_quarter * 100:.1f}%  ·  W/L ratio = {b:.2f}",
        expanded=False,
    ):
        pv_col, _ = st.columns([1, 2])
        with pv_col:
            portfolio_vnd = st.number_input(
                "Tổng vốn danh mục (₫)",
                min_value=10_000_000,
                max_value=10_000_000_000,
                value=500_000_000,
                step=50_000_000,
                format="%d",
                key=f"kelly_pv_{r['ticker']}",
            )

        pos_value   = portfolio_vnd * f_quarter
        # Round down to nearest lot of 100 shares; minimum 100 when Kelly > 0
        shares      = int(pos_value / price / 100) * 100
        shares      = max(100, shares) if f_quarter > 0 and shares < 100 else shares
        risk_amt    = shares * price * avg_loss / 100          # ₫ at-risk per avg loss
        actual_pct  = (shares * price / portfolio_vnd * 100) if portfolio_vnd > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Full Kelly",           f"{f_full * 100:.1f}%",
                  help="Mức lý thuyết Kelly — biến động rất cao, KHÔNG nên dùng")
        c2.metric("¼ Kelly (khuyến nghị)", f"{f_quarter * 100:.1f}%")
        c3.metric("Số lượng CP (lot 100)", f"{shares:,}")
        c4.metric("Rủi ro ước tính",       f"{risk_amt:,.0f} ₫",
                  delta=f"{avg_loss:.1f}% avg loss/trade", delta_color="inverse")

        st.markdown(
            f'<div style="background:#141824;border:1px solid #2d3347;border-radius:8px;'
            f'padding:12px 16px;font-size:12.5px;color:#94a3b8;line-height:2.1;">'
            f'<b style="color:#e2e8f0;">Giá trị vị thế:</b> '
            f'<span style="color:#22c55e;font-weight:700;">{shares * price:,.0f} ₫</span>'
            f'&nbsp;({actual_pct:.1f}% danh mục)'
            f'&nbsp;&nbsp;·&nbsp;&nbsp;'
            f'<b style="color:#e2e8f0;">Win rate:</b> '
            f'<span style="color:#60a5fa;font-weight:700;">{win_rate * 100:.1f}%</span>'
            f'&nbsp;&nbsp;·&nbsp;&nbsp;'
            f'<b style="color:#e2e8f0;">W/L (b):</b> '
            f'<span style="color:#60a5fa;font-weight:700;">{b:.2f}</span>'
            f'&nbsp;&nbsp;·&nbsp;&nbsp;'
            f'<b style="color:#e2e8f0;">Nguồn:</b> backtest {bt_lbl}'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "⚠️ Kelly Criterion — f* = (p·b − q) / b. "
            "¼ Kelly giảm phương sai, bảo toàn vốn tốt hơn Full Kelly. "
            "Không bao gồm phí giao dịch và slippage. Chỉ dùng làm tham khảo."
        )


# ── signal color map (used in multiple tables) ─────────────────────────────
_SIG_COLOR_MAP = {
    "MUA":            "#22c55e",
    "THEO DÕI–TĂNG":  "#3b82f6",
    "TRUNG LẬP":      "#94a3b8",
    "THEO DÕI–GIẢM":  "#f97316",
    "BÁN / TRÁNH":    "#ef4444",
}


def _ticker_sig_cell(ticker: str, sig: str) -> str:
    """Ticker cell with signal-based left-border color strip."""
    c = _SIG_COLOR_MAP.get(sig, "#475569")
    return (
        f'<b style="font-size:14px;border-left:3px solid {c};'
        f'padding-left:7px;color:{c}">{_safe(ticker)}</b>'
    )


def _filterable_table(table_id: str, html: str) -> str:
    """Wrap a <table> with per-column filter inputs in a filter row under headers."""
    import re as _re

    # Count <th> cells in the first header <tr>
    m = _re.search(r"<thead[^>]*>(.*?)</thead>", html, _re.DOTALL | _re.IGNORECASE)
    n_cols = 0
    if m:
        first_tr = _re.search(r"<tr[^>]*>(.*?)</tr>", m.group(1), _re.DOTALL | _re.IGNORECASE)
        if first_tr:
            n_cols = len(_re.findall(r"<th[^>]*>", first_tr.group(1), _re.IGNORECASE))

    # JS that, on each keypress, hides rows failing any column filter
    js = (
        "(function(){"
        "var f=document.querySelectorAll('#" + table_id + " .flt-row th input');"
        "document.querySelectorAll('#" + table_id + " tbody tr').forEach(function(r){"
        "var s=true;"
        "[].forEach.call(f,function(fi,i){"
        "var v=fi.value.toLowerCase();"
        "if(!v)return;"
        "var c=r.querySelectorAll('td')[i];"
        "if(!c||!c.innerText.toLowerCase().includes(v))s=false;"
        "});"
        "r.classList.toggle('tbl-hidden',!s);"
        "});"
        "})()"
    )

    filter_cells = "".join(
        "<th style='padding:2px;'><input placeholder='🔍' oninput='" + js + "'/></th>"
        for _ in range(n_cols)
    )
    filter_row = "<tr class='flt-row'>" + filter_cells + "</tr>"

    # Tag table and inject filter row after first </tr> inside <thead>
    tagged = html.replace("<table ", '<table id="' + table_id + '" ')

    def _inject(match):
        return match.group(0).replace("</tr>", "</tr>" + filter_row, 1)

    tagged = _re.sub(
        r"<thead[^>]*>.*?</thead>",
        _inject,
        tagged,
        count=1,
        flags=_re.DOTALL | _re.IGNORECASE,
    )
    return tagged


def _ssi_cell(r: dict) -> str:
    """Small SSI badge HTML for summary/scanner tables."""
    _s = compute_ssi_score(r)
    v  = _s.get("ssi", 0)
    g  = _s.get("ssi_grade", "?")
    c  = _s.get("ssi_color", "#94a3b8")
    return (
        f'<span style="background:{c}22;border:1px solid {c};color:{c};'
        f'border-radius:999px;padding:2px 8px;font-size:11px;font-weight:800;">'
        f'{v}·{g}</span>'
    )


def render_correlation_matrix(results: list, dfs: dict) -> None:
    """F12: Correlation matrix heatmap for ≥3 tickers (Phase 5)."""
    valid = [
        r["ticker"] for r in results
        if "error" not in r and dfs.get(r["ticker"]) is not None
    ]
    if len(valid) < 3:
        return
    st.markdown("#### 🔗 Ma trận tương quan lợi suất (F12)")
    # Build returns matrix
    all_ret = {}
    for tk in valid:
        df_tk = dfs[tk]
        if df_tk is not None and len(df_tk) >= 20:
            try:
                rets = df_tk["Close"].pct_change().dropna().tail(60)
                all_ret[tk] = rets.values
            except Exception:
                pass
    if len(all_ret) < 3:
        st.caption("Không đủ dữ liệu lợi suất để tính tương quan.")
        return
    import pandas as _pd_corr
    min_len = min(len(v) for v in all_ret.values())
    corr_df = _pd_corr.DataFrame(
        {tk: v[-min_len:] for tk, v in all_ret.items()}
    ).corr()
    corr_tks = list(corr_df.columns)
    z = [[round(corr_df.loc[a, b], 2) for b in corr_tks] for a in corr_tks]
    fig = go.Figure(go.Heatmap(
        z=z, x=corr_tks, y=corr_tks,
        colorscale="RdYlGn", zmid=0, zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in z],
        hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
        texttemplate="%{text}",
    ))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0d1117",
        height=max(280, len(corr_tks) * 50 + 60), margin=dict(l=10, r=10, t=20, b=10),
        font=dict(family="JetBrains Mono, Consolas, monospace", size=11, color="#94a3b8"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption("Dựa trên lợi suất hàng ngày 60 phiên gần nhất.")


def render_summary_table(results: list) -> None:
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("### 📋 Bảng Tổng Kết")

    # Compute PROMETHEE ranking for valid results
    valid_results = [r for r in results if "error" not in r and r.get("price")]
    rank_df = promethee_ii_ranking(valid_results) if len(valid_results) >= 2 else pd.DataFrame()
    rank_map = {row["ticker"]: row for _, row in rank_df.iterrows()} if not rank_df.empty else {}

    rows = ""
    for r in results:
        sig_v = r.get("signal", "")
        if "error" in r:
            rows += (f'<tr><td>{_ticker_sig_cell(r["ticker"], "")}</td>'
                     f'<td colspan="9" class="col-red">❌ {_safe(r["error"])}</td></tr>')
            continue
        pct_v  = r.get("pct_change", 0) or 0
        p_cls  = "col-pos" if pct_v > 0 else "col-neg" if pct_v < 0 else "col-flat"
        c_flag = " ⚠️" if r.get("at_ceiling") else ""
        f_flag = " ✅" if r.get("at_floor")   else ""
        rk = rank_map.get(r["ticker"])
        rank_html = (
            f'<b style="color:#fbbf24;">#{rk["rank"]}</b>'
            f'<span style="font-size:10px;color:#64748b;"> ({rk["net_flow"]:+.3f})</span>'
            if rk is not None else "–"
        )
        rows += f"""<tr>
  <td>{_ticker_sig_cell(r['ticker'], sig_v)}</td>
  <td>{_f(r.get('price'))}</td>
  <td class="{p_cls}">{_pct(pct_v)}</td>
  <td>{_f(r.get('rsi'), 1)}</td>
  <td>{_f(r.get('stoch_k'), 1)}</td>
  <td>{_f(r.get('adx'), 1)}</td>
  <td>{(_f(r.get('kl_ratio'), 1) + '×') if r.get('kl_ratio') else '–'}</td>
  <td style="font-size:12px;color:var(--muted);">{r.get('trend_struct','–')}</td>
  <td>{_badge(sig_v)}{c_flag}{f_flag}</td>
  <td>{_t25_badge(r.get('t25_signal',''), r.get('t25_score'))}</td>
  <td>{_ssi_cell(r)}</td>
  <td>{rank_html}</td>
</tr>"""
    table_html = f'''
<table class="sum-table">
  <thead>
    <tr>
      <th>Mã</th><th>Giá</th><th>%Δ</th>
      <th>RSI</th><th>Stoch</th><th>ADX</th><th>KL×</th>
      <th>Cấu trúc MA</th><th>Tín hiệu</th>
      <th title="VN-Swing Alpha T+2.5 score">T+2.5</th>
      <th title="Swing Strength Index">SSI</th>
      <th>MCDA Rank</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
'''
    st.markdown(_filterable_table("summary_tbl", table_html), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT HELPERS  (reads data/Profiler/*.json JSONL files)
# ═══════════════════════════════════════════════════════════════════════════════
_AUDIT_DIR      = os.path.join(_DIR, "data", "Profiler")
# ── Phase 3: Persistent data stores (F5, F11, F13, F14) ────────────────────
_TRADES_PATH    = os.path.join(_DIR, "data", "active_trades.json")
_ALERTS_PATH    = os.path.join(_DIR, "data", "alerts.json")
_JOURNAL_PATH   = os.path.join(_DIR, "data", "journal.jsonl")
_CONDITIONS_PATH= os.path.join(_DIR, "data", "conditions.json")
os.makedirs(os.path.join(_DIR, "data"), exist_ok=True)


def _load_active_trades() -> list:
    try:
        if os.path.isfile(_TRADES_PATH):
            with open(_TRADES_PATH, encoding="utf-8") as _f:
                return json.load(_f)
    except Exception:
        pass
    return []


def _save_active_trades(trades: list) -> None:
    try:
        with open(_TRADES_PATH, "w", encoding="utf-8") as _f:
            json.dump(trades, _f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_alerts() -> list:
    try:
        if os.path.isfile(_ALERTS_PATH):
            with open(_ALERTS_PATH, encoding="utf-8") as _f:
                return json.load(_f)
    except Exception:
        pass
    return []


def _save_alerts(alerts: list) -> None:
    try:
        with open(_ALERTS_PATH, "w", encoding="utf-8") as _f:
            json.dump(alerts, _f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _append_journal_entry(entry: dict) -> None:
    try:
        from datetime import datetime as _dt
        entry["closed_at"] = entry.get("closed_at") or _dt.now().isoformat(timespec="seconds")
        with open(_JOURNAL_PATH, "a", encoding="utf-8") as _f:
            _f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _load_journal() -> list:
    rows = []
    try:
        if os.path.isfile(_JOURNAL_PATH):
            with open(_JOURNAL_PATH, encoding="utf-8") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line:
                        try:
                            rows.append(json.loads(_line))
                        except Exception:
                            pass
    except Exception:
        pass
    rows.sort(key=lambda x: x.get("closed_at", ""), reverse=True)
    return rows


def _load_conditions() -> list:
    try:
        if os.path.isfile(_CONDITIONS_PATH):
            with open(_CONDITIONS_PATH, encoding="utf-8") as _f:
                return json.load(_f)
    except Exception:
        pass
    return []


def _save_conditions(conds: list) -> None:
    try:
        with open(_CONDITIONS_PATH, "w", encoding="utf-8") as _f:
            json.dump(conds, _f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _list_audit_tickers() -> list:
    """Return sorted list of tickers that have audit JSONL files."""
    if not os.path.isdir(_AUDIT_DIR):
        return []
    return sorted(
        f[:-5].upper()
        for f in os.listdir(_AUDIT_DIR)
        if f.lower().endswith(".json")
    )


def _load_audit_history(ticker: str) -> list:
    """Load all audit runs for a ticker, newest first."""
    path = os.path.join(_AUDIT_DIR, f"{ticker.upper()}.json")
    if not os.path.isfile(path):
        return []
    rows = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                        # ── Migrate old-format records (pre-multi-horizon backtest)
                        # Old code wrote 'bt_win_rate' etc.; new code writes 'bt5_*'.
                        # Copy old keys into the bt5 slot so Kelly panel and audit
                        # charts work correctly for historical runs.
                        if rec.get('bt_win_rate') and not rec.get('bt5_win_rate'):
                            for _sfx in ('signals','win_rate','avg_return','avg_win',
                                         'avg_loss','max_loss_streak','forward_days','threshold'):
                                if f'bt_{_sfx}' in rec:
                                    rec[f'bt5_{_sfx}'] = rec[f'bt_{_sfx}']
                        # Migrate old 'vsa' key → 'vsa_state'
                        if rec.get('vsa') and not rec.get('vsa_state'):
                            rec['vsa_state'] = rec['vsa']
                        rows.append(rec)
                    except Exception:
                        pass
    except Exception:
        pass
    rows.sort(key=lambda x: x.get("run_ts", ""), reverse=True)
    return rows


def _audit_signal_color(sig: str) -> str:
    return {
        "MUA":            "#22c55e",
        "THEO DÕI–TĂNG": "#3b82f6",
        "TRUNG LẬP":    "#94a3b8",
        "THEO DÕI–GIẢM": "#f97316",
        "BÁN / TRÁNH":   "#ef4444",
    }.get(sig, "#94a3b8")


def _build_audit_trend_chart(history_asc: list) -> go.Figure:
    """Plotly dual-axis chart: bull% bars + price line over scan timestamps."""
    ts   = [r.get("run_ts", "") for r in history_asc]
    bp   = [r.get("bull_pct", 50) for r in history_asc]
    px_  = [r.get("price") or 0  for r in history_asc]
    sigs = [r.get("signal", "")   for r in history_asc]
    bar_colors = [_audit_signal_color(s) for s in sigs]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Bull% bars
    fig.add_trace(
        go.Bar(
            x=ts, y=bp,
            name="Bull %",
            marker_color=bar_colors, opacity=0.75,
            hovertemplate="%{x}<br>Bull: %{y:.1f}%<extra></extra>",
        ),
        secondary_y=False,
    )
    # Price line
    fig.add_trace(
        go.Scatter(
            x=ts, y=px_,
            name="Giá",
            mode="lines+markers",
            line=dict(color="#f59e0b", width=2),
            marker=dict(size=6),
            hovertemplate="%{x}<br>Giá: %{y:,.0f}<extra></extra>",
        ),
        secondary_y=True,
    )
    # 50% reference line on bull% axis
    fig.add_hline(y=50, line_dash="dash", line_color="rgba(148,163,184,0.35)",
                  secondary_y=False)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0e1117", plot_bgcolor="#0d1117",
        height=260, margin=dict(l=10, r=60, t=20, b=40),
        font=dict(family="JetBrains Mono, Consolas, monospace", size=11, color="#94a3b8"),
        legend=dict(orientation="h", y=1.1, x=0, bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        bargap=0.25,
    )
    fig.update_yaxes(title_text="Bull %", range=[0, 100],
                     gridcolor="#1a2030", secondary_y=False)
    fig.update_yaxes(title_text="Giá", gridcolor="#1a2030", secondary_y=True)
    fig.update_xaxes(gridcolor="#1a2030", tickangle=-30, tickfont=dict(size=9))
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def _t_rec_action_color(action: str) -> str:
    return _T_REC_COLORS.get(action, "#94a3b8")


def _audit_snapshot_row_html(r: dict, runs: int) -> str:
    """Build one <tr> for the snapshot table with signal-colored ticker."""
    sig   = r.get("signal", "")
    scol  = _audit_signal_color(sig)
    pct   = r.get("pct_change", 0) or 0
    bp    = r.get("bull_pct", 50) or 50
    ts    = (r.get("run_ts") or "")[:16].replace("T", " ")
    rl    = r.get("regime_label") or r.get("regime") or "–"
    vsa   = r.get("vsa_state", "NEUTRAL") or "NEUTRAL"
    _sc   = r.get("signal_confirmed")
    conf  = "✓" if _sc is True else ("⚡" if _sc is False else "–")
    cc    = "#22c55e" if _sc is True else ("#f97316" if _sc is False else "#94a3b8")
    pc    = "#22c55e" if pct > 0 else "#ef4444" if pct < 0 else "#94a3b8"
    bc    = _audit_signal_color(sig)
    # Forecast summary (if saved)
    fc_ov   = r.get("fc_overall_vote", "")
    fc_conf = r.get("fc_overall_conf")
    fc_cell = (
        f'<span style="color:{_audit_signal_color(fc_ov)};font-size:11px;">'
        f'{fc_ov} <span style="color:#64748b;">({fc_conf:.0f}%)</span></span>'
        if fc_ov and fc_conf else "–"
    )
    tk_cell = (
        f'<b style="font-size:14px;border-left:3px solid {scol};'
        f'padding-left:7px;color:{scol};">{_safe(r["ticker"])}</b>'
    )
    # T+ Recommendation cell (from persisted t_rec_* fields)
    _tra  = r.get("t_rec_action", "")
    _trg  = r.get("t_rec_grade",  "")
    _trs  = r.get("t_rec_score")
    if _tra:
        _trc = _t_rec_action_color(_tra)
        _trl = {"STRONG_BUY": "S.BUY", "BUY": "BUY", "WATCH": "WATCH",
                "SKIP": "SKIP", "AVOID": "AVOID"}.get(_tra, _tra)
        _score_s = f" {_trs}" if _trs is not None else ""
        t_rec_cell = (
            f'<span style="background:{_trc}22;border:1px solid {_trc};color:{_trc};'
            f'border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700;">'
            f'{_trl}{_score_s}</span>'
            f'<span style="font-size:11px;color:#64748b;"> {_trg}</span>'
        )
    else:
        t_rec_cell = "–"
    return (
        f'<tr>'
        f'<td>{tk_cell}</td>'
        f'<td style="font-family:var(--mono);">{_f(r.get("price"))}</td>'
        f'<td style="color:{pc};font-family:var(--mono);">{"+" if pct>=0 else ""}{pct:.1f}%</td>'
        f'<td style="color:{scol};font-weight:700;">{sig}</td>'
        f'<td>'
        f'<div style="background:#1a1f2e;border-radius:4px;height:14px;width:80px;overflow:hidden;">'
        f'<div style="background:{bc};height:100%;width:{int(bp)}%;opacity:.7;"></div></div>'
        f'<span style="font-size:11px;color:#94a3b8;">{bp:.0f}%</span></td>'
        f'<td style="font-size:12px;color:#94a3b8;">{rl}</td>'
        f'<td style="font-size:12px;color:#64748b;">{vsa}</td>'
        f'<td style="text-align:center;color:{cc};font-weight:700;">{conf}</td>'
        f'<td>{t_rec_cell}</td>'
        f'<td>{fc_cell}</td>'
        f'<td style="font-size:11px;color:#475569;">{ts}</td>'
        f'<td style="text-align:center;color:#475569;">{runs}</td>'
        f'</tr>'
    )


def _audit_detail_expander(row: dict, idx: int, prev_row: dict | None) -> None:
    """Render one collapsible expander with full indicator details for a single audit run."""
    sig_   = row.get("signal", "")
    scol_  = _audit_signal_color(sig_)
    ts_    = (row.get("run_ts") or "")[:16].replace("T", " ")
    bp_    = row.get("bull_pct", 50) or 50
    changed = (prev_row is not None and sig_ != prev_row.get("signal"))
    _trg_lbl = row.get("t_rec_action", "")
    _tr_badge = (
        f"  ·  🎯{_trg_lbl[:1]}{row.get('t_rec_grade','')}/{row.get('t_rec_score','')}" if _trg_lbl else ""
    )
    label  = f"{'⚡ ' if changed else ''}#{idx+1}  {ts_}  ·  {sig_}  ·  Bull {bp_:.0f}%  ·  {_f(row.get('price'))}{_tr_badge}"
    with st.expander(label, expanded=(idx == 0)):
        # ── Row A: key metrics ────────────────────────────────────────────
        ca1,ca2,ca3,ca4,ca5,ca6 = st.columns(6)
        ca1.metric("Giá",           _f(row.get("price")))
        ca2.metric("Thay đổi",      f'{row.get("pct_change",0) or 0:+.2f}%')
        ca3.metric("Bull %",        f'{bp_:.0f}%')
        ca4.metric("Bear %",        f'{100-bp_:.0f}%')
        ca5.metric("Tín hiệu",      sig_)
        ca6.metric("Xác nhận",      "✓ Có" if row.get("signal_confirmed", True) else "⚡ Chưa")

        # ── Row B: regime + VSA ───────────────────────────────────────────
        cb1,cb2,cb3,cb4,cb5 = st.columns(5)
        cb1.metric("Regime",        row.get("regime_label") or row.get("regime", "–"))
        cb2.metric("Regime Score",  row.get("regime_score", 0))
        cb3.metric("SMA200 Slope",  f'{row.get("sma200_slope", 0) or 0:+.2f}%')
        cb4.metric("VSA State",     row.get("vsa_state", "–") or "–")
        cb5.metric("VSA Score",     f'{row.get("vsa_score", 0) or 0:+.1f}')

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # ── MA table ─────────────────────────────────────────────────────
        price_ = row.get("price") or 0
        ma_rows = ""
        for lbl, key in [
            ("SMA 20","sma20"),("SMA 50","sma50"),("SMA 200","sma200"),
            ("EMA 9","ema9"),("EMA 21","ema21"),("EMA 50","ema50"),("EMA 200","ema200"),
            ("BB Upper","bb_upper"),("BB Mid","bb_mid"),("BB Lower","bb_lower"),
        ]:
            v = row.get(key)
            if v is None: continue
            pct_v = (v - price_) / price_ * 100 if price_ else 0
            pos   = "↑ Trên" if price_ > v else "↓ Dưới"
            pcls  = "#22c55e" if price_ > v else "#ef4444"
            ma_rows += (f'<tr><td style="color:#94a3b8;">{lbl}</td>'
                        f'<td style="font-family:var(--mono);">{v:,.0f}</td>'
                        f'<td style="color:{pcls};">{pct_v:+.2f}%</td>'
                        f'<td style="color:{pcls};">{pos}</td></tr>')

        # ── Oscillator table ──────────────────────────────────────────────
        osc_rows = ""
        for lbl, key, dp in [
            ("RSI (14)","rsi",1),("Stoch %K","stoch_k",1),("Stoch %D","stoch_d",1),
            ("ADX (14)","adx",1),("+DI","pdi",1),("-DI","ndi",1),
            ("MACD","macd",0),("MACD Signal","macd_signal",0),("MACD Hist","macd_hist",0),
            ("ATR (14)","atr",0),("Williams %R","williams_r",1),("CCI (20)","cci",0),
            ("OBV","obv",0),("OBV MA20","obv_ma",0),
            ("Vol Ratio","kl_ratio",2),
        ]:
            v = row.get(key)
            if v is None: continue
            fmt = f"{v:,.{dp}f}"
            osc_rows += (f'<tr><td style="color:#94a3b8;">{lbl}</td>'
                         f'<td style="font-family:var(--mono);">{fmt}</td></tr>')

        # ── Trade plan table ──────────────────────────────────────────────
        tp_rows = ""
        for lbl, key, cls in [
            ("Entry","entry","#f59e0b"),("SL","sl","#ef4444"),
            ("TP1","tp1","#06b6d4"),("TP2","tp2","#22c55e"),
        ]:
            v = row.get(key)
            if v: tp_rows += (f'<tr><td style="color:#94a3b8;">{lbl}</td>'
                              f'<td style="color:{cls};font-family:var(--mono);">{v:,.0f}</td></tr>')
        if row.get("rr1"):
            tp_rows += (f'<tr><td style="color:#94a3b8;">R:R</td>'
                        f'<td style="color:#06b6d4;">{row["rr1"]:.2f}:1</td></tr>')

        t1, t2, t3 = st.columns(3)
        with t1:
            st.markdown("**Moving Averages**")
            st.markdown(f'<table class="sum-table"><thead><tr>'
                        f'<th>MA</th><th>Giá trị</th><th>vs Giá</th><th>Vị trí</th>'
                        f'</tr></thead><tbody>{ma_rows}</tbody></table>',
                        unsafe_allow_html=True)
        with t2:
            st.markdown("**Oscillators & Indicators**")
            st.markdown(f'<table class="sum-table"><thead><tr>'
                        f'<th>Indicator</th><th>Giá trị</th>'
                        f'</tr></thead><tbody>{osc_rows}</tbody></table>',
                        unsafe_allow_html=True)
        with t3:
            st.markdown("**Trade Plan & Backtest**")
            st.markdown(f'<table class="sum-table"><thead><tr>'
                        f'<th>Mục</th><th>Giá trị</th>'
                        f'</tr></thead><tbody>{tp_rows}</tbody></table>',
                        unsafe_allow_html=True)
            # backtest stats — multi-timeframe (bt3 / bt5 / bt7 / bt10)
            _bt_pfxs = [("bt3","3d"),("bt5","5d"),("bt7","7d"),("bt10","10d")]
            _bt_avail = [(p, l) for p, l in _bt_pfxs if row.get(f"{p}_signals")]
            if _bt_avail:
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                bt_rows = ""
                # header sub-row
                for pfx, lbl in _bt_avail:
                    n   = row.get(f"{pfx}_signals", 0)
                    win = row.get(f"{pfx}_win_rate", 0)
                    avg = row.get(f"{pfx}_avg_return", 0)
                    ml  = row.get(f"{pfx}_max_loss_streak", 0)
                    w_c = "#22c55e" if win >= 55 else "#f97316" if win >= 45 else "#ef4444"
                    a_c = "#22c55e" if avg >= 0 else "#ef4444"
                    bt_rows += (
                        f'<tr>'
                        f'<td style="color:#94a3b8;">{lbl} ({n}✓)</td>'
                        f'<td style="font-family:var(--mono);color:{w_c}">{win:.1f}%</td>'
                        f'<td style="font-family:var(--mono);color:{a_c}">{avg:+.2f}%</td>'
                        f'<td style="font-family:var(--mono);color:#94a3b8">↓max {ml}</td>'
                        f'</tr>'
                    )
                st.markdown(
                    f'<table class="sum-table"><thead><tr>'
                    f'<th>Backtest</th><th>Win%</th><th>Avg%</th><th>Streak</th>'
                    f'</tr></thead><tbody>{bt_rows}</tbody></table>',
                    unsafe_allow_html=True,
                )

        # ── Confirmations + Commentary ────────────────────────────────────
        confirms = row.get("confirmations") or []
        if confirms:
            conf_html = "".join(f'<span class="conf-badge">{c}</span>' for c in confirms)
            st.markdown(f'<div style="margin-top:8px;">{conf_html}</div>',
                        unsafe_allow_html=True)
        commentary = row.get("commentary", "")
        if commentary:
            body = "<br>".join(commentary.split("\n"))
            st.markdown(f'<div class="commentary" style="margin-top:6px;">{body}</div>',
                        unsafe_allow_html=True)

        # ── Forecast summary (if persisted in audit record) ───────────────
        _fc_ov    = row.get("fc_overall_vote", "")
        _fc_conf  = row.get("fc_overall_conf")
        _fc_short = row.get("fc_short_vote", "")
        _fc_mid   = row.get("fc_mid_vote", "")
        _fc_long  = row.get("fc_long_vote", "")
        _fc_lstm  = row.get("fc_lstm_pct")
        if _fc_ov:
            def _fvcolor(v):
                return "#22c55e" if "TĂNG" in v or "MUA" in v else "#ef4444" if "GIẢM" in v or "BÁN" in v else "#94a3b8"
            _fc_rows = []
            for _lbl2, _vote2, _conf2, _rkkey in [
                ("Tổng hợp",          _fc_ov,    _fc_conf,                  None),
                ("⏱ Ngắn (3–5ngày)",  _fc_short, row.get("fc_short_conf"),  "fc_short_reasons"),
                ("📅 Trung (1tháng)",   _fc_mid,   row.get("fc_mid_conf"),    "fc_mid_reasons"),
                ("📈 Dài (3–6tháng)",   _fc_long,  row.get("fc_long_conf"),   "fc_long_reasons"),
            ]:
                if not _vote2: continue
                _rc  = _fvcolor(_vote2)
                _c2s = f" ({_conf2:.0f}%)" if _conf2 else ""
                _rrs = row.get(_rkkey, []) if _rkkey else []
                _rrs_txt = " · ".join(_rrs[:3])
                _fc_rows.append(
                    f'<tr><td style="color:#94a3b8;white-space:nowrap;">{_lbl2}</td>'
                    f'<td style="color:{_rc};font-weight:700;">{_vote2}</td>'
                    f'<td style="color:#64748b;font-size:11px;">{_c2s.strip()}</td>'
                    f'<td style="color:#475569;font-size:11px;">{_rrs_txt}</td></tr>'
                )
            if _fc_lstm is not None:
                _lc = "#22c55e" if _fc_lstm >= 0 else "#ef4444"
                _fc_rows.append(
                    f'<tr><td style="color:#94a3b8;">🧠 ML/LSTM</td>'
                    f'<td style="color:{_lc};font-weight:700;">{_fc_lstm:+.2f}%</td>'
                    f'<td colspan="2" style="color:#64748b;font-size:11px;">5 ngày</td></tr>'
                )
            if _fc_rows:
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                st.markdown(
                    f'<table class="sum-table"><thead><tr>'
                    f'<th>Dự báo</th><th>Kết luận</th><th>Xác tín</th><th>Lý do chính</th>'
                    f'</tr></thead><tbody>{"".join(_fc_rows)}</tbody></table>',
                    unsafe_allow_html=True,
                )

        # ── Meta ──────────────────────────────────────────────────────────
        st.caption(
            f"Nguồn: {row.get('ohlcv_src','–')}  ·  "
            f"{row.get('bars',0)} nến  ·  "
            f"Ngày cuối: {row.get('last_date','–')}  ·  "
            f"Quét lúc: {ts_}"
        )

        # ── Persisted T+ recommendation quick-metrics ────────────────────────────
        _saved_tra = row.get("t_rec_action", "")
        if _saved_tra:
            _trc  = _T_REC_COLORS.get(_saved_tra, "#94a3b8")
            _trg  = row.get("t_rec_grade", "")
            _trs  = row.get("t_rec_score", 0)
            _trfl = row.get("t_rec_flags",   []) or []
            _trss = row.get("t_rec_signals", []) or []
            _r_tp1= row.get("t_rec_tp1")
            _r_sl = row.get("t_rec_sl")
            _r_rr = row.get("t_rec_rr")
            _r_sz = row.get("t_rec_size_pct")
            _r_kl = row.get("t_rec_kelly", "–")
            _atr_cols = st.columns([2, 1, 1, 1])
            with _atr_cols[0]:
                st.markdown(
                    f'<div style="margin-top:8px;padding:8px 12px;border-radius:7px;'
                    f'background:{_trc}1a;border:1px solid {_trc}44;">'
                    f'<span style="color:{_trc};font-size:16px;font-weight:800;">'
                    f'🎯 {_saved_tra.replace("_"," ")} &nbsp; Grade {_trg}</span>'
                    f'<br><span style="color:#94a3b8;font-size:12px;">Score: <b style="color:{_trc};">{_trs}</b>/100 '
                    f'· Sizing: <b style="color:#a78bfa;">{_r_sz:.1f}%</b> ({_r_kl})</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with _atr_cols[1]:
                st.metric("SL",  f"{_r_sl:,.0f}" if _r_sl else "–")
            with _atr_cols[2]:
                st.metric("TP1", f"{_r_tp1:,.0f}" if _r_tp1 else "–")
            with _atr_cols[3]:
                st.metric("R:R", f"{_r_rr:.2f}:1" if _r_rr else "–")
            if _trss:
                st.markdown(
                    "<div>" + "".join(
                        f'<span style="display:inline-block;margin:2px 3px 0 0;padding:2px 7px;'
                        f'border-radius:10px;background:#16a34a22;color:#22c55e;font-size:11px;">✅ {s}</span>'
                        for s in _trss
                    ) + "</div>", unsafe_allow_html=True,
                )
            if _trfl:
                st.markdown(
                    "<div style='margin-top:3px;'>" + "".join(
                        f'<span style="display:inline-block;margin:2px 3px 0 0;padding:2px 7px;'
                        f'border-radius:10px;background:#dc262622;color:#ef4444;font-size:11px;">⚠️ {f}</span>'
                        for f in _trfl
                    ) + "</div>", unsafe_allow_html=True,
                )
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # ── VN-Swing Alpha T+2.5 panel ───────────────────────────────────────────
        _t25_sig   = row.get("t25_signal", "")
        _t25_score = row.get("t25_score")
        _t25_confs = row.get("t25_confirms", [])
        _t25_momo  = row.get("t25_momo_score")
        _t25_str   = row.get("t25_struct_score")
        _t25_con   = row.get("t25_conf_score")
        _candle_p  = row.get("candle_pattern", "NEUTRAL")
        _rsi_div   = row.get("rsi_divergence", "NONE")
        if _t25_sig:
            _tc = _T25_COLOR.get(_t25_sig, "#475569")
            _timing = (
                "⏰ Cửa sổ vào lệnh: **10:00–11:00** (tốt nhất) · 13:30–14:00 (thay thế) · **TRÁNH ATO/ATC**"
                if _t25_sig == "T25_BUY" else ""
            )
            _score_str = f" · {_t25_score:.0f}/100" if _t25_score is not None else ""
            _sub_str   = ""
            if _t25_momo is not None:
                _sub_str = f"Momentum: {_t25_momo:.0f}/20 · Structure: {_t25_str:.0f}/20 · Confirm: {_t25_con:.0f}/10"
            _conf_str  = " · ".join((_t25_confs or [])[:6])
            _extra = []
            if _candle_p and _candle_p != "NEUTRAL":
                _extra.append(f"Candle: {_candle_p}")
            if _rsi_div and _rsi_div != "NONE":
                _extra.append(f"RSI Div: {_rsi_div}")
            _muted = "#94a3b8"
            _dim   = "#64748b"
            _hp = [
                f'<div style="margin-top:8px;padding:8px 12px;border-left:3px solid {_tc};'
                f'background:{_tc}12;border-radius:5px;">',
                f'<span style="color:{_tc};font-weight:700;font-size:13px;">'
                f'\U0001f4ca VN-Swing Alpha T+2.5: {_t25_sig.replace("T25_","")}{_score_str}</span>',
            ]
            if _sub_str:
                _hp.append(f'<br><small style="color:{_muted};">{_sub_str}</small>')
            if _conf_str:
                _hp.append(f'<br><small style="color:{_dim};">{_conf_str}</small>')
            if _extra:
                _hp.append(f'<br><small style="color:{_dim};">{" · ".join(_extra)}</small>')
            if _timing:
                _hp.append(f'<br><small style="color:{_muted};">{_timing}</small>')
            _hp.append('</div>')
            st.markdown("".join(_hp), unsafe_allow_html=True)
        render_t_plus_recommendation(row)
def render_t_plus_recommendation(r: dict, fc: dict = None) -> None:
    """
    Render the T+ Entry Recommendation card for a single ticker result dict.
    Uses generate_t_plus_recommendation() to compute the score/action then
    displays it in an expander with grade badge, confidence gauge, trade levels,
    sizing info, and supporting/risk signal chips.
    """
    ticker = r.get("ticker", "")
    # Build minimal fc from stored fields if not supplied
    if fc is None and r.get("fc_lstm_pct") is not None:
        fc = {"lstm_pred_pct": r["fc_lstm_pct"], "lstm_source": r.get("fc_lstm_source", "ridge")}

    rec = generate_t_plus_recommendation(r, fc)
    action    = rec["action"]
    grade     = rec["grade"]
    score     = rec["confidence_score"]
    color     = _T_REC_COLORS.get(action, "#94a3b8")

    action_labels = {
        "STRONG_BUY": "💎 STRONG BUY",
        "BUY":        "✅ BUY",
        "WATCH":      "👁 WATCH",
        "SKIP":       "⏭ SKIP",
        "AVOID":      "🚫 AVOID",
    }
    label = action_labels.get(action, action)

    with st.expander(
        f"🎯 Khuyến nghị T+ Entry · **{ticker}** · {label} (Grade {grade}) · {score}/100",
        expanded=(action in ("STRONG_BUY", "BUY")),
    ):
        # ── Row 1: Action banner ──────────────────────────────────────────────
        bar_w = max(4, score)
        st.markdown(
            f'<div style="padding:10px 14px;border-radius:7px;'
            f'background:{color}1a;border:1px solid {color}55;margin-bottom:8px;">'
            f'<span style="color:{color};font-size:18px;font-weight:800;">{label}</span>'
            f'&nbsp;&nbsp;<span style="color:#94a3b8;font-size:13px;">Grade&nbsp;</span>'
            f'<span style="color:{color};font-size:22px;font-weight:900;'
            f'font-family:monospace;">{grade}</span>'
            f'<span style="float:right;color:#94a3b8;font-size:12px;line-height:2;">'
            f'Score: <b style="color:{color};">{score}</b>/100</span>'
            f'</div>'
            f'<div style="background:#1a2030;border-radius:4px;height:8px;overflow:hidden;margin-bottom:10px;">'
            f'<div style="background:{color};width:{bar_w}%;height:100%;transition:width .4s;"></div></div>',
            unsafe_allow_html=True,
        )

        # ── Row 2: 3 columns — entry zone | SL/TP | sizing ───────────────────
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**📍 Vùng vào lệnh**")
            if rec["entry_zone_low"] and rec["entry_zone_high"]:
                st.markdown(
                    f'<div style="font-family:monospace;color:#fbbf24;font-size:14px;">'
                    f'{rec["entry_zone_low"]:,.0f} – {rec["entry_zone_high"]:,.0f}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("–")
            st.caption(rec.get("entry_timing", "") or "")
        with c2:
            st.markdown("**📉 SL / TP1 / TP2**")
            _sl  = rec["sl_price"]
            _tp1 = rec["tp1_price"]
            _tp2 = rec["tp2_price"]
            _rr  = rec["rr_ratio"]
            _mr  = rec["max_risk_pct"]
            _er  = rec["expected_return_pct"]
            _parts = []
            if _sl:
                _parts.append(f'<span style="color:#ef4444;">SL {_sl:,.0f}</span>')
            if _tp1:
                _t1_sfx = f' (+{_er:.1f}%)' if _er else ''
                _parts.append(f'<span style="color:#06b6d4;">TP1 {_tp1:,.0f}{_t1_sfx}</span>')
            if _tp2:
                _parts.append(f'<span style="color:#22c55e;">TP2 {_tp2:,.0f}</span>')
            st.markdown(
                '<div style="font-family:monospace;font-size:13px;line-height:1.8;">'
                + '<br>'.join(_parts) + '</div>',
                unsafe_allow_html=True,
            )
            if _rr:
                st.caption(f"R:R = {_rr:.2f}:1{'  ·  Risk ' + str(_mr) + '%' if _mr else ''}")
        with c3:
            st.markdown("**💼 Sizing / Kelly**")
            _pct  = rec["position_size_pct"]
            _kmode= rec["kelly_mode"]
            st.markdown(
                f'<div style="font-size:20px;font-weight:700;font-family:monospace;'
                f'color:#a78bfa;">{_pct:.1f}%</div>',
                unsafe_allow_html=True,
            )
            st.caption(f"Phương pháp: {_kmode}")

        # ── Row 3: Supporting signals and risk flags ──────────────────────────
        sup = rec.get("supporting_signals", [])
        flags = rec.get("risk_flags", [])
        if sup:
            chips = "".join(
                f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 8px;'
                f'border-radius:12px;background:#16a34a22;color:#22c55e;font-size:11px;">'
                f'✅ {s}</span>' for s in sup
            )
            st.markdown(f'<div>{chips}</div>', unsafe_allow_html=True)
        if flags:
            fchips = "".join(
                f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 8px;'
                f'border-radius:12px;background:#dc262622;color:#ef4444;font-size:11px;">'
                f'⚠️ {f}</span>' for f in flags
            )
            st.markdown(f'<div style="margin-top:4px;">{fchips}</div>', unsafe_allow_html=True)

        # ── Row 4 (informational): LSTM badge ─────────────────────────────────
        if rec.get("lstm_info"):
            st.markdown(
                f'<div style="margin-top:6px;color:#64748b;font-size:11px;">'
                f'🧠 {rec["lstm_info"]}</div>',
                unsafe_allow_html=True,
            )


def _embed_t_rec(result: dict) -> None:
    """Compute T+ recommendation and embed t_rec_* fields into result in-place (before audit save)."""
    if result.get("error") or not result.get("price"):
        return
    try:
        rec = generate_t_plus_recommendation(result)
        result["t_rec_action"]     = rec["action"]
        result["t_rec_grade"]      = rec["grade"]
        result["t_rec_score"]      = rec["confidence_score"]
        result["t_rec_entry_low"]  = rec["entry_zone_low"]
        result["t_rec_entry_high"] = rec["entry_zone_high"]
        result["t_rec_sl"]         = rec["sl_price"]
        result["t_rec_tp1"]        = rec["tp1_price"]
        result["t_rec_rr"]         = rec["rr_ratio"]
        result["t_rec_size_pct"]   = rec["position_size_pct"]
        result["t_rec_kelly"]      = rec["kelly_mode"]
        result["t_rec_timing"]     = rec["entry_timing"]
        result["t_rec_flags"]      = rec["risk_flags"]
        result["t_rec_signals"]    = rec["supporting_signals"]
        # Phase 7: new snapshot fields
        try:
            _ssi_snap               = compute_ssi_score(result)
            result["t_rec_ssi"]         = _ssi_snap.get("ssi")
            result["t_rec_ssi_grade"]   = _ssi_snap.get("ssi_grade")
        except Exception:
            pass
        result["rs_rating_snap"]   = result.get("rs_rating")
        result["gap_type_snap"]    = result.get("gap_type")
        result["structure_snap"]   = result.get("structure_label")
        result["vwap_snap"]        = result.get("vwap")
        result["ex_div_days_snap"] = result.get("ex_div_days")
    except Exception:
        pass


def render_audit_page() -> None:
    """Full audit history page — reads data/Profiler/*.json JSONL files."""
    all_tickers = _list_audit_tickers()

    if not all_tickers:
        st.info("📂 Chưa có dữ liệu audit. Hãy chạy phân tích ít nhất một lần.")
        return

    # ― Load latest entry per ticker ――――――――――――――――――――――――――――――――――――――
    latest_by_ticker: dict = {}
    all_runs_count = 0
    signal_changes = []
    last_scan_ts   = ""
    runs_count: dict = {}

    t_rec_changes = []
    for t in all_tickers:
        h = _load_audit_history(t)
        if not h:
            continue
        all_runs_count  += len(h)
        runs_count[t]    = len(h)
        latest_by_ticker[t] = h[0]
        if h[0].get("run_ts", "") > last_scan_ts:
            last_scan_ts = h[0].get("run_ts", "")
        if len(h) >= 2 and h[0].get("signal") != h[1].get("signal"):
            signal_changes.append({
                "ticker": t,
                "prev":   h[1].get("signal", ""),
                "curr":   h[0].get("signal", ""),
                "ts":     h[0].get("run_ts", ""),
            })
        if (len(h) >= 2
                and h[0].get("t_rec_action")
                and h[1].get("t_rec_action")
                and h[0].get("t_rec_action") != h[1].get("t_rec_action")):
            t_rec_changes.append({
                "ticker": t,
                "prev":   h[1].get("t_rec_action", ""),
                "prev_g": h[1].get("t_rec_grade",  ""),
                "curr":   h[0].get("t_rec_action", ""),
                "curr_g": h[0].get("t_rec_grade",  ""),
                "ts":     h[0].get("run_ts", ""),
            })

    # ― Overview metrics ――――――――――――――――――――――――――――――――――――――――――――――――
    st.markdown("### 🗂️ Audit Log — Lịch sử phân tích")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📁 Mã đang theo dõi",  len(latest_by_ticker))
    m2.metric("🔄 Tổng lần quét",     all_runs_count)
    m3.metric("⚠️ Thay đổi tín hiệu", len(signal_changes))
    m4.metric("⏱ Lần quét cuối",      last_scan_ts[:16].replace("T", " ") if last_scan_ts else "–")

    # ─ T+ recommendation changes alert ────────────────────────────────────
    if t_rec_changes:
        t_chips = ""
        for ch in t_rec_changes:
            pc_ = _T_REC_COLORS.get(ch["prev"], "#94a3b8")
            cc_ = _T_REC_COLORS.get(ch["curr"], "#94a3b8")
            t_chips += (
                f'<span style="display:inline-flex;align-items:center;gap:5px;'
                f'background:#1a1f2e;border:1px solid #2d3347;border-radius:6px;'
                f'padding:4px 10px;margin:3px;font-size:12px;font-weight:700;">'
                f'<b>🎯 {ch["ticker"]}</b> '
                f'<span style="color:{pc_};">{ch["prev"]}({ch["prev_g"]})</span>'
                f' → <span style="color:{cc_};">{ch["curr"]}({ch["curr_g"]})</span>'
                f'</span>'
            )
        st.markdown(
            f'<div style="margin:4px 0 8px;"><span style="font-size:12px;color:#a78bfa;font-weight:600;">'
            f'🎯 T+ Khuyến nghị thay đổi:</span><br>{t_chips}</div>',
            unsafe_allow_html=True,
        )

    # ― Signal changes alert ――――――――――――――――――――――――――――――――――――――――――――
    if signal_changes:
        chips = ""
        for ch in signal_changes:
            prev_c = _audit_signal_color(ch["prev"])
            curr_c = _audit_signal_color(ch["curr"])
            chips += (
                f'<span style="display:inline-flex;align-items:center;gap:5px;'
                f'background:#1a1f2e;border:1px solid #2d3347;border-radius:6px;'
                f'padding:4px 10px;margin:3px;font-size:12px;font-weight:700;">'
                f'<b>{ch["ticker"]}</b> '
                f'<span style="color:{prev_c};">{ch["prev"]}</span>'
                f' → <span style="color:{curr_c};">{ch["curr"]}</span>'
                f'</span>'
            )
        st.markdown(
            f'<div style="margin:6px 0 10px;"><span style="font-size:12px;color:#f97316;font-weight:600;">'
            f'⚡ Tín hiệu thay đổi kể từ lần quét trước:</span><br>{chips}</div>',
            unsafe_allow_html=True,
        )

    # ═══ FILTER BAR ══════════════════════════════════════════════════════
    st.markdown("---")
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 1])
    with fc1:
        _SIG_ALL = "— Tất cả tín hiệu —"
        _SIG_OPTIONS = [_SIG_ALL, "MUA", "THEO DÕI–TĂNG", "TRUNG LẬP", "THEO DÕI–GIẢM", "BÁN / TRÁNH"]
        sig_filter = st.selectbox("🔔 Lọc theo tín hiệu", _SIG_OPTIONS,
                                  key="audit_sig_filter")
    with fc2:
        ticker_filter_raw = st.text_input("🔍 Lọc theo mã (phân cách bằng dấu phẩy)",
                                          placeholder="VD: HPG, TCH, CII",
                                          key="audit_ticker_filter")
        ticker_filter = {t.strip().upper() for t in ticker_filter_raw.split(",") if t.strip()}
    with fc3:
        _DATE_ALL = "— Tất cả ngày —"
        _all_dates = sorted(
            {(r.get("run_ts") or "")[:10] for r in latest_by_ticker.values()
             if (r.get("run_ts") or "")[:10]},
            reverse=True,
        )
        date_filter = st.selectbox("📅 Ngày quét", [_DATE_ALL] + _all_dates,
                                   key="audit_date_filter")
    with fc4:
        sort_by = st.selectbox("📶 Sắp xếp", ["Tín hiệu", "T+ Score↓", "Bull %↓", "Giá↓", "Thay đổi↓", "Mã A→Z"],
                               key="audit_sort")

    # Extra: T+ action filter
    _TREC_ALL = "— Tất cả T+ action —"
    _TREC_OPTIONS = [_TREC_ALL, "STRONG_BUY", "BUY", "WATCH", "SKIP", "AVOID"]
    t_rec_filter = st.selectbox("🎯 Lọc theo T+ Rec", _TREC_OPTIONS, key="audit_trec_filter")

    # ― Apply filters ―――――――――――――――――――――――――――――――――――――――――――――――――――
    filtered = [
        r for r in latest_by_ticker.values()
        if "error" not in r
        and (not ticker_filter or r["ticker"] in ticker_filter)
        and (sig_filter == _SIG_ALL or r.get("signal", "") == sig_filter)
        and (date_filter == _DATE_ALL or (r.get("run_ts") or "")[:10] == date_filter)
        and (t_rec_filter == _TREC_ALL or r.get("t_rec_action", "") == t_rec_filter)
    ]

    _SIG_ORDER = ["MUA", "THEO DÕI–TĂNG", "TRUNG LẬP", "THEO DÕI–GIẢM", "BÁN / TRÁNH", ""]
    def _sig_rank(r): return _SIG_ORDER.index(r.get("signal","")) if r.get("signal","") in _SIG_ORDER else 99
    if sort_by == "Tín hiệu":
        filtered.sort(key=_sig_rank)
    elif sort_by == "T+ Score↓":
        filtered.sort(key=lambda r: r.get("t_rec_score") or 0, reverse=True)
    elif sort_by == "Bull %↓":
        filtered.sort(key=lambda r: r.get("bull_pct", 0) or 0, reverse=True)
    elif sort_by == "Giá↓":
        filtered.sort(key=lambda r: r.get("price") or 0, reverse=True)
    elif sort_by == "Thay đổi↓":
        filtered.sort(key=lambda r: r.get("pct_change") or 0, reverse=True)
    else:
        filtered.sort(key=lambda r: r["ticker"])

    st.markdown(f"<span style='font-size:12px;color:#64748b;'>Hiển thị {len(filtered)} / {len(latest_by_ticker)} mã</span>",
                unsafe_allow_html=True)

    # ― Snapshot table (filtered) ――――――――――――――――――――――――――――――――――――――――
    st.markdown("##### 📊 Snapshot các mã đang theo dõi (lần quét mới nhất)")
    if not filtered:
        st.info("Không có mã nào khớp với bộ lọc.")
    else:
        rows_html = "".join(
            _audit_snapshot_row_html(r, runs_count.get(r["ticker"], 0))
            for r in filtered
        )
        audit_snap_html = f'''
<table class="sum-table">
  <thead>
    <tr>
      <th>Mã</th><th>Giá</th><th>%Δ</th>
      <th>Tín hiệu</th><th>Bull %</th>
      <th>Regime</th><th>VSA</th><th>Xác nhận</th>
      <th title="T+ Khuyến nghị">🎯 T+ Rec</th>
      <th>Dự báo</th><th>Lần quét cuối</th><th>Số lần</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
'''
        st.markdown(_filterable_table("audit_snap_tbl", audit_snap_html), unsafe_allow_html=True)

    # ― Per-ticker drilldown ――――――――――――――――――――――――――――――――――――――――――――――――
    st.markdown("---")
    st.markdown("##### 🔍 Lịch sử chi tiết theo mã")

    drilldown_options = [r["ticker"] for r in filtered] or all_tickers
    sel = st.selectbox(
        "Chọn mã cổ phiếu để xem chi tiết",
        options=drilldown_options,
        format_func=lambda t: f"{t}  —  {(latest_by_ticker.get(t) or {}).get('signal', '')}",
        key="audit_sel_ticker",
    )

    if sel:
        hist = _load_audit_history(sel)
        if not hist:
            st.warning(f"Không tìm thấy dữ liệu cho {sel}.")
        else:
            hist_asc   = list(reversed(hist))
            latest_run = hist[0]

            # ── Summary metrics ───────────────────────────────────────────
            lc1,lc2,lc3,lc4,lc5 = st.columns(5)
            lc1.metric("Giá mới nhất",  _f(latest_run.get("price")))
            lc2.metric("Tín hiệu",      latest_run.get("signal", "–"))
            lc3.metric("Bull %",        f'{latest_run.get("bull_pct", 0):.0f}%')
            lc4.metric("Regime",        latest_run.get("regime_label") or latest_run.get("regime", "–"))
            lc5.metric("Số lần quét",   len(hist))

            # ── Trend chart ───────────────────────────────────────────────
            if len(hist_asc) >= 2:
                st.plotly_chart(
                    _build_audit_trend_chart(hist_asc),
                    use_container_width=True,
                    config={"displayModeBar": False},
                    key=f"audit_trend_{sel}",
                )

            # ── Per-run detail expanders ──────────────────────────────────
            st.markdown(f"**{len(hist)} lần quét** — nhấn vào từng dòng để xem đầy đủ chi tiết:")
            for i, row in enumerate(hist):
                prev = hist[i + 1] if i < len(hist) - 1 else None
                _audit_detail_expander(row, i, prev)


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
def render_sidebar():
    with st.sidebar:
        st.markdown("""
<div style="text-align:center;padding:10px 0 18px;">
  <div style="font-size:36px;line-height:1;">📊</div>
  <div style="font-size:17px;font-weight:800;letter-spacing:1.5px;margin-top:6px;">
    QUANT PROFILER</div>
  <div style="font-size:11px;color:#475569;margin-top:4px;">
    Vietnam Stock · Technical Analysis</div>
</div>
""", unsafe_allow_html=True)

        # ── Watchlist nhanh ───────────────────────────────────────────────
        _WATCHLIST_GROUPS = {
            "VN30 Blue-chip":  "HPG,VNM,VCB,BID,CTG,TCB,VHM,VIC,MBB,ACB,FPT,GAS,SAB,VJC,PLX,REE,MWG,PNJ,MSN,VRE",
            "Ngân hàng":       "VCB,BID,CTG,MBB,TCB,ACB,VPB,HDB,LPB,SHB,STB,TPB,OCB,MSB,VIB,EIB,SSB",
            "BDS + Xay dung":  "VHM,NVL,PDR,DIG,KDH,TCH,NLG,DXG,CTD,HBC,VCG,DPG,CII",
            "Nang luong":      "GAS,PLX,POW,NT2,GEG,REE,PC1,PVD,PVT,BSR",
            "Cong nghe":       "FPT,CMG,ELC,VNG,ICT",
            "Tieu dung + BL":  "VNM,MSN,SAB,MWG,PNJ,FRT,KDC,DBC,VHC,ANV",
            "Chung khoan":     "SSI,VCI,VND,HCM,MBS,FTS,VIX,ORS",
        }
        with st.expander("📋 Watchlist nhanh", expanded=False):
            for _grp_name, _grp_tickers in _WATCHLIST_GROUPS.items():
                if st.button(_grp_name, key=f"wl_{_grp_name.replace(' ','_')}",
                             use_container_width=True):
                    st.session_state["ticker_input"] = _grp_tickers

        ticker_input = st.text_area(
            "🔍 Mã cổ phiếu",
            placeholder="VD:  HPG, TCH, CII, MSN, VNM",
            help="Nhập một hoặc nhiều mã, phân cách bằng dấu phẩy",
            height=76, key="ticker_input",
        )

        days = st.select_slider(
            "📅 Lịch sử",
            options=[200, 400, 600],
            value=400,
            format_func=lambda d: f"{d} ngày (~{d // 252} năm)",
        )

        col_a, col_b = st.columns(2)
        with col_a:
            show_bb  = st.toggle("BB Bands", value=True)
        with col_b:
            show_ema = st.toggle("EMA 9/21", value=False)
        show_levels = st.toggle("Entry / SL / TP trên biểu đồ", value=True)

        analyse_btn = st.button("▶  Phân tích", type="primary", use_container_width=True)

        if st.button("🗑  Xoá cache", use_container_width=True):
            st.cache_data.clear()
            st.toast("Cache đã xoá.", icon="✅")

        st.markdown("---")
        page = st.radio(
            "Trang",
            [
                "📊 Phân tích",
                "📂 Portfolio Hub",
                "📡 Scanner",
                "🗂 Audit Log",
                "🎯 T+ Khuyến nghị",
                "🔄 Quản lý lệnh",
                "🌡️ Sector Flow",
                "🔔 Cảnh báo",
                "📓 Trade Journal",
            ],
            horizontal=False,
            label_visibility="collapsed",
            key="nav_page",
        )
        st.markdown("---")
        st.markdown("""
<div style="font-size:11.5px;color:#475569;line-height:2;">
<b style="color:#64748b;letter-spacing:.5px;">PIPELINE DATA</b><br>
⚡ DNSE → SSI → CafeF (OHLCV)<br>
📡 SSI iboard-query (Real-time)<br>
🕐 Cache: 5 phút<br><br>
<b style="color:#64748b;letter-spacing:.5px;">INDICATORS</b><br>
SMA 5/10/20/50/200<br>
EMA 9/21/50/200<br>
RSI · Stoch · MACD<br>
BB · ATR · ADX/±DI<br>
OBV · Williams %R · CCI
</div>
""", unsafe_allow_html=True)

    return ticker_input, days, show_bb, show_ema, show_levels, analyse_btn, page


# ═══════════════════════════════════════════════════════════════════════════════
#  WELCOME SCREEN
# ═══════════════════════════════════════════════════════════════════════════════
def render_welcome() -> None:
    st.markdown("""
<div style="text-align:center;padding:48px 16px 0;">
  <div style="font-size:56px;line-height:1;margin-bottom:12px;">📊</div>
  <h1 style="font-size:34px;font-weight:800;margin-bottom:6px;letter-spacing:-0.5px;">Quant Profiler</h1>
  <p style="font-size:16px;color:#64748b;max-width:480px;margin:0 auto 36px;line-height:1.7;">
    Phân tích kỹ thuật cổ phiếu Việt Nam<br>
    <span style="font-size:13px;">DNSE · SSI iboard-api · SSI iboard-query · CafeF</span>
  </p>
</div>

<div class="welcome-grid">
  <div class="welcome-card">
    <div class="welcome-icon">📡</div>
    <div class="welcome-title">Dữ liệu thực</div>
    <div class="welcome-body">
      DNSE → SSI → CafeF<br>400 ngày lịch sử OHLCV<br>Giá real-time SSI iboard
    </div>
  </div>
  <div class="welcome-card">
    <div class="welcome-icon">📈</div>
    <div class="welcome-title">11 Indicators</div>
    <div class="welcome-body">
      RSI · Stoch · MACD<br>BB · ATR · ADX/±DI<br>OBV · Williams %R · CCI
    </div>
  </div>
  <div class="welcome-card">
    <div class="welcome-icon">🎯</div>
    <div class="welcome-title">Kế hoạch giao dịch</div>
    <div class="welcome-body">
      Entry / SL / TP1 / TP2<br>ATR-based sizing<br>Risk : Reward ratio
    </div>
  </div>
</div>
<p style="text-align:center;color:#475569;font-size:14px;margin-top:36px;">
  ← Nhập mã cổ phiếu vào thanh bên trái và nhấn <b>Phân tích</b>
</p>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  PER-TICKER RENDER
# ═══════════════════════════════════════════════════════════════════════════════
def _chip_html(r: dict) -> str:
    if "error" in r:
        return f'<span class="ticker-chip chip-err">&#x274C; {r["ticker"]}</span>'
    _chip_cls = {
        "MUA":           "chip-buy",
        "THEO DÕI–TĂNG": "chip-watchup",
        "TRUNG LẬP":    "chip-neutral",
        "THEO DÕI–GIẢM": "chip-watchdn",
        "BÁN / TRÁNH":  "chip-sell",
    }
    cls = _chip_cls.get(r.get("signal", ""), "chip-neutral")
    sym = r.get("signal_sym", "⚪")
    pct = r.get("pct_change", 0) or 0
    pct_s = f"{'+' if pct >= 0 else ''}{pct:.1f}%"
    return (
        f'<span class="ticker-chip {cls}">'
        f'{sym} {r["ticker"]}'
        f'<span style="font-size:11px;font-weight:500;opacity:.75;"> {pct_s}</span>'
        f'</span>'
    )


def render_ticker_chips(results: list) -> None:
    """Compact coloured chips row showing all analysed tickers + their signals."""
    chips = "".join(_chip_html(r) for r in results)
    st.markdown(
        f'<div class="ticker-chips">{chips}</div>',
        unsafe_allow_html=True,
    )


def render_smart_money(r: dict, df: pd.DataFrame) -> None:
    """Smart Money Analysis section: VSA · MFI · Wyckoff · BiLSTM weekly forecast."""
    if df is None or df.empty or len(df) < 30:
        return

    st.markdown("---")
    st.markdown(
        '<div class="section-hdr">🧠 Smart Money Analysis — VSA · MFI · Dự báo tuần</div>',
        unsafe_allow_html=True,
    )

    with st.spinner("Đang tính Smart Money..."):
        try:
            sig_score = r.get("score", 0)
            smi  = compute_smart_money_index(df)
            vsa  = detect_vsa_patterns(df)
            phase = detect_wyckoff_phase(
                df,
                _vsa_label=vsa.get("label", ""),
                _mfi=smi.get("mfi_latest", 50.0),
            )
            fc = forecast_weekly_direction(df, sig_score, symbol=r.get("ticker", ""))
        except Exception:
            st.info("Không thể tính Smart Money cho mã này.")
            return

    # ── Row 1: three headline metrics ───────────────────────────────────
    sm1, sm2, sm3 = st.columns(3)
    smi_score = smi.get("smi_score", 0)
    smi_col   = smi.get("smi_color", "#6B7280")
    smi_lbl   = smi.get("smi_label", "N/A")
    mfi_v     = smi.get("mfi_latest", 50.0)
    ph_lbl    = phase.get("label_vi", "Không xác định")
    ph_col    = phase.get("color",   "#6B7280")

    with sm1:
        st.markdown(f"""
        <div style="text-align:center;padding:8px;">
          <div style="font-size:11px;color:#6B7280;margin-bottom:4px;">Smart Money Index</div>
          <div style="font-size:32px;font-weight:700;color:{smi_col};">{smi_score:+d}</div>
          <span style="background:{smi_col}22;color:{smi_col};padding:2px 8px;
            border-radius:5px;font-size:12px;font-weight:500;">{smi_lbl}</span>
        </div>""", unsafe_allow_html=True)
    with sm2:
        st.markdown(f"""
        <div style="text-align:center;padding:8px;">
          <div style="font-size:11px;color:#6B7280;margin-bottom:4px;">Pha Wyckoff</div>
          <div style="font-size:15px;font-weight:600;color:{ph_col};margin-bottom:4px;">
            {ph_lbl}
          </div>
          <div style="font-size:11px;color:#9CA3AF;">{phase.get('detail','')[:60]}</div>
        </div>""", unsafe_allow_html=True)
    with sm3:
        mfi_col = (
            "#16A34A" if mfi_v > 60
            else "#DC2626" if mfi_v < 40
            else "#6B7280"
        )
        st.markdown(f"""
        <div style="text-align:center;padding:8px;">
          <div style="font-size:11px;color:#6B7280;margin-bottom:4px;">MFI (14)</div>
          <div style="font-size:32px;font-weight:700;color:{mfi_col};">{mfi_v:.1f}</div>
          <div style="font-size:11px;color:#9CA3AF;">
            {'Mua mạnh' if mfi_v > 70 else 'Bán mạnh' if mfi_v < 30 else 'Trung tính'}
          </div>
        </div>""", unsafe_allow_html=True)

    # ── VSA pattern alert ───────────────────────────────────────────────────────────────
    vsa_lbl = vsa.get("label",    "NEUTRAL")
    vsa_lv  = vsa.get("label_vi", "Trung tính")
    vsa_det = vsa.get("detail",   "")
    vsa_dir = vsa.get("signal_dir", 0)
    vsa_ac  = (
        "alert-ok"     if vsa_dir > 0
        else "alert-danger" if vsa_dir < 0
        else "alert-warn"
    )
    icon_v = "📈" if vsa_dir > 0 else ("📉" if vsa_dir < 0 else "📊")
    st.markdown(
        f'<div class="{vsa_ac}">'
        f'<b>{icon_v} VSA Wyckoff: {vsa_lv}</b> — {vsa_det}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Weekly forecast card ─────────────────────────────────────────────────────────
    direction   = fc.get("direction",     "NEUTRAL")
    confidence  = fc.get("confidence_pct", 0)
    tgt         = fc.get("target_pct",     0.0)
    stp         = fc.get("stop_pct",      -2.0)
    bilstm_prob = fc.get("bilstm_prob")
    bilstm_stat = fc.get("bilstm_status", "UNAVAILABLE")
    rationale   = fc.get("rationale",     [])

    dir_col  = (
        "#16A34A" if direction == "BULLISH"
        else "#DC2626" if direction == "BEARISH"
        else "#6B7280"
    )
    dir_icon = "🟢" if direction == "BULLISH" else ("🔴" if direction == "BEARISH" else "🟡")
    dir_vi   = (
        "TĂNG" if direction == "BULLISH"
        else "GIẢM" if direction == "BEARISH"
        else "TRUNG LẬP"
    )

    st.markdown(f"""
    <div style="border:1.5px solid {dir_col};border-radius:10px;
         padding:14px 18px;margin:10px 0;">
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:10px;">
        <div style="font-size:22px;font-weight:800;color:{dir_col};">
          {dir_icon} Dự báo tuần tới: {dir_vi}
        </div>
        <span style="background:{dir_col}22;color:{dir_col};padding:3px 10px;
          border-radius:5px;font-size:13px;font-weight:600;">Confidence {confidence}%</span>
      </div>
      <div style="display:flex;gap:24px;font-size:13px;margin-bottom:8px;">
        <span>🎯 Target: <b style="color:{dir_col}">{tgt:+.2f}%</b></span>
        <span>🛑 Stop: <b style="color:#DC2626">{stp:.2f}%</b></span>
      </div>
    </div>""", unsafe_allow_html=True)

    st.progress(confidence / 100, text=f"Confidence level: {confidence}%")

    if rationale:
        st.markdown("**Cơ sở phân tích:**")
        for item in rationale:
            st.markdown(f"• {item}")

    comps = smi.get("components", {})
    if comps:
        with st.expander("Phân tích chi tiết SMI theo thành phần"):
            for cname, (clbl, cpts) in comps.items():
                cc = "#16A34A" if cpts > 0 else "#DC2626" if cpts < 0 else "#6B7280"
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:3px 0;border-bottom:0.5px solid #E5E7EB;font-size:12px;">'
                    f'<span><b style="color:#374151;">{cname}</b> — {clbl}</span>'
                    f'<span style="color:{cc};font-weight:600;">{cpts:+d}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    bstat_ui = {
        "ACTIVE":      ("✅ BiLSTM model đang hoạt động",          "#16A34A"),
        "TRAINING":    ("⏳ BiLSTM: đang huấn luyện lần đầu...",   "#F59E0B"),
        "FALLBACK":    ("🔄 BiLSTM fallback — dùng heuristic",     "#6B7280"),
        "UNAVAILABLE": ("📦 BiLSTM không khả dụng (cần TensorFlow)","#9CA3AF"),
    }.get(bilstm_stat, ("–", "#9CA3AF"))
    bi_lbl, bi_col = bstat_ui
    extra = f" — Xác suất tăng: {bilstm_prob*100:.0f}%" if bilstm_prob is not None else ""
    st.caption(
        f'<span style="color:{bi_col};font-size:11px;">{bi_lbl}{extra}</span>'
        ' &nbsp;|&nbsp; Dựa trên Wyckoff VSA + VN-MFI. <i>Không phải tư vấn đầu tư.</i>',
        unsafe_allow_html=True,
    )


def render_trend_warning(r: dict, df: pd.DataFrame) -> None:
    """
    TTWE — Trend Transition Warning Engine panel.

    Shows: state badge, confidence badge, score meters, evidence pills,
    rationale, and a research disclaimer.
    """
    tw = compute_trend_warning(r, df)

    state = tw["state"]
    color = tw["state_color"]
    label = tw["state_label"]
    conf  = tw["confidence"]
    ev    = tw["evidence"]
    rat   = tw["rationale"]
    exh   = tw["exhaustion_score"]
    eme   = tw["emergence_score"]

    _CONF_COLORS = {"LOW": "#ffd740", "MEDIUM": "#ff9800", "HIGH": "#e53935"}
    conf_color   = _CONF_COLORS.get(conf, "#90a4ae")
    conf_txt_col = "#111111" if conf in ("LOW", "MEDIUM") else "#ffffff"

    st.markdown("---")
    st.markdown("### 🔁 Trend Transition Warning Engine (TTWE)")

    # ── State badge + confidence + scores ────────────────────────────────────
    col_badge, col_conf, col_scores = st.columns([3, 1, 2])
    with col_badge:
        st.markdown(
            f'<div style="background:{color};color:#fff;padding:10px 18px;'
            f'border-radius:8px;font-weight:700;font-size:1.05rem;display:inline-block">'
            f'{label}</div>',
            unsafe_allow_html=True,
        )
    with col_conf:
        st.markdown(
            f'<div style="background:{conf_color};color:{conf_txt_col};padding:10px 12px;'
            f'border-radius:8px;font-weight:700;text-align:center;font-size:0.9rem">'
            f'Độ tin cậy<br><b>{conf}</b></div>',
            unsafe_allow_html=True,
        )
    with col_scores:
        st.markdown(
            f'<div style="padding:10px 0;font-size:0.88rem;color:#b0bec5">'
            f'Exhaustion score: <b style="color:#ffab40">{exh}</b>'
            f'&nbsp;&nbsp;|&nbsp;&nbsp;'
            f'Emergence score: <b style="color:#29b6f6">{eme}</b></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Evidence pills ────────────────────────────────────────────────────────
    if ev:
        pills_html = " ".join(
            f'<span style="background:#263238;color:#e0e0e0;padding:3px 10px;'
            f'border-radius:12px;font-size:0.8rem;margin:2px;display:inline-block">'
            f'{e}</span>'
            for e in ev
        )
        st.markdown(
            f'<div style="margin-bottom:6px"><b>Tín hiệu đã kích hoạt:</b><br>{pills_html}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="color:#78909c;font-size:0.88rem;margin-bottom:6px">'
            '<i>Không có tín hiệu nào kích hoạt ở phiên này.</i></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Rationale ─────────────────────────────────────────────────────────────
    if rat and state != INSUFFICIENT_DATA:
        st.info(f"**Phân tích TTWE:** {rat}")
    elif state == INSUFFICIENT_DATA:
        st.warning(f"⚠️ {rat}")

    # ── Disclaimer ────────────────────────────────────────────────────────────
    st.caption(
        "⚠️ TTWE là hệ thống cảnh báo phân tích kỹ thuật, không phải khuyến nghị giao dịch. "
        "Divergence là tín hiệu cảnh báo sớm — luôn chờ xác nhận cấu trúc hoặc khối lượng "
        "trước khi hành động. Kết quả quá khứ không đảm bảo hiệu suất tương lai."
    )


def render_ticker_section(r: dict, dfs: dict, show_bb, show_ema, show_levels) -> None:
    if "error" in r:
        st.error(f"❌ **{r['ticker']}**: {r['error']}")
        return

    ticker = r["ticker"]
    df     = dfs.get(ticker, pd.DataFrame())

    # Price header
    render_price_header(r)

    # Chart
    if not df.empty:
        fig = build_chart(df, r, show_bb=show_bb, show_ema=show_ema, show_levels=show_levels)
        st.plotly_chart(fig, use_container_width=True, config={
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["autoScale2d", "lasso2d", "select2d"],
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png", "filename": f"quant_{ticker}",
                "height": 700, "width": 1400, "scale": 2,
            },
        }, key=f"chart_{ticker}")
    else:
        st.warning("Không có dữ liệu biểu đồ.")

    # Indicator cards
    render_indicator_cards(r)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # MA table | Trade plan + Commentary
    col_l, col_r = st.columns([1, 1], gap="medium")
    with col_l:
        st.markdown("##### 📊 Moving Averages")
        render_ma_table(r)
    with col_r:
        st.markdown("##### 🎯 Kế hoạch giao dịch  (ATR-based)")
        render_trade_plan(r)
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        st.markdown("##### 📝 Nhận xét phân tích")
        render_commentary(r)

    render_position_sizing(r)
    render_backtest(r)
    render_monte_carlo(r, df)
    render_forecast_horizons(r, df)
    render_t_plus_recommendation(r)
    render_smart_money(r, df)
    render_trend_warning(r, df)
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  PORTFOLIO HUB
# ═══════════════════════════════════════════════════════════════════════════════

def render_portfolio_hub() -> None:
    """Portfolio Hub: CSV upload → T+2.5 settlement → P&L attribution."""
    st.markdown("## 📂 Portfolio Hub")
    st.caption("Tải file danh mục từ SSI/DNSE → phân tích P&L và trạng thái T+2 KRX tự động.")

    # ── Upload or manual entry ────────────────────────────────────────────────
    col_up, col_info = st.columns([2, 1])
    with col_up:
        uploaded = st.file_uploader(
            "📁 Tải lên file danh mục (CSV hoặc XLSX)",
            type=["csv", "xlsx", "xls"],
            help="File từ SSI iBoard / Saturn. Hỗ trợ cả .xlsx và .csv.",
            key="portfolio_upload",
        )
    with col_info:
        st.markdown("""
<div style="background:#141824;border:1px solid #2d3347;border-radius:8px;padding:12px;font-size:12px;color:#94a3b8;line-height:1.8;">
<b style="color:#e2e8f0;">Định dạng hỗ trợ:</b><br>
• <b style="color:#60a5fa;">SSI iBoard XLSX</b> — xuất từ mục Danh mục<br>
• SSI Saturn / DNSE CSV export<br>
• Cột cần có: <code>Mã CK</code>, <code>SL</code>, <code>Giá vốn</code><br>
• Hoặc nhập tay bên dưới<br>
<b style="color:#fbbf24;">T+2 KRX:</b> Cổ phiếu mua hôm nay về sau 2 phiên
</div>
""", unsafe_allow_html=True)

    # Manual entry fallback
    with st.expander("✏️ Nhập tay danh mục (nếu không có file)", expanded=not uploaded):
        manual_txt = st.text_area(
            "Nhập theo định dạng:  MÃ,SỐ_LƯỢNG,GIÁ_VỐN  (mỗi dòng một mã)",
            placeholder="HPG,1000,20000\nVNM,500,60000\nTCH,2000,15000",
            height=120,
            key="portfolio_manual",
        )

    # ── Parse holdings ────────────────────────────────────────────────────────
    holdings = None
    if uploaded is not None:
        try:
            holdings = parse_portfolio_csv(uploaded)
            st.success(f"✅ Đọc thành công {len(holdings)} mã từ file.")
        except Exception as e:
            st.error(f"❌ Không đọc được file: {e}")
            st.info("💡 Thử nhập tay bên dưới hoặc kiểm tra lại định dạng CSV.")
    elif manual_txt and manual_txt.strip():
        rows = []
        for line in manual_txt.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                try:
                    rows.append({
                        "ticker":     parts[0].upper(),
                        "qty":        float(parts[1].replace(",", "")),
                        "avg_cost":   float(parts[2].replace(",", "")),
                        "trade_date": None,
                        "sector":     "",
                    })
                except ValueError:
                    pass
        if rows:
            holdings = pd.DataFrame(rows)
            st.info(f"📝 {len(holdings)} mã từ nhập tay.")

    if holdings is None or holdings.empty:
        st.markdown("""
<div style="text-align:center;padding:48px;color:#475569;">
    <div style="font-size:48px;">📂</div>
    <p style="font-size:15px;margin-top:12px;">Chưa có danh mục. Tải file hoặc nhập tay bên trên.</p>
</div>
""", unsafe_allow_html=True)
        return

    # ── T+2 settlement status ─────────────────────────────────────────────────
    from datetime import date as _date
    holdings = classify_settlement_status(holdings, today=_date.today())

    # ── Show editable holdings table ──────────────────────────────────────────
    st.markdown("##### 📋 Danh mục (có thể chỉnh sửa)")
    editable = st.data_editor(
        holdings[["ticker", "qty", "avg_cost", "trade_date", "status"]].rename(columns={
            "ticker": "Mã", "qty": "Số lượng", "avg_cost": "Giá vốn BQ",
            "trade_date": "Ngày GD", "status": "Trạng thái T+2",
        }),
        use_container_width=True,
        hide_index=True,
        key="portfolio_editor",
    )
    # Apply any user edits from the table back to holdings (internal column names)
    holdings = editable.rename(columns={
        "Mã": "ticker", "Số lượng": "qty", "Giá vốn BQ": "avg_cost",
        "Ngày GD": "trade_date", "Trạng thái T+2": "status",
    })

    # ── Fetch current prices — button-gated, cached in session state ─────────
    # Fetching on every Streamlit rerender would block the UI on each interaction.
    # Instead: cache prices in session_state and only re-fetch on explicit button click.
    import concurrent.futures as _cf
    tickers_list = list(holdings["ticker"].dropna().str.upper().unique())
    _price_key   = "portfolio_price_cache"

    btn_col, ts_col = st.columns([1, 3])
    with btn_col:
        do_fetch = st.button("🔄 Cập nhật giá", key="portfolio_refresh", type="primary")
    with ts_col:
        _cached = st.session_state.get(_price_key)
        if _cached:
            st.caption(f"📅 Giá cập nhật lúc {_cached['ts']}  ·  {len(_cached['prices'])} mã")
        else:
            st.caption("⚠️ Chưa có giá — nhấn **🔄 Cập nhật giá** để tải.")

    if do_fetch or _price_key not in st.session_state:
        def _fetch_price(tk):
            try:
                rt = fetch_ssi_realtime(tk)
                return tk, (rt.get("price") or 0) if rt else 0
            except Exception:
                return tk, 0
        with st.spinner(f"⏳ Lấy giá {len(tickers_list)} mã (song song)..."):
            with _cf.ThreadPoolExecutor(max_workers=6) as _pool:
                _prices = dict(_pool.map(_fetch_price, tickers_list))
        st.session_state[_price_key] = {
            "prices": _prices,
            "ts": datetime.now().strftime("%H:%M:%S"),
        }

    _cached = st.session_state.get(_price_key)
    if not _cached:
        st.info("💡 Nhấn **🔄 Cập nhật giá** để tính P&L và hiển thị biểu đồ.")
        return
    price_map = _cached["prices"]

    # ── Calculate performance ─────────────────────────────────────────────────
    perf_df  = calculate_performance(holdings, price_map)
    summary  = build_portfolio_summary(perf_df)

    # ── KPI tiles ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("##### 📊 Tổng quan danh mục")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Giá trị thị trường",
        f"{summary['total_value']:,.0f} ₫",
    )
    k2.metric(
        "Vốn đầu tư",
        f"{summary['total_cost']:,.0f} ₫",
    )
    pnl_val = summary["total_pnl"]
    pnl_pct = summary["total_pnl_pct"]
    k3.metric(
        "Lãi/Lỗ chưa thực hiện",
        f"{pnl_val:+,.0f} ₫",
        delta=f"{pnl_pct:+.2f}%",
        delta_color="normal",
    )
    k4.metric(
        "Số mã",
        str(summary["position_count"]),
        delta=f"🏆 {summary['top_gainer']} ({summary['top_gainer_pct']:+.1f}%)" if summary["top_gainer"] else None,
        delta_color="off",
    )

    # ── T+2.5 Holdings table ──────────────────────────────────────────────────
    st.markdown("##### 🕐 Chi tiết P&L + Trạng thái T+2")

    _STATUS_HTML = {
        "settled":    '<span style="color:#22c55e;font-weight:700;">✅ Đã khớp</span>',
        "t1_pending": '<span style="color:#f97316;font-weight:700;">⏳ T+1 Chờ về</span>',
        "t2_pending": '<span style="color:#ef4444;font-weight:700;">⏰ T+2 Chờ về</span>',
    }
    rows_html = ""
    for _, row in perf_df.sort_values("portfolio_weight", ascending=False).iterrows():
        cp     = row.get("current_price", 0)
        ac     = row.get("avg_cost", 0)
        pnl    = row.get("unrealized_pnl", 0)
        pnl_p  = row.get("pnl_pct", 0)
        wt     = row.get("portfolio_weight", 0)
        avail  = row.get("price_available", True)
        stat   = _STATUS_HTML.get(row.get("status", "settled"), "")
        pnl_c  = "color:#22c55e" if pnl >= 0 else "color:#ef4444"
        cp_s   = f"{cp:,.0f}" if avail else "–"
        pnl_s  = f"{pnl:+,.0f}" if avail else "–"
        pnlp_s = f"{pnl_p:+.2f}%" if avail else "–"
        rows_html += (
            f'<tr>'
            f'<td><b>{row["ticker"]}</b></td>'
            f'<td style="font-family:monospace;">{int(row["qty"]):,}</td>'
            f'<td style="font-family:monospace;">{ac:,.0f}</td>'
            f'<td style="font-family:monospace;">{cp_s}</td>'
            f'<td style="font-family:monospace;{pnl_c}">{pnl_s}</td>'
            f'<td style="font-family:monospace;{pnl_c}">{pnlp_s}</td>'
            f'<td style="font-family:monospace;">{wt:.1f}%</td>'
            f'<td>{row.get("sector","")}</td>'
            f'<td>{stat}</td>'
            f'</tr>'
        )
    st.markdown(
        f'<table class="sum-table"><thead><tr>'
        f'<th>Mã</th><th>SL</th><th>Giá vốn</th><th>Giá hiện tại</th>'
        f'<th>Lãi/Lỗ (₫)</th><th>Lãi/Lỗ (%)</th><th>Tỷ trọng</th><th>Ngành</th><th>T+2 KRX</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )

    # ── VN-Swing Alpha T+2.5 Exit Recommendations ──────────────────────────────
    st.markdown("---")
    st.markdown("##### 🎯 VN-Swing Alpha — Khuyến nghị Exit T+2.5")
    st.caption(
        "Tính toán dựa trên ATR, regime và backtest win rate từ lần phân tích gần nhất. "
        "Cần cập nhật giá trước | Ngày GD = số phiên kể từ ngày mua."
    )
    from datetime import date as _date_hub
    _today_hub = _date_hub.today()
    _ACTION_ICON = {
        "HOLD":       "🟡 Giữ",
        "SELL_ALL":   "🔴 Bán Hết",
        "SELL_60PCT": "🟠 Bán 60%",
        "SELL_50PCT": "🟠 Bán 50%",
    }
    _exit_rows = ""
    for _, _row in perf_df.iterrows():
        _tk  = _row["ticker"]
        _ac  = _row.get("avg_cost", 0)
        _cp  = _row.get("current_price", 0)
        if not _cp or not _ac:
            continue
        _audit_h  = _load_audit_history(_tk)
        _latest_a = _audit_h[0] if _audit_h else {}
        _atr_v    = _latest_a.get("atr") or (_ac * 0.02)
        _wr_v     = max(0.40, min(0.80, float(
            _latest_a.get("bt5_win_rate") or _latest_a.get("bt_win_rate") or 0.50
        )))
        _regime_v = _latest_a.get("regime", "SIDEWAYS")
        _kl_v     = float(_latest_a.get("kl_ratio") or 1.0)
        _td_v     = _row.get("trade_date")
        _dit_v    = 0
        if _td_v:
            try:
                if isinstance(_td_v, str):
                    from datetime import datetime as _dt_hub
                    _td_v = _dt_hub.strptime(str(_td_v)[:10], "%Y-%m-%d").date()
                _dit_v = max(0, (_today_hub - _td_v).days)
            except Exception:
                _dit_v = 0
        _mgr_v  = T25ExitManager(_ac, _atr_v, _wr_v)
        _out_v  = _mgr_v.daily_update(_cp, _dit_v, _regime_v, 0.0, _kl_v)
        _act_lbl = _ACTION_ICON.get(_out_v["action"], _out_v["action"])
        _act_c   = ("#22c55e" if _out_v["action"] == "HOLD"
                    else "#ef4444" if _out_v["action"] == "SELL_ALL"
                    else "#f97316")
        # Rolling 5-day beta from last audit record — VN-Swing Alpha Improvement
        _beta_v   = float(_latest_a.get("rolling_beta_5d") or 1.0)
        _beta_c   = "#ef4444" if _beta_v > 1.2 else "#22c55e" if _beta_v < 0.8 else "#94a3b8"
        _kelly_lbl = _out_v.get("kelly_mode", _mgr_v.kelly_mode)
        _exit_rows += (
            f'<tr>'
            f'<td><b>{_safe(_tk)}</b></td>'
            f'<td style="color:{_act_c};font-weight:700;">{_act_lbl}</td>'
            f'<td style="font-family:monospace;">{_dit_v}d</td>'
            f'<td style="font-family:monospace;color:#ef4444;">{_out_v["sl"]:,.0f}</td>'
            f'<td style="font-family:monospace;color:#fbbf24;">{_out_v["tp1"]:,.0f}</td>'
            f'<td style="font-family:monospace;color:#22c55e;">{_out_v["tp2"]:,.0f}</td>'
            f'<td style="font-family:monospace;color:{_beta_c};">{_beta_v:.2f}β</td>'
            f'<td style="font-size:11px;color:#64748b;">{_safe(_kelly_lbl)}</td>'
            f'<td style="font-size:11px;color:#94a3b8;">{_safe(str(_out_v["reason"])[:70])}</td>'
            f'</tr>'
        )
    if _exit_rows:
        st.markdown(
            f'<table class="sum-table"><thead><tr>'
            f'<th>Mã</th><th>Hành động</th><th>Ngày GD</th>'
            f'<th>Stop-loss</th><th>TP1</th><th>TP2</th>'
            f'<th title="5-day Rolling Beta vs VNINDEX">Beta 5D</th>'
            f'<th>Kelly Mode</th>'
            f'<th>Lý do (VN-Swing Alpha)</th>'
            f'</tr></thead><tbody>{_exit_rows}</tbody></table>',
            unsafe_allow_html=True,
        )
        st.caption(T25ExitManager.entry_timing_note())
    else:
        st.info("⚠️ Chưa có dữ liệu giá để tính exit. Nhấn **🔄 Cập nhật giá** trước.")

    # ── Charts: Pie + Sector bar ──────────────────────────────────────────────
    st.markdown("---")
    ch1, ch2 = st.columns(2)
    with ch1:
        st.markdown("##### 🥧 Phân bổ danh mục theo mã")
        pie_fig = go.Figure(go.Pie(
            labels=perf_df["ticker"].tolist(),
            values=perf_df["portfolio_weight"].tolist(),
            hole=0.4,
            textinfo="label+percent",
            marker=dict(colors=[
                "#3b82f6","#22c55e","#f97316","#a855f7","#06b6d4",
                "#fbbf24","#ef4444","#94a3b8","#10b981","#6366f1",
            ][:len(perf_df)]),
        ))
        pie_fig.update_layout(
            height=280, margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="#0e1117", font=dict(color="#e2e8f0", size=11),
            legend=dict(orientation="h"),
        )
        st.plotly_chart(pie_fig, use_container_width=True, config={"displayModeBar": False})

    with ch2:
        st.markdown("##### 🏭 Phân bổ theo ngành")
        sec = summary["sector_attribution"]
        if sec:
            bar_fig = go.Figure(go.Bar(
                x=list(sec.values()),
                y=list(sec.keys()),
                orientation="h",
                marker=dict(color="#3b82f6"),
                text=[f"{v:.1f}%" for v in sec.values()],
                textposition="inside",
            ))
            bar_fig.update_layout(
                height=280, margin=dict(t=10, b=10, l=10, r=10),
                plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                font=dict(color="#e2e8f0", size=11),
                xaxis=dict(gridcolor="#1e2535", title="% Tỷ trọng"),
                yaxis=dict(gridcolor="#1e2535"),
            )
            st.plotly_chart(bar_fig, use_container_width=True, config={"displayModeBar": False})


# ═══════════════════════════════════════════════════════════════════════════════
#  SCANNER PAGE (REST polling + PROMETHEE II MCDA ranking)
# ═══════════════════════════════════════════════════════════════════════════════

def render_scanner() -> None:
    """Real-time REST scanner with PROMETHEE II MCDA ranking."""
    import time as _time

    st.markdown("## 📡 Scanner — Chấm điểm MCDA Thời gian thực")
    st.caption(
        "Nhập danh sách mã → hệ thống chấm điểm và xếp hạng bằng PROMETHEE II. "
        "Quét nhanh (Lite Mode): chỉ dùng giá real-time SSI. "
        "Quét sâu (Deep Mode): phân tích đầy đủ 400 ngày."
    )

    # ── Market Breadth banner (F7) ───────────────────────────────────────────
    _bc_key = "scanner_breadth_cache"
    if _bc_key not in st.session_state:
        try:
            _bdata = compute_market_breadth()
        except Exception:
            _bdata = {"adl_today": 0, "adl_slope": "NEUTRAL", "uv_dv_ratio": 1.0,
                      "breadth_signal": "MIXED", "advance": 0, "decline": 0}
        st.session_state[_bc_key] = _bdata
    _bdata = st.session_state[_bc_key]
    _bs    = _bdata.get("breadth_signal", "MIXED")
    _bc    = {"BROAD_BULL": "#22c55e", "BROAD_BEAR": "#ef4444", "MIXED": "#f59e0b"}.get(_bs, "#94a3b8")
    _ba, _bd = _bdata.get("advance", 0), _bdata.get("decline", 0)
    _buv    = _bdata.get("uv_dv_ratio", 1.0)
    st.markdown(
        f'<div style="padding:8px 14px;border-radius:7px;background:{_bc}11;'
        f'border:1px solid {_bc}44;margin-bottom:10px;display:flex;gap:24px;align-items:center;">'
        f'<span style="color:{_bc};font-weight:800;font-size:14px;">VN30 Breadth: {_bs}</span>'
        f'<span style="color:#94a3b8;font-size:12px;">↑ {_ba} / ↓ {_bd} · UV/DV {_buv:.2f}×</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    col_inp, col_ctrl = st.columns([2, 1])
    with col_inp:
        scanner_input = st.text_area(
            "🔍 Danh sách mã",
            value=st.session_state.get("ticker_input", ""),
            placeholder="VD: HPG, VNM, TCH, ACB, MBB, VCB",
            height=80,
            key="scanner_ticker_input",
        )
    with col_ctrl:
        scan_mode  = st.radio("Chế độ quét", ["⚡ Lite (nhanh)", "🔬 Deep (đầy đủ)"],
                              key="scanner_mode", horizontal=False)
        auto_ref   = st.select_slider("🔄 Tự động làm mới", options=["Tắt", "30s", "60s"],
                                      value="Tắt", key="scanner_autoref")
        scan_btn   = st.button("▶ Quét ngay", type="primary", use_container_width=True)

    import re as _re_sc
    _VN_RE_SC = _re_sc.compile(r'^(?=.*[A-Za-z])[A-Za-z0-9]{2,6}$')
    tickers_raw = [
        t.strip().upper()
        for t in scanner_input.replace(";", ",").split(",")
        if t.strip()
    ]
    _sc_invalid = [t for t in tickers_raw if not _VN_RE_SC.match(t)]
    tickers     = list(dict.fromkeys(t for t in tickers_raw if _VN_RE_SC.match(t)))
    if _sc_invalid:
        st.warning(
            f"⚠️ Bỏ qua mã không hợp lệ: " + ", ".join(_sc_invalid[:10])
            + (" …" if len(_sc_invalid) > 10 else "")
        )

    # Auto-refresh logic
    if auto_ref != "Tắt" and "scanner_last_run" in st.session_state:
        interval = 30 if auto_ref == "30s" else 60
        elapsed  = _time.time() - st.session_state.get("scanner_last_run", 0)
        if elapsed >= interval:
            scan_btn = True

    if not scan_btn or not tickers:
        if not tickers:
            st.info("← Nhập danh sách mã và nhấn **Quét ngay**.")
        return

    st.session_state["scanner_last_run"] = _time.time()

    # ── Fetch data ────────────────────────────────────────────────────────────
    scan_results = []
    is_deep = "Deep" in scan_mode

    with st.spinner(f"{'🔬 Phân tích sâu' if is_deep else '⚡ Quét nhanh'} {len(tickers)} mã..."):
        if is_deep:
            # Deep mode: full analyse_ticker — uses async parallel fetch
            batch = async_fetch_many(tickers, days=400)
            for tk in tickers:
                pair = batch.get(tk)
                if pair:
                    res, df_ = pair
                    # Enrich with forecast data before saving to audit
                    if not res.get("error") and isinstance(df_, pd.DataFrame) and not df_.empty:
                        try:
                            _fc2 = multi_horizon_forecast(res, df_)
                            res["fc_overall_vote"]  = _fc2.get("overall_vote", "")
                            res["fc_overall_conf"]  = _fc2.get("overall_conf", 0.0)
                            res["fc_short_vote"]    = _fc2.get("short_vote", "")
                            res["fc_short_conf"]    = _fc2.get("short_conf", 0.0)
                            res["fc_short_reasons"] = _fc2.get("short_reasons", [])
                            res["fc_mid_vote"]      = _fc2.get("mid_vote", "")
                            res["fc_mid_conf"]      = _fc2.get("mid_conf", 0.0)
                            res["fc_mid_reasons"]   = _fc2.get("mid_reasons", [])
                            res["fc_long_vote"]     = _fc2.get("long_vote", "")
                            res["fc_long_conf"]     = _fc2.get("long_conf", 0.0)
                            res["fc_long_reasons"]  = _fc2.get("long_reasons", [])
                            res["fc_lstm_pct"]      = _fc2.get("lstm_pred_pct")
                        except Exception:
                            pass
                    scan_results.append(res)
                    _embed_t_rec(res)
                    save_profiler_audit(res)
        else:
            # Lite mode: real-time price only (fast) — build minimal result dicts
            for tk in tickers:
                try:
                    rt = fetch_ssi_realtime(tk)
                    if rt and rt.get("price"):
                        scan_results.append({
                            "ticker":    tk,
                            "price":     rt.get("price", 0),
                            "pct_change":rt.get("pct_change", 0),
                            "bull_pct":  50.0,   # neutral — no indicator data
                            "kl_ratio":  None,
                            "atr":       None,
                            "signal":    "–",
                            "signal_sym":"⚪",
                            "rr1":       None,
                        })
                    else:
                        scan_results.append({"ticker": tk, "error": "Không lấy được giá"})
                except Exception as e:
                    scan_results.append({"ticker": tk, "error": str(e)})

    valid = [r for r in scan_results if "error" not in r and r.get("price")]
    if not valid:
        st.error("Không có dữ liệu hợp lệ. Kiểm tra lại kết nối SSI.")
        return

    # ── VN-Swing Alpha Improvement: CSAD Herding Detection ───────────────────
    _csad_val = 0.0
    _herding_detected = False
    if is_deep and len(valid) >= 3:
        _ret_arr = np.array(
            [(r.get("pct_change") or 0) / 100.0 for r in valid], dtype=float
        )
        _csad_val = calculate_csad(_ret_arr)
        _max_spike = max(abs(r.get("pct_change") or 0) for r in valid)
        # Herding condition: extremely low cross-sectional dispersion during a spike
        _herding_detected = _csad_val < 0.005 and _max_spike > 2.0
        if _herding_detected:
            # Downgrade all T25_BUY → T25_WATCH to protect F0 from irrational herding
            for _rv in valid:
                if _rv.get("t25_signal") == "T25_BUY":
                    _rv["t25_signal"] = "T25_WATCH"
                    _cc = list(_rv.get("t25_confirms") or [])
                    _cc.append("⚠️CSAD_herding")
                    _rv["t25_confirms"] = _cc

        _csad_c1, _csad_c2 = st.columns([1, 3])
        with _csad_c1:
            st.metric(
                "🌡 CSAD Herding Index",
                f"{_csad_val:.4f}",
                delta="⚠️ Herding — T25_BUY hạ bậc" if _herding_detected else "✅ Phân kỳ bình thường",
                delta_color="inverse",
            )
        with _csad_c2:
            if _herding_detected:
                st.warning(
                    f"🚨 **Herding Alert** — CSAD={_csad_val:.4f} quá thấp trong phiên biến động cao "
                    f"(spike tối đa {_max_spike:.1f}%). Đây là dấu hiệu đám đông phi lý trí. "
                    f"Tất cả tín hiệu **T25_BUY** đã hạ xuống **T25_WATCH**. "
                    f"F0 không nên mua đuổi trong điều kiện này."
                )
            else:
                st.info(
                    f"✅ CSAD = {_csad_val:.4f} — Phân kỳ cơ bản tốt. "
                    f"Không phát hiện herding đám đông trong rổ hiện tại."
                )

    # ── PROMETHEE II ranking ──────────────────────────────────────────────────
    if is_deep and len(valid) >= 2:
        rank_df = promethee_ii_ranking(valid)
    else:
        # Lite mode: rank by pct_change only
        rank_df = pd.DataFrame([
            {"ticker": r["ticker"], "rank": i + 1, "net_flow": 0.0,
             "score_val": 50.0, "liq_val": 0.0, "vol_val": 0.0,
             "signal": r.get("signal", "–"), "price": r["price"],
             "pct_change": r.get("pct_change", 0)}
            for i, r in enumerate(sorted(valid, key=lambda x: x.get("pct_change", 0), reverse=True))
        ])

    # ── Scanner filters ───────────────────────────────────────────────────────
    _SC_ALL_SIGS    = ["MUA", "THEO DÕI–TĂNG", "TRUNG LẬP", "THEO DÕI–GIẢM", "BÁN / TRÁNH", "–"]
    _SC_ACT_ALL     = ["STRONG_BUY", "BUY", "WATCH", "SKIP", "AVOID"]
    _SC_ACT_ICONS   = {"STRONG_BUY": "💎", "BUY": "✅", "WATCH": "👁", "SKIP": "⏭", "AVOID": "🚫"}
    _SC_SIG_ICONS   = {
        "MUA": "🟢", "THEO DÕI–TĂNG": "🔵", "TRUNG LẬP": "⚪",
        "THEO DÕI–GIẢM": "🟠", "BÁN / TRÁNH": "🔴", "–": "⬜",
    }
    r_lookup_pre  = {r["ticker"]: r for r in valid}
    # Signals present in current scan
    _sc_sig_present = list(dict.fromkeys(
        r.get("signal", "–") for _, row in rank_df.iterrows()
        for r in [r_lookup_pre.get(row["ticker"], {})]
        if r.get("signal") or row.get("signal")
    ))
    _sc_sig_present = [
        s for s in _SC_ALL_SIGS
        if s in {row.get("signal", r_lookup_pre.get(row["ticker"], {}).get("signal", "–"))
                 for _, row in rank_df.iterrows()}
    ]
    _fsc1, _fsc2 = st.columns([3, 2]) if is_deep else (st.container(), None)
    with _fsc1:
        if _sc_sig_present:
            _sc_sig_opts = [f"{_SC_SIG_ICONS.get(s, '')} {s}" for s in _sc_sig_present]
            _sc_sig_sel  = st.multiselect(
                "🔍 Lọc Tín hiệu",
                options=_sc_sig_opts,
                default=_sc_sig_opts,
                key="scanner_sig_filter",
            )
            _sc_sig_set = {s for s in _sc_sig_present if f"{_SC_SIG_ICONS.get(s, '')} {s}" in _sc_sig_sel}
        else:
            _sc_sig_set = set()
    if is_deep and _fsc2 is not None:
        with _fsc2:
            _sc_act_present = [
                a for a in _SC_ACT_ALL
                if any(
                    generate_t_plus_recommendation(r_lookup_pre.get(row["ticker"], {})).get("action") == a
                    for _, row in rank_df.iterrows()
                )
            ]
            if _sc_act_present:
                _sc_act_opts = [f"{_SC_ACT_ICONS[a]} {a}" for a in _sc_act_present]
                _sc_act_sel  = st.multiselect(
                    "🎯 Lọc T+ Action",
                    options=_sc_act_opts,
                    default=_sc_act_opts,
                    key="scanner_act_filter",
                )
                _sc_act_set = {a for a in _sc_act_present if f"{_SC_ACT_ICONS[a]} {a}" in _sc_act_sel}
            else:
                _sc_act_set = set(_SC_ACT_ALL)
    else:
        _sc_act_set = set(_SC_ACT_ALL)

    # Apply signal filter to rank_df
    if _sc_sig_set:
        def _row_sig(row):
            return r_lookup_pre.get(row["ticker"], {}).get("signal") or row.get("signal", "–")
        rank_df = rank_df[rank_df.apply(_row_sig, axis=1).isin(_sc_sig_set)].reset_index(drop=True)
        # Re-number rank column
        rank_df["rank"] = range(1, len(rank_df) + 1)
    # Apply T+ action filter to rank_df (deep mode only)
    if is_deep and _sc_act_set != set(_SC_ACT_ALL):
        def _row_act(row):
            return generate_t_plus_recommendation(r_lookup_pre.get(row["ticker"], {})).get("action", "–")
        rank_df = rank_df[rank_df.apply(_row_act, axis=1).isin(_sc_act_set)].reset_index(drop=True)
        rank_df["rank"] = range(1, len(rank_df) + 1)

    if rank_df.empty:
        st.info("ℹ️ Không có mã nào khớp với bộ lọc đã chọn.")
        return

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown(f"#### 🏆 Kết quả xếp hạng  ({len(rank_df)} mã)  &nbsp;&nbsp; <span style='font-size:12px;color:#64748b;'>{'Deep Analysis' if is_deep else 'Lite Mode — chỉ giá RT'}</span>",
                unsafe_allow_html=True)

    _SIG_COLORS = {
        "MUA":            "#22c55e",
        "THEO DÕI–TĂNG":  "#3b82f6",
        "TRUNG LẬP":     "#94a3b8",
        "THEO DÕI–GIẢM": "#f97316",
        "BÁN / TRÁNH":   "#ef4444",
        "–":             "#475569",
    }

    rows_html = ""
    r_lookup = {r["ticker"]: r for r in valid}
    for _, row in rank_df.iterrows():
        tk   = row["ticker"]
        sig  = row.get("signal", "–")
        sc   = _SIG_COLORS.get(sig, "#475569")
        pr   = row.get("price", 0)
        pct  = row.get("pct_change", 0) or 0
        p_c  = "color:#22c55e" if pct > 0 else "color:#ef4444" if pct < 0 else "color:#94a3b8"
        nf   = row.get("net_flow", 0)
        rnk  = row.get("rank", "–")
        sv   = row.get("score_val", 0)
        lv   = row.get("liq_val", 0)
        vv   = row.get("vol_val", 0)
        rr   = r_lookup.get(tk, {}).get("rr1")
        rr_s = f"{rr:.2f}:1" if rr else "–"
        lv_s = f"{lv:.2f}×" if is_deep else "–"
        vv_s = f"{vv:.2f}%" if is_deep else "–"
        t25_sig  = r_lookup.get(tk, {}).get("t25_signal", "")
        t25_sc   = r_lookup.get(tk, {}).get("t25_score")
        t25_cell = _t25_badge(t25_sig, t25_sc) if is_deep else "–"
        # T+ Recommendation badge (deep mode only)
        if is_deep:
            _trec = generate_t_plus_recommendation(r_lookup.get(tk, {}))
            _tact = _trec["action"]
            _tscr = _trec["confidence_score"]
            _tcol = _T_REC_COLORS.get(_tact, "#94a3b8")
            _act_short = {"STRONG_BUY": "S.BUY", "BUY": "BUY", "WATCH": "WATCH",
                          "SKIP": "SKIP", "AVOID": "AVOID"}.get(_tact, _tact)
            rec_cell = (
                f'<span style="background:{_tcol}22;border:1px solid {_tcol};color:{_tcol};'
                f'border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700;">'
                f'{_act_short} {_tscr}</span>'
            )
        else:
            rec_cell = "–"
        # ticker cell colored by signal
        tk_cell = (
            f'<b style="font-size:14px;border-left:3px solid {sc};'
            f'padding-left:7px;color:{sc}">{_safe(tk)}</b>'
        )
        rows_html += (
            f'<tr>'
            f'<td><b style="color:#fbbf24;">#{rnk}</b></td>'
            f'<td>{tk_cell}</td>'
            f'<td style="font-family:monospace;">{pr:,.0f}</td>'
            f'<td style="font-family:monospace;{p_c}">{pct:+.2f}%</td>'
            f'<td><span style="background:{sc}22;border:1px solid {sc};color:{sc};'
            f'border-radius:999px;padding:2px 10px;font-size:11px;font-weight:700;">{sig}</span></td>'
            f'<td style="font-family:monospace;">{nf:+.4f}</td>'
            f'<td style="font-family:monospace;">{sv:.1f}</td>'
            f'<td style="font-family:monospace;color:#94a3b8;">{lv_s}</td>'
            f'<td style="font-family:monospace;color:#94a3b8;">{vv_s}</td>'
            f'<td style="font-family:monospace;">{rr_s}</td>'
            f'<td>{t25_cell}</td>'
            f'<td>{rec_cell}</td>'
            f'</tr>'
        )

    scanner_table_html = (
        f'<table class="sum-table"><thead><tr>'
        f'<th>Hạng</th><th>Mã</th><th>Giá</th><th>%Δ</th>'
        f'<th>Tín hiệu</th><th>NetFlow</th><th>Bull%</th>'
        f'<th>Thanh khoản</th><th>Biến động</th><th>R:R</th>'
        f'<th title="VN-Swing Alpha T+2.5">T+2.5</th>'
        f'<th title="T+ Khuyến nghị">T+ Rec</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>'
    )
    st.markdown(_filterable_table("scanner_tbl", scanner_table_html), unsafe_allow_html=True)
    st.caption(
        "PROMETHEE II MCDA: Trọng số — Bull Score (50%), thanh khoản KL×MA20 (30%), biến động ATR/Giá (−20%). "
        "Lite Mode không có đủ dữ liệu chỉ báo — chuyển sang Deep Mode để xếp hạng chính xác."
    )

    if auto_ref != "Tắt":
        intv = int(auto_ref.replace("s",""))
        elapsed = _time.time() - st.session_state.get("scanner_last_run", 0)
        remaining = max(0, int(intv - elapsed))
        st.info(f"🔄 Tự động làm mới sau ≈{remaining}s")
        _time.sleep(1)   # 1s tick — do NOT block the full interval here
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  F5: ACTIVE TRADE TRACKER PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def render_active_trades_page() -> None:
    """🔄 Quản lý lệnh — Track open T+x positions with live exit guidance."""
    import time as _time
    from datetime import date as _date, datetime as _dt

    st.markdown("## 🔄 Quản lý lệnh đang mở")
    st.caption("Theo dõi và nhận hướng dẫn thoát lệnh theo ngày cho từng vị thế T+x đang mở.")

    trades = _load_active_trades()

    # ── Add new trade form ─────────────────────────────────────────────────────
    with st.expander("➕ Thêm lệnh mới", expanded=(not trades)):
        with st.form("add_trade_form"):
            fc1, fc2, fc3, fc4 = st.columns(4)
            new_tk    = fc1.text_input("Mã CK", placeholder="HPG").upper().strip()
            new_entry = fc2.number_input("Giá vào (₫)", min_value=100.0, step=100.0, value=25000.0)
            new_qty   = fc3.number_input("Số lượng (cp)", min_value=100, step=100, value=1000)
            new_date  = fc4.date_input("Ngày vào lệnh", value=_date.today())
            new_notes = st.text_input("Ghi chú", placeholder="Lý do vào lệnh…")
            submitted = st.form_submit_button("✅ Thêm lệnh", use_container_width=True)
            if submitted and new_tk:
                trades.append({
                    "ticker":     new_tk,
                    "entry":      float(new_entry),
                    "qty":        int(new_qty),
                    "entry_date": str(new_date),
                    "notes":      new_notes,
                    "id":         _time.time(),
                })
                _save_active_trades(trades)
                st.success(f"✅ Đã thêm lệnh {new_tk}")
                st.rerun()

    if not trades:
        st.info("📭 Không có lệnh nào đang mở.")
        return

    st.markdown(f"**{len(trades)} lệnh đang mở** — giá RT được cập nhật tự động.")

    today = _date.today()
    _ACTION_COLOR = {
        "SELL_ALL":   "#ef4444",
        "SELL_60PCT": "#f97316",
        "SELL_50PCT": "#f59e0b",
        "HOLD":       "#22c55e",
    }

    for i, trade in enumerate(trades):
        tk       = trade.get("ticker", "?")
        entry    = float(trade.get("entry", 0))
        qty      = int(trade.get("qty", 0))
        edate_s  = trade.get("entry_date", str(today))
        try:
            edate = _date.fromisoformat(edate_s)
        except Exception:
            edate = today
        day_in_trade = (today - edate).days

        # Fetch RT price
        rt = fetch_ssi_realtime(tk)
        cur_price = float(rt.get("price") or entry)
        pnl_pct   = (cur_price - entry) / entry * 100 if entry else 0.0
        pnl_vnd   = (cur_price - entry) * qty

        # Get regime from session if available
        _sess_res = st.session_state.get("results", [])
        regime = "SIDEWAYS"
        for _r in _sess_res:
            if _r.get("ticker") == tk:
                regime = _r.get("regime", "SIDEWAYS")
                break

        # T25ExitManager daily_update
        cur_atr = float(trade.get("atr_at_entry") or entry * 0.02)
        try:
            mgr    = T25ExitManager(entry, cur_atr)
            update = mgr.daily_update(cur_price, max(1, day_in_trade), regime=regime)
        except Exception:
            update = {"action": "HOLD", "reason": "–", "trail": 0, "tp1": 0, "tp2": 0, "sl": 0,
                      "rec_size_pct": 10, "kelly_mode": "Half-Kelly"}

        action  = update["action"]
        reason  = update["reason"].replace(" — recommend by VN-Swing Alpha", "")
        ac_col  = _ACTION_COLOR.get(action, "#94a3b8")

        pnl_col = "#22c55e" if pnl_pct >= 0 else "#ef4444"

        with st.expander(
            f"{'🔴 ' if action=='SELL_ALL' else '🟠 ' if 'SELL' in action else '🟢 '}"
            f"**{tk}**  ·  Ngày {day_in_trade}  ·  "
            f"{'↑' if pnl_pct>=0 else '↓'} {pnl_pct:+.2f}%  ·  {action}",
            expanded=(action != "HOLD"),
        ):
            # Row 1: metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Giá vào",   f"{entry:,.0f}")
            col2.metric("Giá hiện",  f"{cur_price:,.0f}", delta=f"{pnl_pct:+.2f}%")
            col3.metric("P&L (₫)",   f"{pnl_vnd:+,.0f}", delta_color="normal")
            col4.metric("Ngày T+",   f"T+{day_in_trade}")
            col5.metric("Khối lượng", f"{qty:,}")

            # Row 2: action banner
            st.markdown(
                f'<div style="margin:8px 0;padding:10px 14px;border-radius:7px;'
                f'background:{ac_col}22;border:1px solid {ac_col}66;">'
                f'<span style="color:{ac_col};font-size:16px;font-weight:800;">{action}</span>'
                f'<span style="color:#94a3b8;font-size:12px;margin-left:10px;">{reason}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Row 3: SL/TP/Trail levels
            sl_c  = update.get("sl",    0)
            tp1_c = update.get("tp1",   0)
            tp2_c = update.get("tp2",   0)
            trail = update.get("trail", 0)
            st.markdown(
                f'<div style="font-family:monospace;font-size:12px;color:#94a3b8;">'
                f'SL: <b style="color:#ef4444;">{sl_c:,.0f}</b> &nbsp;·&nbsp; '
                f'Trail: <b style="color:#f59e0b;">{trail:,.0f}</b> &nbsp;·&nbsp; '
                f'TP1: <b style="color:#06b6d4;">{tp1_c:,.0f}</b> &nbsp;·&nbsp; '
                f'TP2: <b style="color:#22c55e;">{tp2_c:,.0f}</b>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.caption(f"Vào: {edate_s} | Ghi chú: {trade.get('notes') or '–'}")

            # Close trade button
            close_col, _ = st.columns([1, 4])
            if close_col.button("✖ Đóng lệnh", key=f"close_{trade.get('id',i)}"):
                closed_entry = {
                    **trade,
                    "exit_price":    cur_price,
                    "exit_date":     str(today),
                    "day_in_trade":  day_in_trade,
                    "pnl_pct":       round(pnl_pct, 2),
                    "pnl_vnd":       round(pnl_vnd, 0),
                    "action_at_exit": action,
                    "t_rec_grade_at_entry": trade.get("t_rec_grade") or "?",
                }
                _append_journal_entry(closed_entry)
                trades = [t for t in trades if t.get("id") != trade.get("id")]
                _save_active_trades(trades)
                st.success(f"✅ Đã đóng lệnh {tk} — ghi vào nhật ký giao dịch.")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  F6: SECTOR ROTATION HEATMAP PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def render_sector_heatmap_page() -> None:
    """🌡️ Sector Flow — Sector rotation heatmap + market breadth."""
    from portfolio_engine import _SECTOR_MAP

    st.markdown("## 🌡️ Sector Rotation & Market Breadth")
    st.caption("Theo dõi dòng tiền luân chuyển giữa các ngành — cập nhật theo phiên.")

    # ── Build sector groups ────────────────────────────────────────────────────
    sector_groups: dict = {}
    for tk, sector in _SECTOR_MAP.items():
        sector_groups.setdefault(sector, []).append(tk)

    refresh_col, _ = st.columns([1, 5])
    refresh = refresh_col.button("🔄 Cập nhật", key="sector_refresh")
    cache_key = "sector_heatmap_cache"
    if refresh or cache_key not in st.session_state:
        with st.spinner("Đang tải dữ liệu ngành…"):
            all_tickers_sec = list(_SECTOR_MAP.keys())
            try:
                res_map, _ = async_fetch_many(all_tickers_sec, days=15, max_workers=12, on_progress=None)
            except Exception:
                res_map = {}
        st.session_state[cache_key] = res_map

    res_map = st.session_state.get(cache_key, {})

    # Compute 1d / 3d / 5d returns per sector
    sectors_ordered = sorted(sector_groups.keys())
    horizons        = ["1D", "3D", "5D"]
    heatmap_z  = []
    hover_text = []

    for sector in sectors_ordered:
        tickers = sector_groups[sector]
        row_z   = []
        row_ht  = []
        for h_label, lag in [("1D", 1), ("3D", 3), ("5D", 5)]:
            rets = []
            for tk in tickers:
                entry = res_map.get(tk)
                if entry is None:
                    continue
                df_tk, _ = entry if isinstance(entry, tuple) else (entry, None)
                if df_tk is None or df_tk.empty or len(df_tk) < lag + 1:
                    continue
                try:
                    r = float(df_tk["Close"].iloc[-1] / df_tk["Close"].iloc[-(lag + 1)] - 1) * 100
                    rets.append(r)
                except Exception:
                    pass
            med = round(sum(rets) / len(rets), 2) if rets else 0.0
            row_z.append(med)
            row_ht.append(f"{sector}<br>{h_label}: {med:+.2f}%<br>({len(rets)} mã)")
        heatmap_z.append(row_z)
        hover_text.append(row_ht)

    # Plotly heatmap
    fig = go.Figure(go.Heatmap(
        z=heatmap_z,
        x=horizons,
        y=sectors_ordered,
        text=hover_text,
        hoverinfo="text",
        colorscale="RdYlGn",
        zmid=0,
        colorbar=dict(title="Return %", thickness=12, len=0.8),
    ))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0e1117", plot_bgcolor="#0d1117",
        height=max(400, len(sectors_ordered) * 24 + 80),
        margin=dict(l=160, r=40, t=30, b=40),
        font=dict(family="JetBrains Mono, Consolas, monospace", size=11, color="#94a3b8"),
        xaxis=dict(side="top"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Market Breadth widget ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Độ rộng thị trường VN30")
    with st.spinner("Đang tính breadth…"):
        try:
            breadth = compute_market_breadth()
        except Exception:
            breadth = {"adl_today": 0, "adl_slope": "NEUTRAL", "uv_dv_ratio": 1.0,
                       "breadth_signal": "MIXED", "advance": 0, "decline": 0}

    _bs_col = {"BROAD_BULL": "#22c55e", "BROAD_BEAR": "#ef4444", "MIXED": "#f59e0b"}.get(
        breadth.get("breadth_signal", "MIXED"), "#94a3b8")
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("A/D hôm nay", f"{breadth.get('adl_today', 0):+d}")
    b2.metric("Tăng / Giảm", f"{breadth.get('advance', 0)} / {breadth.get('decline', 0)}")
    b3.metric("UV/DV ratio", f"{breadth.get('uv_dv_ratio', 1.0):.2f}×")
    b4.metric("Breadth signal", breadth.get("breadth_signal", "MIXED"))
    st.markdown(
        f'<span style="color:{_bs_col};font-size:20px;font-weight:800;">'
        f'● {breadth.get("breadth_signal","MIXED")}</span>'
        f'<span style="color:#64748b;font-size:12px;margin-left:8px;">'
        f'ADL slope: {breadth.get("adl_slope","NEUTRAL")}</span>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  F11 + F14: PRICE ALERTS & CONDITIONAL CHAINS PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def render_alerts_page() -> None:
    """🔔 Cảnh báo — Price/signal alerts + conditional signal chains (F14)."""
    from datetime import datetime as _dt

    st.markdown("## 🔔 Cảnh báo & Điều kiện")

    alerts     = _load_alerts()
    conditions = _load_conditions()
    results    = st.session_state.get("results", [])
    res_by_tk  = {r.get("ticker"): r for r in results if "error" not in r}

    tab_alerts, tab_conds = st.tabs(["🔔 Price Alerts", "⛓️ Conditional Chains"])

    with tab_alerts:
        # ── Add alert form ─────────────────────────────────────────────────────
        with st.form("add_alert_form"):
            ac1, ac2, ac3 = st.columns(3)
            al_tk   = ac1.text_input("Mã CK", placeholder="HPG").upper().strip()
            al_cond = ac2.selectbox("Điều kiện", [
                "PRICE_ABOVE", "PRICE_BELOW", "T25_BUY", "RS_ABOVE_70", "SSI_ABOVE_80", "AVOID_LIFTED",
            ])
            al_val  = ac3.number_input("Giá trị ngưỡng (nếu cần)", min_value=0.0, step=100.0)
            al_sub  = st.form_submit_button("➕ Thêm cảnh báo", use_container_width=True)
            if al_sub and al_tk:
                alerts.append({
                    "ticker":    al_tk,
                    "condition": al_cond,
                    "threshold": float(al_val),
                    "created":   _dt.now().isoformat(timespec="seconds"),
                    "status":    "ACTIVE",
                    "id":        _time_module.time() if hasattr(_time_module, "time") else 0,
                })
                _save_alerts(alerts)
                st.success(f"✅ Đã thêm cảnh báo cho {al_tk}")
                st.rerun()

        # ── Check & display alerts ─────────────────────────────────────────────
        if not alerts:
            st.info("Chưa có cảnh báo nào. Thêm cảnh báo ở trên.")
        else:
            triggered_ids = []
            for alert in alerts:
                tk   = alert.get("ticker", "")
                cond = alert.get("condition", "")
                thr  = float(alert.get("threshold", 0))
                stat = alert.get("status", "ACTIVE")
                r    = res_by_tk.get(tk, {})
                price = float(r.get("price") or 0)
                fired = False
                if stat == "ACTIVE":
                    if cond == "PRICE_ABOVE"  and price > thr and thr > 0: fired = True
                    elif cond == "PRICE_BELOW" and price < thr and thr > 0: fired = True
                    elif cond == "T25_BUY"    and r.get("t25_signal") == "T25_BUY": fired = True
                    elif cond == "RS_ABOVE_70" and int(r.get("rs_rating") or 0) > 70: fired = True
                    elif cond == "SSI_ABOVE_80":
                        ssi_r = compute_ssi_score(r)
                        if ssi_r.get("ssi", 0) >= 80: fired = True
                    elif cond == "AVOID_LIFTED" and r.get("t_rec_action","") not in ("AVOID",""):
                        if alert.get("prev_action","") == "AVOID": fired = True
                if fired:
                    st.toast(f"🔔 {tk}: {cond} kích hoạt!", icon="🚨")
                    triggered_ids.append(alert.get("id"))
                    alert["status"] = "TRIGGERED"

            if triggered_ids:
                _save_alerts(alerts)

            # Display table
            rows = ""
            for alert in alerts:
                stat = alert.get("status", "ACTIVE")
                sc   = "#22c55e" if stat == "TRIGGERED" else "#94a3b8"
                rows += (
                    f'<tr>'
                    f'<td><b style="color:#fbbf24;">{_safe(alert.get("ticker",""))}</b></td>'
                    f'<td style="color:#94a3b8;">{alert.get("condition","")}</td>'
                    f'<td style="font-family:monospace;">{alert.get("threshold",0):,.0f}</td>'
                    f'<td style="font-size:11px;color:#64748b;">{(alert.get("created",""))[:16]}</td>'
                    f'<td style="color:{sc};font-weight:700;">{stat}</td>'
                    f'</tr>'
                )
            st.markdown(
                f'<table class="sum-table"><thead><tr>'
                f'<th>Mã</th><th>Điều kiện</th><th>Ngưỡng</th><th>Tạo lúc</th><th>Trạng thái</th>'
                f'</tr></thead><tbody>{rows}</tbody></table>',
                unsafe_allow_html=True,
            )
            if st.button("🗑️ Xóa tất cả cảnh báo đã kích hoạt"):
                _save_alerts([a for a in alerts if a.get("status") != "TRIGGERED"])
                st.rerun()

    with tab_conds:
        st.markdown("### ⛓️ Điều kiện chuỗi (F14 — Conditional Signal Chains)")
        st.caption("Khi điều kiện 1 VÀ điều kiện 2 cùng thỏa mãn → thông báo hoặc mở lệnh tự động.")
        with st.form("add_cond_form"):
            cc1, cc2, cc3 = st.columns(3)
            c_tk  = cc1.text_input("Mã CK", placeholder="VNM").upper().strip()
            c_c1  = cc2.selectbox("Điều kiện 1", ["T25_BUY", "RS_ABOVE_70", "SSI_ABOVE_80", "HH+HL_STRUCTURE"])
            c_c2  = cc3.selectbox("Điều kiện 2", ["BULL_TREND", "MACD_CROSS_UP", "PRICE_ABOVE_SMA20", "VOL_SURGE"])
            c_sub = st.form_submit_button("➕ Thêm điều kiện chuỗi")
            if c_sub and c_tk:
                conditions.append({
                    "ticker": c_tk, "cond1": c_c1, "cond2": c_c2,
                    "status": "WATCHING", "created": datetime.now().isoformat(timespec="seconds"),
                })
                _save_conditions(conditions)
                st.rerun()

        if conditions:
            for cond in conditions:
                tk = cond.get("ticker", "")
                r  = res_by_tk.get(tk, {})
                c1 = cond.get("cond1", "")
                c2 = cond.get("cond2", "")
                # Evaluate conditions
                c1_ok = (
                    (c1 == "T25_BUY"          and r.get("t25_signal") == "T25_BUY") or
                    (c1 == "RS_ABOVE_70"       and int(r.get("rs_rating") or 0) > 70) or
                    (c1 == "SSI_ABOVE_80"      and compute_ssi_score(r).get("ssi", 0) >= 80) or
                    (c1 == "HH+HL_STRUCTURE"   and r.get("is_hh") and r.get("is_hl"))
                )
                c2_ok = (
                    (c2 == "BULL_TREND"        and r.get("regime") == "BULL_TREND") or
                    (c2 == "MACD_CROSS_UP"     and "MACD_cross↑" in (r.get("t25_confirms") or [])) or
                    (c2 == "PRICE_ABOVE_SMA20" and r.get("price", 0) > (r.get("sma20") or 0)) or
                    (c2 == "VOL_SURGE"         and float(r.get("kl_ratio") or 0) > 1.5)
                )
                both = c1_ok and c2_ok
                flag = "🟢 KHỚP" if both else "⚪ Chờ"
                if both:
                    st.toast(f"⛓️ {tk}: Chuỗi điều kiện {c1} + {c2} đã thỏa mãn!", icon="⚡")
                st.markdown(
                    f'<div style="margin:4px 0;padding:6px 10px;border-radius:5px;'
                    f'background:{"#16a34a22" if both else "#1a2030"};">'
                    f'<b style="color:#fbbf24;">{tk}</b> &nbsp; '
                    f'<span style="color:#94a3b8;">{c1}</span>'
                    f' AND <span style="color:#94a3b8;">{c2}</span>'
                    f' &nbsp; → &nbsp; {flag}</div>',
                    unsafe_allow_html=True,
                )


# ═══════════════════════════════════════════════════════════════════════════════
#  F13: TRADE JOURNAL PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def render_trade_journal_page() -> None:
    """📓 Trade Journal — Closed trade history with P&L attribution by grade."""
    from datetime import datetime as _dt

    st.markdown("## 📓 Nhật ký giao dịch")
    st.caption("Lịch sử các lệnh đã đóng — đánh giá hiệu quả theo Grade T+ Rec.")

    journal = _load_journal()

    # ── Manual add form ────────────────────────────────────────────────────────
    with st.expander("➕ Thêm lệnh thủ công"):
        with st.form("add_journal_form"):
            jc1, jc2, jc3, jc4 = st.columns(4)
            j_tk    = jc1.text_input("Mã CK", placeholder="HPG").upper().strip()
            j_entry = jc2.number_input("Giá vào (₫)", min_value=100.0, step=100.0)
            j_exit  = jc3.number_input("Giá ra (₫)",  min_value=100.0, step=100.0)
            j_qty   = jc4.number_input("KL", min_value=100, step=100)
            j_edate = st.date_input("Ngày vào", value=_dt.today())
            j_xdate = st.date_input("Ngày ra",  value=_dt.today())
            j_grade = st.selectbox("Grade lúc vào", ["A", "B", "C", "D", "E", "?"])
            j_sub   = st.form_submit_button("📝 Ghi lệnh")
            if j_sub and j_tk and j_entry > 0 and j_exit > 0:
                pnl_pct = (j_exit - j_entry) / j_entry * 100
                _append_journal_entry({
                    "ticker":               j_tk,
                    "entry":                float(j_entry),
                    "exit_price":           float(j_exit),
                    "qty":                  int(j_qty),
                    "entry_date":           str(j_edate),
                    "exit_date":            str(j_xdate),
                    "pnl_pct":              round(pnl_pct, 2),
                    "pnl_vnd":              round((j_exit - j_entry) * j_qty, 0),
                    "t_rec_grade_at_entry": j_grade,
                })
                st.success(f"✅ Đã ghi lệnh {j_tk}")
                st.rerun()

    if not journal:
        st.info("📭 Chưa có lịch sử giao dịch.")
        return

    # ── Summary metrics ────────────────────────────────────────────────────────
    wins  = [t for t in journal if float(t.get("pnl_pct", 0)) > 0]
    total = len(journal)
    win_r = len(wins) / total * 100 if total else 0
    avg_p = sum(float(t.get("pnl_pct", 0)) for t in journal) / total if total else 0
    best  = max(journal, key=lambda x: float(x.get("pnl_pct", -999)), default={})
    worst = min(journal, key=lambda x: float(x.get("pnl_pct", 999)), default={})

    sm1, sm2, sm3, sm4, sm5 = st.columns(5)
    sm1.metric("📊 Tổng lệnh",  total)
    sm2.metric("🏆 Win rate",   f"{win_r:.1f}%")
    sm3.metric("📈 Avg P&L",    f"{avg_p:+.2f}%")
    sm4.metric("🌟 Tốt nhất",   f"{float(best.get('pnl_pct',0)):+.2f}% ({best.get('ticker','–')})")
    sm5.metric("💀 Tệ nhất",    f"{float(worst.get('pnl_pct',0)):+.2f}% ({worst.get('ticker','–')})")

    # ── Breakdown by Grade ─────────────────────────────────────────────────────
    st.markdown("#### Hiệu quả theo Grade T+ Rec")
    grade_stats: dict = {}
    for t in journal:
        g = t.get("t_rec_grade_at_entry", "?")
        grade_stats.setdefault(g, []).append(float(t.get("pnl_pct", 0)))

    g_rows = ""
    for g in sorted(grade_stats.keys()):
        vals = grade_stats[g]
        gw   = sum(1 for v in vals if v > 0)
        ga   = sum(vals) / len(vals)
        gc   = _T_REC_COLORS.get(
            {"A":"STRONG_BUY","B":"BUY","C":"WATCH","D":"SKIP","E":"AVOID"}.get(g,""), "#94a3b8")
        g_rows += (
            f'<tr><td style="color:{gc};font-size:18px;font-weight:900;'
            f'font-family:monospace;">{g}</td>'
            f'<td>{len(vals)}</td>'
            f'<td style="color:{"#22c55e" if gw/len(vals)>0.5 else "#ef4444"};">'
            f'{gw/len(vals)*100:.1f}%</td>'
            f'<td style="color:{"#22c55e" if ga>0 else "#ef4444"};font-family:monospace;">'
            f'{ga:+.2f}%</td></tr>'
        )
    st.markdown(
        f'<table class="sum-table"><thead><tr>'
        f'<th>Grade</th><th>Số lệnh</th><th>Win%</th><th>Avg P&L</th>'
        f'</tr></thead><tbody>{g_rows}</tbody></table>',
        unsafe_allow_html=True,
    )

    # ── Monthly P&L chart ──────────────────────────────────────────────────────
    monthly: dict = {}
    for t in journal:
        m = (t.get("exit_date") or "")[:7]
        if m:
            monthly[m] = monthly.get(m, 0) + float(t.get("pnl_pct", 0))
    if monthly:
        months = sorted(monthly.keys())
        vals_m = [monthly[m] for m in months]
        fig = go.Figure(go.Bar(
            x=months, y=vals_m,
            marker_color=["#22c55e" if v >= 0 else "#ef4444" for v in vals_m],
            hovertemplate="%{x}: %{y:+.2f}%<extra></extra>",
        ))
        fig.update_layout(
            template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0d1117",
            height=220, margin=dict(l=10, r=10, t=20, b=30),
            font=dict(family="JetBrains Mono, Consolas, monospace", size=11, color="#94a3b8"),
            xaxis=dict(gridcolor="#1a2030"), yaxis=dict(gridcolor="#1a2030"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Full journal table ─────────────────────────────────────────────────────
    st.markdown("#### Lịch sử đầy đủ")
    j_rows = ""
    for t in journal[:100]:
        pnl = float(t.get("pnl_pct", 0))
        pc  = "#22c55e" if pnl >= 0 else "#ef4444"
        g   = t.get("t_rec_grade_at_entry", "?")
        gc  = _T_REC_COLORS.get(
            {"A":"STRONG_BUY","B":"BUY","C":"WATCH","D":"SKIP","E":"AVOID"}.get(g,""), "#94a3b8")
        j_rows += (
            f'<tr>'
            f'<td><b style="color:#fbbf24;">{_safe(t.get("ticker",""))}</b></td>'
            f'<td style="font-family:monospace;">{_f(t.get("entry"))}</td>'
            f'<td style="font-family:monospace;">{_f(t.get("exit_price"))}</td>'
            f'<td style="color:{pc};font-family:monospace;">{pnl:+.2f}%</td>'
            f'<td style="color:{gc};font-weight:700;">{g}</td>'
            f'<td style="font-size:11px;color:#64748b;">{(t.get("entry_date",""))[:10]}</td>'
            f'<td style="font-size:11px;color:#64748b;">{(t.get("exit_date",""))[:10]}</td>'
            f'</tr>'
        )
    st.markdown(
        f'<table class="sum-table"><thead><tr>'
        f'<th>Mã</th><th>Vào</th><th>Ra</th><th>P&L%</th>'
        f'<th>Grade</th><th>Ngày vào</th><th>Ngày ra</th>'
        f'</tr></thead><tbody>{j_rows}</tbody></table>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  T+ RECOMMENDATION PAGE
# ═══════════════════════════════════════════════════════════════════════════════
def render_t_plus_page() -> None:
    """Standalone 🎯 T+ Khuyến nghị page.

    Ranks all tickers in session results by T+ confidence_score and shows
    a compact summary table + per-ticker expandable recommendation cards.
    User can optionally enter new tickers to analyse from scratch.
    """
    st.markdown("## 🎯 T+ Entry Khuyến nghị")
    st.caption("Xếp hạng toàn bộ tín hiệu & khuyến nghị vào lệnh T+ theo điểm tin cậy tổng hợp.")

    results = st.session_state.get("results", [])
    valid   = [r for r in results if "error" not in r and r.get("price")]

    if not valid:
        st.info("📭 Chưa có kết quả phân tích. Hãy chạy phân tích từ tab **📊 Phân tích** trước.")
        return

    # ── Compute recommendations for all valid tickers ─────────────────────────
    recs = []
    for r in valid:
        rec = generate_t_plus_recommendation(r)
        recs.append({**rec, "ticker": r["ticker"], "price": r.get("price")})

    # Sort by confidence_score descending
    recs.sort(key=lambda x: x["confidence_score"], reverse=True)

    # ── Filters ───────────────────────────────────────────────────────────────
    _ALL_TPLUS_ACTIONS = ["STRONG_BUY", "BUY", "WATCH", "SKIP", "AVOID"]
    _ACT_ICONS = {
        "STRONG_BUY": "💎",
        "BUY":        "✅",
        "WATCH":      "👁",
        "SKIP":       "⏭",
        "AVOID":      "🚫",
    }
    _present_actions = [
        a for a in _ALL_TPLUS_ACTIONS
        if any(rd["action"] == a for rd in recs)
    ]
    if _present_actions:
        _f1, _f2 = st.columns([3, 1])
        with _f1:
            _act_opts = [f"{_ACT_ICONS[a]} {a}" for a in _present_actions]
            _act_sel  = st.multiselect(
                "🔍 Lọc theo Hành động T+",
                options=_act_opts,
                default=_act_opts,
                key="tplus_action_filter",
            )
            _act_sel_set = {a for a in _present_actions if f"{_ACT_ICONS[a]} {a}" in _act_sel}
        with _f2:
            _min_score = st.slider("Min Score", 0, 100, 0, 5, key="tplus_min_score")
        recs = [
            rd for rd in recs
            if rd["action"] in _act_sel_set
            and rd["confidence_score"] >= _min_score
        ]

    if not recs:
        st.info("ℹ️ Không có mã nào khớp với bộ lọc đã chọn.")
        return

    # ── Summary table ──────────────────────────────────────────────────────────
    tbl_rows = ""
    for rd in recs:
        _a = rd["action"]
        _g = rd["grade"]
        _s = rd["confidence_score"]
        _c = _T_REC_COLORS.get(_a, "#94a3b8")
        _pr = rd.get("price")
        _sl = rd.get("sl_price")
        _tp = rd.get("tp1_price")
        _rr = rd.get("rr_ratio")
        _pct_sz = rd.get("position_size_pct", 0)
        _entry_lo = rd.get("entry_zone_low")
        _entry_hi = rd.get("entry_zone_high")
        _entry_str = (
            f"{_entry_lo:,.0f}–{_entry_hi:,.0f}" if _entry_lo and _entry_hi else "–"
        )
        _flag_cnt = len(rd.get("risk_flags", []))
        _sup_cnt  = len(rd.get("supporting_signals", []))
        _action_lbl = {
            "STRONG_BUY": "💎 S.BUY",
            "BUY":        "✅ BUY",
            "WATCH":      "👁 WATCH",
            "SKIP":       "⏭ SKIP",
            "AVOID":      "🚫 AVOID",
        }.get(_a, _a)
        tbl_rows += (
            f'<tr>'
            f'<td><b style="color:{_c};font-size:14px;border-left:3px solid {_c};'
            f'padding-left:7px;">{_safe(rd["ticker"])}</b></td>'
            f'<td style="font-family:monospace;">{_f(_pr)}</td>'
            f'<td><span style="background:{_c}22;border:1px solid {_c};color:{_c};'
            f'border-radius:999px;padding:2px 10px;font-size:11px;font-weight:700;">'
            f'{_action_lbl}</span></td>'
            f'<td style="color:{_c};font-size:20px;font-weight:900;'
            f'font-family:monospace;text-align:center;">{_g}</td>'
            f'<td style="text-align:center;">'
            f'<div style="background:#1a2030;border-radius:4px;height:8px;width:80px;overflow:hidden;display:inline-block;">'
            f'<div style="background:{_c};width:{_s}%;height:100%;"></div></div>'
            f'<span style="font-size:11px;color:#94a3b8;"> {_s}</span></td>'
            f'<td style="font-family:monospace;color:#fbbf24;">{_entry_str}</td>'
            f'<td style="font-family:monospace;color:#ef4444;">{_f(_sl)}</td>'
            f'<td style="font-family:monospace;color:#06b6d4;">{_f(_tp)}</td>'
            f'<td style="font-family:monospace;">{f"{_rr:.2f}:1" if _rr else "–"}</td>'
            f'<td style="font-family:monospace;color:#a78bfa;">{_pct_sz:.1f}%</td>'
            f'<td style="font-size:11px;">'
            f'{"✅ " + str(_sup_cnt) if _sup_cnt else ""}'
            f'{"  ⚠️ " + str(_flag_cnt) if _flag_cnt else ""}</td>'
            f'</tr>'
        )
    st.markdown(
        f'<table class="sum-table"><thead><tr>'
        f'<th>Mã</th><th>Giá</th><th>Hành động</th><th>Grade</th><th>Score</th>'
        f'<th>Vùng vào</th><th>SL</th><th>TP1</th><th>R:R</th>'
        f'<th>Sizing</th><th>Tín hiệu</th>'
        f'</tr></thead><tbody>{tbl_rows}</tbody></table>',
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Per-ticker recommendation cards ───────────────────────────────────────
    st.markdown("### 📋 Chi tiết từng mã")
    results_by_ticker = {r["ticker"]: r for r in valid}
    for rd in recs:
        tk = rd["ticker"]
        r  = results_by_ticker.get(tk, {})
        render_t_plus_recommendation(r)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    ticker_input, days, show_bb, show_ema, show_levels, analyse_btn, page = render_sidebar()

    if page == "🗂 Audit Log":
        render_audit_page()
        return

    if page == "📂 Portfolio Hub":
        render_portfolio_hub()
        return

    if page == "🎯 T+ Khuyến nghị":
        render_t_plus_page()
        return

    if page == "� Quản lý lệnh":
        render_active_trades_page()
        return

    if page == "🌡️ Sector Flow":
        render_sector_heatmap_page()
        return

    if page == "🔔 Cảnh báo":
        render_alerts_page()
        return

    if page == "📓 Trade Journal":
        render_trade_journal_page()
        return

    if page == "�📡 Scanner":
        render_scanner()
        return

    # Session state init
    if "results" not in st.session_state:
        st.session_state.results = []
    if "dfs" not in st.session_state:
        st.session_state.dfs = {}

    # Process on button click
    if analyse_btn and ticker_input.strip():
        import re as _re
        _VN_TICKER_RE = _re.compile(r'^(?=.*[A-Za-z])[A-Za-z0-9]{2,6}$')
        _raw = [
            t.strip().upper()
            for t in ticker_input.replace(";", ",").split(",")
            if t.strip()
        ]
        _invalid = [t for t in _raw if not _VN_TICKER_RE.match(t)]
        tickers  = [t for t in _raw if _VN_TICKER_RE.match(t)]
        if _invalid:
            st.warning(
                f"⚠️ Bỏ qua {len(_invalid)} mã không hợp lệ: "
                + ", ".join(_invalid[:10])
                + (" …" if len(_invalid) > 10 else "")
                + " — Mã VN gồm 2–6 ký tự chữ-số, phải có ít nhất 1 chữ cái."
            )
        if tickers:
            results, dfs = [], {}
            prog = st.progress(0, text="Khởi động phân tích...")
            for i, ticker in enumerate(tickers):
                prog.progress(
                    max(5, int(i / len(tickers) * 90)),
                    text=f"🔍 {ticker}... ({i + 1}/{len(tickers)})",
                )
                try:
                    result, df = cached_analyse(ticker, days)
                    # Enrich result with forecast data before saving to audit
                    if not result.get("error") and isinstance(df, pd.DataFrame) and not df.empty:
                        try:
                            _fc = multi_horizon_forecast(result, df)
                            result["fc_overall_vote"]  = _fc.get("overall_vote", "")
                            result["fc_overall_conf"]  = _fc.get("overall_conf", 0.0)
                            result["fc_short_vote"]    = _fc.get("short_vote", "")
                            result["fc_short_conf"]    = _fc.get("short_conf", 0.0)
                            result["fc_short_reasons"] = _fc.get("short_reasons", [])
                            result["fc_mid_vote"]      = _fc.get("mid_vote", "")
                            result["fc_mid_conf"]      = _fc.get("mid_conf", 0.0)
                            result["fc_mid_reasons"]   = _fc.get("mid_reasons", [])
                            result["fc_long_vote"]     = _fc.get("long_vote", "")
                            result["fc_long_conf"]     = _fc.get("long_conf", 0.0)
                            result["fc_long_reasons"]  = _fc.get("long_reasons", [])
                            result["fc_lstm_pct"]      = _fc.get("lstm_pred_pct")
                        except Exception:
                            pass
                except Exception as exc:
                    result = {"ticker": ticker, "error": str(exc)}
                    df = pd.DataFrame()
                results.append(result)
                _embed_t_rec(result)
                save_profiler_audit(result)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    dfs[ticker] = df
            prog.progress(100, text="✓ Hoàn thành")
            prog.empty()
            st.session_state.results = results
            st.session_state.dfs     = dfs

    results = st.session_state.get("results", [])
    dfs     = st.session_state.get("dfs", {})

    if not results:
        render_welcome()
        return

    # Ticker chips summary bar — always visible, never clipped
    render_ticker_chips(results)

    # ── Signal / Action filter ────────────────────────────────────────────────
    _ALL_SIGNALS = ["MUA", "THEO DÕI–TĂNG", "TRUNG LẬP", "THEO DÕI–GIẢM", "BÁN / TRÁNH"]
    _SIG_ICONS   = {
        "MUA":            "🟢",
        "THEO DÕI–TĂNG":  "🔵",
        "TRUNG LẬP":      "⚪",
        "THEO DÕI–GIẢM":  "🟠",
        "BÁN / TRÁNH":    "🔴",
    }

    if len(results) > 1:
        # Only offer signals that are actually present in current results
        _present = [
            s for s in _ALL_SIGNALS
            if any(r.get("signal") == s for r in results if "error" not in r)
        ]
        if _present:
            _opts = [f"{_SIG_ICONS[s]} {s}" for s in _present]
            _sel  = st.multiselect(
                "🔍 Lọc theo Tín hiệu / Hành động",
                options=_opts,
                default=_opts,
                key="signal_filter",
            )
            _sel_set = {s for s in _present if f"{_SIG_ICONS[s]} {s}" in _sel}
            filtered = [
                r for r in results
                if "error" in r or r.get("signal") in _sel_set
            ]
        else:
            filtered = results
    else:
        filtered = results

    if not filtered:
        st.info("ℹ️ Không có mã nào khớp với tín hiệu đã chọn.")
        return

    # ── Result area ───────────────────────────────────────────────────────────
    if len(filtered) > 1:
        tab_labels = [r["ticker"] for r in filtered]
        tabs = st.tabs(tab_labels + ["📋 Tổng kết"])
        for tab, r in zip(tabs[:-1], filtered):
            with tab:
                render_ticker_section(r, dfs, show_bb, show_ema, show_levels)
        with tabs[-1]:
            render_summary_table(filtered)
            render_correlation_matrix(filtered, dfs)
    else:
        render_ticker_section(filtered[0], dfs, show_bb, show_ema, show_levels)


if __name__ == "__main__":
    main()
