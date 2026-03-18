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
    HISTORY_DAYS,
    _last,
)
from portfolio_engine import (
    parse_portfolio_csv,
    classify_settlement_status,
    calculate_performance,
    build_portfolio_summary,
    T25ExitManager,
)
from forecast_engine import (
    promethee_ii_ranking,
    monte_carlo_projection,
    multi_horizon_forecast,
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
/* ── Filterable-table search box ──────────────────────────────── */
.tbl-search-wrap { margin: 0 0 8px; }
.tbl-search-wrap input {
  width: 100%;
  background: #141824;
  border: 1px solid #2d3347;
  border-radius: 6px;
  color: #e2e8f0;
  font-size: 13px;
  padding: 6px 12px;
  outline: none;
  box-sizing: border-box;
}
.tbl-search-wrap input::placeholder { color: #475569; }
.tbl-search-wrap input:focus { border-color: #3b82f6; }
tr.tbl-hidden { display: none !important; }
</style>
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

    st.markdown(f"""
<div class="price-header">
  <div>
    <div class="ph-label">Mã · Tín hiệu</div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:3px;">
      <span style="font-size:26px;font-weight:800;">{_safe(r['ticker'])}</span>
      {_badge(sig)} {regime_html} {conf_flag} {ceil_flag}{flr_flag}
    </div>
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
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
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
    fc = multi_horizon_forecast(r, df)
    with st.expander(
        f"🔭 Dự báo Đa Khung Thời gian  ·  Tổng hợp: {fc['overall_vote']}  ({fc['overall_conf']:.0f}%)",
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
    """Wrap a <table> in a live-search input that hides non-matching rows."""
    tagged = html.replace("<table ", f'<table id="{table_id}" ')
    return (
        f'<div class="tbl-search-wrap">'
        f'<input id="{table_id}_q" oninput="(function(){{'
        f'var q=document.getElementById(\'{table_id}_q\').value.toLowerCase();'
        f'document.querySelectorAll(\'#{table_id} tbody tr\').forEach(function(r){{'
        f'r.classList.toggle(\'tbl-hidden\',!r.innerText.toLowerCase().includes(q));'
        f'}});}})()" placeholder="🔍 Lọc theo mã, tín hiệu, chỉ số..." />'
        f'</div>'
        + tagged
    )


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
  <td>{rank_html}</td>
</tr>"""
    table_html = f'''
<table class="sum-table">
  <thead>
    <tr>
      <th>Mã</th><th>Giá</th><th>%Δ</th>
      <th>RSI</th><th>Stoch</th><th>ADX</th><th>KL×</th>
      <th>Cấu trúc MA</th><th>Tín hiệu</th>
      <th title="VN-Swing Alpha T+2.5 score">T+2.5</th><th>MCDA Rank</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
'''
    st.markdown(_filterable_table("summary_tbl", table_html), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT HELPERS  (reads data/Profiler/*.json JSONL files)
# ═══════════════════════════════════════════════════════════════════════════════
_AUDIT_DIR = os.path.join(_DIR, "data", "Profiler")


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
    label  = f"{'⚡ ' if changed else ''}#{idx+1}  {ts_}  ·  {sig_}  ·  Bull {bp_:.0f}%  ·  {_f(row.get('price'))}"
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

    # ― Overview metrics ――――――――――――――――――――――――――――――――――――――――――――――――
    st.markdown("### 🗂️ Audit Log — Lịch sử phân tích")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📁 Mã đang theo dõi",  len(latest_by_ticker))
    m2.metric("🔄 Tổng lần quét",     all_runs_count)
    m3.metric("⚠️ Thay đổi tín hiệu", len(signal_changes))
    m4.metric("⏱ Lần quét cuối",      last_scan_ts[:16].replace("T", " ") if last_scan_ts else "–")

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
        sort_by = st.selectbox("📶 Sắp xếp", ["Tín hiệu", "Bull %↓", "Giá↓", "Thay đổi↓", "Mã A→Z"],
                               key="audit_sort")

    # ― Apply filters ―――――――――――――――――――――――――――――――――――――――――――――――――――
    filtered = [
        r for r in latest_by_ticker.values()
        if "error" not in r
        and (not ticker_filter or r["ticker"] in ticker_filter)
        and (sig_filter == _SIG_ALL or r.get("signal", "") == sig_filter)
        and (date_filter == _DATE_ALL or (r.get("run_ts") or "")[:10] == date_filter)
    ]

    _SIG_ORDER = ["MUA", "THEO DÕI–TĂNG", "TRUNG LẬP", "THEO DÕI–GIẢM", "BÁN / TRÁNH", ""]
    def _sig_rank(r): return _SIG_ORDER.index(r.get("signal","")) if r.get("signal","") in _SIG_ORDER else 99
    if sort_by == "Tín hiệu":
        filtered.sort(key=_sig_rank)
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
            ["📊 Phân tích", "📂 Portfolio Hub", "📡 Scanner", "🗂 Audit Log"],
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
        })
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
            f'</tr>'
        )

    scanner_table_html = (
        f'<table class="sum-table"><thead><tr>'
        f'<th>Hạng</th><th>Mã</th><th>Giá</th><th>%Δ</th>'
        f'<th>Tín hiệu</th><th>NetFlow</th><th>Bull%</th>'
        f'<th>Thanh khoản</th><th>Biến động</th><th>R:R</th>'
        f'<th title="VN-Swing Alpha T+2.5">T+2.5</th>'
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

    if page == "📡 Scanner":
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

    # Multiple tickers → tabbed layout
    if len(results) > 1:
        # Use short tab labels (no emoji prefix) to save horizontal space
        tab_labels = [r["ticker"] for r in results]
        tabs = st.tabs(tab_labels + ["📋 Tổng kết"])
        for tab, r in zip(tabs[:-1], results):
            with tab:
                render_ticker_section(r, dfs, show_bb, show_ema, show_levels)
        with tabs[-1]:
            render_summary_table(results)
    else:
        render_ticker_section(results[0], dfs, show_bb, show_ema, show_levels)


if __name__ == "__main__":
    main()
