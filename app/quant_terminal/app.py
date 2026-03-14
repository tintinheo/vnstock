"""
Captain Seventh Quant Terminal — Main Streamlit App
Run with: streamlit run app.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import datetime as dt
import math
import json
import time

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from config import (
    APP_TITLE, APP_ICON, PORTFOLIO_DIR, TRADE_LOG_DIR,
    PRICE_REFRESH_SECONDS, MACRO_EVENTS, compute_price_limits, SELL_TAX_RATE,
    APP_VERSION, WATCHLIST_DEFAULT
)
from modules.portfolio import (
    Portfolio,
    list_portfolio_files
)
from modules.data_fetcher import (
    get_quote, get_quotes_batch, get_history, get_financials, get_history_intraday,
    get_catalyst_calendar, get_foreign_flow_batch,
    get_corporate_actions, get_company_news, get_company_profile,
)
from modules.analysis import compute_indicators, compute_signal_score, compute_beta, find_support_resistance, compute_var
from modules.scenarios import generate_scenarios, build_lo_instruction, current_session, generate_buy_scenarios
from modules.performance import compute_sharpe, compute_sortino, compute_max_drawdown, compute_trade_stats, build_monthly_pnl
from modules.market_intel import VN30_SECTORS, compute_sector_returns, compute_market_breadth
from modules.error_logger import setup_file_logging

# Activate file error logging immediately (idempotent on Streamlit re-runs)
setup_file_logging()

# ─── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CUSTOM CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Compact metrics */
  [data-testid="metric-container"] { background: #F8FAFC; border-radius: 8px; padding: 8px 12px; }
  /* Color tags */
  .tag-green  { background:#DCFCE7; color:#15803D; padding:2px 8px; border-radius:5px; font-size:12px; font-weight:500; }
  .tag-red    { background:#FEE2E2; color:#B91C1C; padding:2px 8px; border-radius:5px; font-size:12px; font-weight:500; }
  .tag-amber  { background:#FEF3C7; color:#B45309; padding:2px 8px; border-radius:5px; font-size:12px; font-weight:500; }
  .tag-blue   { background:#DBEAFE; color:#1D4ED8; padding:2px 8px; border-radius:5px; font-size:12px; font-weight:500; }
  .tag-gray   { background:#F3F4F6; color:#4B5563; padding:2px 8px; border-radius:5px; font-size:12px; font-weight:500; }
  /* Section headers */
  .section-hdr { font-size:13px; font-weight:600; color:#374151; text-transform:uppercase;
                 letter-spacing:.06em; border-bottom:1px solid #E5E7EB; padding-bottom:6px; margin-bottom:10px; }
  /* Order card */
  .order-card { background:#F9FAFB; border:1px solid #E5E7EB; border-radius:8px; padding:12px; margin-bottom:8px; }
  /* Alert */
  .alert-danger { background:#FEF2F2; border-left:4px solid #DC2626; padding:10px 14px; border-radius:0 6px 6px 0; margin:8px 0; }
  .alert-warn   { background:#FFFBEB; border-left:4px solid #F59E0B; padding:10px 14px; border-radius:0 6px 6px 0; margin:8px 0; }
  .alert-ok     { background:#F0FDF4; border-left:4px solid #16A34A; padding:10px 14px; border-radius:0 6px 6px 0; margin:8px 0; }
  /* Stacked metric */
  .kpi { text-align:center; }
  .kpi-val { font-size:22px; font-weight:600; }
  .kpi-lbl { font-size:11px; color:#6B7280; }
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ────────────────────────────────────────────────────────────
if "portfolio" not in st.session_state:
    st.session_state.portfolio = Portfolio()
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0
if "live_quotes" not in st.session_state:
    st.session_state.live_quotes = {}
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "refresh_interval" not in st.session_state:
    st.session_state.refresh_interval = 60


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def fmt_price(v, decimals=0):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:,.{decimals}f}đ"

def fmt_pct(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"

def pnl_color(v):
    if v > 0: return "#16A34A"
    if v < 0: return "#DC2626"
    return "#6B7280"

def signal_badge(label, color):
    return f'<span style="background:{color}22;color:{color};padding:2px 8px;border-radius:5px;font-size:12px;font-weight:500;">{label}</span>'


@st.cache_data(ttl=PRICE_REFRESH_SECONDS, show_spinner=False)
def cached_history(symbol: str, days: int = 252):
    return get_history(symbol, days)

@st.cache_data(ttl=PRICE_REFRESH_SECONDS, show_spinner=False)
def cached_quote(symbol: str):
    return get_quote(symbol)

@st.cache_data(ttl=60, show_spinner=False)
def cached_intraday(symbol: str, resolution: str = "15", days: int = 5):
    return get_history_intraday(symbol, resolution, days)


def refresh_quotes():
    """Refresh live prices for all portfolio symbols."""
    pf = st.session_state.portfolio
    if pf.df.empty:
        return
    symbols = list(pf.df["symbol"].unique())
    quotes  = get_quotes_batch(symbols)
    st.session_state.live_quotes = quotes
    pf.enrich_with_live_prices(quotes)
    pf.add_risk_labels()
    st.session_state.last_refresh = time.time()


@st.cache_data(ttl=300, show_spinner=False)
def cached_digest(symbol: str) -> dict:
    """Compute signal digest for one symbol — cached 5 min."""
    hist = get_history(symbol, 90)
    if hist is None or hist.empty:
        return {"score": 0, "label": "N/A", "color": "#6B7280", "rsi": 50.0, "macd_hist": 0.0}
    return compute_signal_score(hist)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_returns_matrix(symbols: tuple, days: int = 120) -> pd.DataFrame:
    """Returns matrix for correlation / VaR analysis — cached 1hr."""
    close_dict = {}
    for sym in symbols:
        h = get_history(sym, days)
        if h is not None and not h.empty and "close" in h.columns:
            close_dict[sym] = h["close"]
    if not close_dict:
        return pd.DataFrame()
    prices = pd.DataFrame(close_dict).dropna(how="all")
    return prices.pct_change().dropna()


# ─── SIDEBAR ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.markdown("---")

    # Portfolio file selector
    st.markdown("### Portfolio")
    portfolio_files = list_portfolio_files()

    uploaded = st.file_uploader(
        "Upload file SSI iBoard (.xlsx)",
        type=["xlsx", "xls"],
        help="Xuất từ SSI iBoard → Danh mục → Export Excel"
    )
    if uploaded:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        # Also save to portfolio dir
        dest = PORTFOLIO_DIR / uploaded.name
        import shutil
        shutil.copy(tmp_path, dest)
        pf = Portfolio().load_from_file(dest)
        st.session_state.portfolio = pf
        refresh_quotes()
        st.success(f"Loaded: {uploaded.name}")

    elif portfolio_files:
        selected_file = st.selectbox(
            "Hoặc chọn file có sẵn",
            options=portfolio_files,
            format_func=lambda p: p.name
        )
        if st.button("Load", use_container_width=True):
            pf = Portfolio().load_from_file(selected_file)
            st.session_state.portfolio = pf
            refresh_quotes()
            st.success(f"Loaded: {selected_file.name}")
    else:
        st.info(f"Đặt file Excel vào:\n`{PORTFOLIO_DIR}`")

    st.markdown("---")

    # Manual refresh
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Refresh giá", use_container_width=True):
            with st.spinner("Đang lấy giá mới nhất..."):
                refresh_quotes()
    with col2:
        elapsed = int(time.time() - st.session_state.last_refresh)
        st.caption(f"Cập nhật: {elapsed}s trước" if elapsed < 3600 else "Chưa refresh")

    st.markdown("---")

    # ── Auto-Refresh ──────────────────────────────────────────────────────────
    st.markdown("### ⟳ Tự động cập nhật")
    ar_col1, ar_col2 = st.columns(2)
    with ar_col1:
        ar_on = st.toggle("Bật", value=st.session_state.auto_refresh, key="ar_toggle")
        st.session_state.auto_refresh = ar_on
    with ar_col2:
        ar_int = st.selectbox(
            "Chu kỳ", [30, 60, 120, 300], index=1,
            format_func=lambda x: f"{x}s", key="ar_interval"
        )
        st.session_state.refresh_interval = ar_int

    _now      = time.time()
    _elapsed  = _now - st.session_state.last_refresh
    _interval = st.session_state.refresh_interval
    _pct      = min(100, int(_elapsed / _interval * 100))
    _rem      = max(0, int(_interval - _elapsed))
    if st.session_state.auto_refresh:
        st.progress(_pct, text=f"Refresh sau {_rem}s")
    else:
        st.caption(f"Cập nhật: {int(_elapsed)}s trước" if _elapsed < 3600 else "Chưa refresh")

    st.markdown("---")

    # Stock selector (from portfolio)
    st.markdown("### Phân tích cổ phiếu")
    pf = st.session_state.portfolio
    symbols_in_pf = list(pf.df["symbol"].unique()) if not pf.df.empty else []

    manual_sym = st.text_input("Nhập mã CK (VD: HPG, FPT)", "").upper().strip()
    if symbols_in_pf:
        pf_sym = st.selectbox("Hoặc chọn từ danh mục", ["—"] + symbols_in_pf)
        if pf_sym != "—":
            st.session_state.selected_symbol = pf_sym
    if manual_sym:
        st.session_state.selected_symbol = manual_sym

    st.markdown("---")

    # Session info
    session_name, session_desc = current_session()
    st.markdown(f"**Phiên hiện tại:** {session_name}")
    st.caption(session_desc)
    st.caption(f"Giờ HCM: {dt.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}")

    st.markdown("---")
    with st.expander("⚙️ Cấu hình"):
        st.selectbox("Nguồn dữ liệu", ["VCI", "TCBS", "KBS", "MSN"],
                     key="cfg_source",
                     help="Nguồn fallback khi SSI không khả dụng")
        st.selectbox("Chu kỳ refresh (s)", [15, 30, 60, 120, 300],
                     index=1, key="cfg_refresh",
                     help="Khoảng cách giữa các lần tự động cập nhật giá")
        st.caption("Thay đổi nhận thức tức thời — không cần khởi động lại app.")

    st.markdown("---")
    st.caption(f"Captain Seventh Quant Terminal v{APP_VERSION}")
    st.caption(f"Released: {__import__('config').RELEASE_DATE}")


# ─── MAIN TABS ────────────────────────────────────────────────────────────────

tab_dashboard, tab_stock, tab_market, tab_trade_log, tab_risk = st.tabs([
    "📊 Danh Mục",
    "🔍 Phân Tích Cổ Phiếu",
    "🌐 Thị Trường",
    "📋 Trade Log",
    "⚡ Rủi Ro",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PORTFOLIO DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

with tab_dashboard:
    pf = st.session_state.portfolio

    if pf.df.empty:
        st.markdown("""
        <div style="background:#EFF6FF;border:2px solid #3B82F6;border-radius:12px;padding:20px 24px;margin:12px 0;">
          <div style="font-size:18px;font-weight:700;color:#1E40AF;margin-bottom:8px;">👋 Chào mừng đến với Quant Terminal!</div>
          <div style="font-size:14px;color:#1D4ED8;margin-bottom:12px;">Bắt đầu bằng cách upload file danh mục từ SSI iBoard:</div>
          <ol style="color:#374151;font-size:13px;margin:0;padding-left:18px;line-height:1.8;">
            <li>Đăng nhập <b>iboard.ssi.com.vn</b> hoặc app SSI iBoard</li>
            <li>Vào <b>Tài sản → Danh mục chứng khoán</b></li>
            <li>Nhấn <b>Export → Excel (.xlsx)</b></li>
            <li>Upload file vào sidebar <b>bên trái ⬅</b></li>
          </ol>
          <div style="font-size:12px;color:#6B7280;margin-top:10px;">
            💡 Chưa có danh mục? Nhập mã CK ở sidebar → tab <b>Phân Tích Cổ Phiếu</b> để phân tích bất kỳ mã nào.
          </div>
        </div>
        """, unsafe_allow_html=True)


    # ── KPI row ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Tổng giá trị TT", fmt_price(pf.total_market), help="Tổng giá trị thị trường danh mục")
    with c2:
        delta_str = fmt_pct(pf.total_pnl_pct)
        st.metric("Lãi/Lỗ thuần", fmt_price(pf.total_pnl), delta_str)
    with c3:
        st.metric("Số mã", len(pf.df), help="Số mã cổ phiếu trong danh mục")
    with c4:
        n_profit = (pf.df["pnl_pct"] > 0).sum() if "pnl_pct" in pf.df else 0
        n_loss   = (pf.df["pnl_pct"] < 0).sum() if "pnl_pct" in pf.df else 0
        st.metric("Đang lãi / lỗ", f"{n_profit} / {n_loss}")
    with c5:
        tradeable = pf.tradeable_symbols()
        st.metric("Mã GD được (T+2)", len(tradeable), help="Số mã đã qua T+2, có thể bán ngay")

    st.markdown("---")

    # ── Portfolio table ───────────────────────────────────────────────────────
    st.markdown('<div class="section-hdr">Toàn bộ danh mục</div>', unsafe_allow_html=True)

    if not pf.df.empty:
        # Build display DataFrame
        disp_cols = []
        for _, row in pf.df.iterrows():
            pnl_pct = row.get("pnl_pct", 0)
            pnl_raw = row.get("pnl", 0)
            weight  = row.get("weight_pct", 0)
            risk    = row.get("risk_label", "—")
            tradeable_qty = row.get("tradeable_qty", 0)
            t2_ok   = "✅" if tradeable_qty and float(tradeable_qty) > 0 else "⏳"
            disp_cols.append({
                "Mã CK": row["symbol"],
                "KL": int(float(row.get("total_qty", 0))),
                "T+2": t2_ok,
                "Giá vốn": fmt_price(row.get("cost_price", 0)),
                "Giá TT": fmt_price(row.get("market_price", 0)),
                "Lãi/Lỗ (đ)": f"{'+' if pnl_raw>0 else ''}{pnl_raw:,.0f}",
                "% L/L": fmt_pct(pnl_pct),
                "% DM": f"{weight:.1f}%",
                "Rủi ro": risk,
            })

        disp_df = pd.DataFrame(disp_cols)

        # Color highlighting
        def highlight_pnl(val):
            try:
                v = float(str(val).replace("+","").replace("%","").replace(",",""))
                if v > 0: return "color: #16A34A; font-weight:500"
                if v < 0: return "color: #DC2626; font-weight:500"
            except:
                pass
            return ""

        styled = (
            disp_df.style
            .map(highlight_pnl, subset=["% L/L", "Lãi/Lỗ (đ)"])
            .set_properties(**{"font-size": "13px"})
        )
        st.dataframe(styled, use_container_width=True, height=min(50 + len(disp_df)*38, 620))

        # ── Click to analyze ─────────────────────────────────────────────────
        st.markdown("**Chọn mã để phân tích chi tiết:**")
        symbol_buttons = st.columns(min(len(pf.df), 9))
        for i, (_, row) in enumerate(pf.df.iterrows()):
            sym = row["symbol"]
            pnl_pct = row.get("pnl_pct", 0)
            color = "🟢" if pnl_pct > 0 else ("🔴" if pnl_pct < 0 else "⚪")
            with symbol_buttons[i % len(symbol_buttons)]:
                if st.button(f"{color} {sym}", key=f"btn_{sym}", use_container_width=True):
                    st.session_state.selected_symbol = sym
                    st.rerun()

    # ── Pie chart ─────────────────────────────────────────────────────────────
    if "weight_pct" in pf.df.columns and "symbol" in pf.df.columns:
        st.markdown("---")
        st.markdown('<div class="section-hdr">Phân bổ danh mục</div>', unsafe_allow_html=True)
        col_chart, col_risk = st.columns([3, 2])

        with col_chart:
            fig_pie = go.Figure(go.Pie(
                labels=pf.df["symbol"],
                values=pf.df["weight_pct"],
                hole=0.45,
                textinfo="label+percent",
                textfont_size=12,
            ))
            fig_pie.update_layout(
                height=320, margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_risk:
            st.markdown("**Cảnh báo hành động ưu tiên**")
            if "risk_label" in pf.df.columns:
                for _, row in pf.df.iterrows():
                    risk = row.get("risk_label", "")
                    sym  = row["symbol"]
                    pnl  = row.get("pnl_pct", 0)
                    if "Rất cao" in risk or "cao" in risk.lower():
                        st.markdown(f'<div class="alert-danger"><b>{sym}</b> — {risk} ({fmt_pct(pnl)})</div>',
                                    unsafe_allow_html=True)
                    elif "chốt" in risk.lower():
                        st.markdown(f'<div class="alert-ok"><b>{sym}</b> — {risk} ({fmt_pct(pnl)})</div>',
                                    unsafe_allow_html=True)
                    elif "thanh lý" in risk.lower():
                        st.markdown(f'<div class="alert-warn"><b>{sym}</b> — {risk} ({fmt_pct(pnl)})</div>',
                                    unsafe_allow_html=True)

    # ── P&L Attribution + Heat Map ────────────────────────────────────────────
    if not pf.df.empty and "pnl" in pf.df.columns:
        st.markdown("---")
        col_attr, col_heat = st.columns([1, 2])

        with col_attr:
            st.markdown('<div class="section-hdr">Đóng góp P&L</div>', unsafe_allow_html=True)
            contrib_df = pf.df[["symbol", "pnl", "pnl_pct"]].copy()
            contrib_df["pnl"]     = pd.to_numeric(contrib_df["pnl"],     errors="coerce").fillna(0)
            contrib_df["pnl_pct"] = pd.to_numeric(contrib_df["pnl_pct"], errors="coerce").fillna(0)
            contrib_df = contrib_df.sort_values("pnl")
            bar_colors = ["#16A34A" if v >= 0 else "#DC2626" for v in contrib_df["pnl"]]
            fig_bar = go.Figure(go.Bar(
                x=contrib_df["pnl"],
                y=contrib_df["symbol"],
                orientation="h",
                marker_color=bar_colors,
                text=[f"{v:+,.0f}đ" for v in contrib_df["pnl"]],
                textposition="outside",
            ))
            fig_bar.update_layout(
                height=max(220, len(contrib_df) * 44),
                margin=dict(l=0, r=70, t=10, b=0),
                xaxis_title="P&L (đ)",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(size=11),
            )
            fig_bar.update_xaxes(showgrid=True, gridcolor="#F3F4F6")
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_heat:
            st.markdown('<div class="section-hdr">Heat Map Danh Mục</div>', unsafe_allow_html=True)
            if "weight_pct" in pf.df.columns:
                heat_df = pf.df.copy()
                heat_df["pnl_pct"]    = pd.to_numeric(heat_df.get("pnl_pct",    0), errors="coerce").fillna(0)
                heat_df["weight_pct"] = pd.to_numeric(heat_df["weight_pct"],       errors="coerce").fillna(0)
                heat_df["label"]      = heat_df.apply(
                    lambda r: f"{r['symbol']}<br>{r['pnl_pct']:+.1f}%", axis=1
                )
                fig_tree = go.Figure(go.Treemap(
                    labels=heat_df["symbol"],
                    parents=["Danh Mục"] * len(heat_df),
                    values=heat_df["weight_pct"].clip(lower=0.1),
                    text=heat_df["label"],
                    textinfo="text",
                    hovertemplate=(
                        "<b>%{label}</b><br>"
                        "Tỷ trọng: %{value:.1f}%<br>"
                        "P&L: %{color:.2f}%<extra></extra>"
                    ),
                    marker=dict(
                        colors=heat_df["pnl_pct"],
                        colorscale=[
                            [0.00, "#7F1D1D"],
                            [0.30, "#DC2626"],
                            [0.50, "#F8FAFC"],
                            [0.70, "#16A34A"],
                            [1.00, "#14532D"],
                        ],
                        cmid=0,
                        showscale=True,
                        colorbar=dict(title="P&L %", thickness=10, len=0.65),
                    ),
                ))
                fig_tree.update_layout(
                    height=max(260, len(heat_df) * 36),
                    margin=dict(l=0, r=0, t=10, b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_tree, use_container_width=True)

    # ── Signal Digest ─────────────────────────────────────────────────────────
    if not pf.df.empty:
        st.markdown("---")
        st.markdown(
            '<div class="section-hdr">Signal Digest — Tín Hiệu Toàn Danh Mục</div>',
            unsafe_allow_html=True,
        )
        with st.spinner("Đang tính tín hiệu kỹ thuật..."):
            digest_rows = []
            for _, row in pf.df.iterrows():
                sym     = row["symbol"]
                sig     = cached_digest(sym)
                pnl_pct = float(row.get("pnl_pct",     0) or 0)
                mkt_p   = float(row.get("market_price", 0) or 0)
                score   = sig.get("score", 0)
                if score >= 40:
                    action = "🟢 Tích lũy thêm"
                elif score >= 10:
                    action = "🟡 Giữ"
                elif pnl_pct > 8 and score < 0:
                    action = "🟠 Chốt lời"
                elif score <= -40 or pnl_pct < -5:
                    action = "🔴 Cắt lỗ / Thoát"
                elif score <= -10:
                    action = "🟠 Giảm tỷ trọng"
                else:
                    action = "⚪ Trung tính"
                digest_rows.append({
                    "Mã":        sym,
                    "Giá TT":    round(mkt_p, 2),
                    "P&L (%)":   pnl_pct,
                    "RSI":       round(sig.get("rsi",      50), 1),
                    "MACD Hist": round(sig.get("macd_hist",  0), 2),
                    "Score":     score,
                    "Tín hiệu":  sig.get("label", "N/A"),
                    "Hành động": action,
                })

        if digest_rows:
            dig_df = pd.DataFrame(digest_rows)

            def _color_val(val):
                try:
                    v = float(val)
                    if v >= 30:  return "color:#16A34A;font-weight:600"
                    if v <= -30: return "color:#DC2626;font-weight:600"
                    if v >= 10:  return "color:#86EFAC"
                    if v <= -10: return "color:#FCA5A5"
                except Exception:
                    pass
                return ""

            styled_dig = (
                dig_df.style
                .map(_color_val, subset=["Score", "P&L (%)"])
                .format({
                    "Giá TT":    "{:,.2f}",
                    "P&L (%)":   "{:+.1f}%",
                    "RSI":       "{:.1f}",
                    "MACD Hist": "{:+.2f}",
                    "Score":     "{:+d}",
                })
                .set_properties(**{"font-size": "12px"})
            )
            st.dataframe(styled_dig, use_container_width=True, height=min(50 + len(dig_df) * 38, 420))

            best  = dig_df.nlargest(1,  "Score").iloc[0]
            worst = dig_df.nsmallest(1, "Score").iloc[0]
            bst_c, wst_c = st.columns(2)
            with bst_c:
                st.markdown(
                    f'<div class="alert-ok"><b>Top Pick: {best["Mã"]}</b> — '
                    f'Score {best["Score"]:+d} | {best["Hành động"]}</div>',
                    unsafe_allow_html=True,
                )
            with wst_c:
                st.markdown(
                    f'<div class="alert-danger"><b>Chú ý: {worst["Mã"]}</b> — '
                    f'Score {worst["Score"]:+d} | {worst["Hành động"]}</div>',
                    unsafe_allow_html=True,
                )

    # ── Save snapshot button ──────────────────────────────────────────────────
    st.markdown("---")
    if st.button("↓ Lưu snapshot danh mục", use_container_width=False):
        pf.save_snapshot()
        st.success(f"Đã lưu vào {TRADE_LOG_DIR}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — STOCK ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

with tab_stock:
    symbol = st.session_state.selected_symbol

    if not symbol:
        st.info("Chọn mã cổ phiếu từ sidebar hoặc nhấn vào mã trong tab Danh Mục.")
    if symbol:
        st.markdown(f"## Phân tích: {symbol}")

    # ── Load data ─────────────────────────────────────────────────────────────
    with st.spinner(f"Đang tải dữ liệu {symbol}..."):
        hist      = cached_history(symbol, 252)
        vnindex   = cached_history("VNINDEX", 252)
        quote     = cached_quote(symbol)
        financials= get_financials(symbol)

    position = st.session_state.portfolio.get_position(symbol)

    # Price from portfolio or live quote
    market_price = quote.get("price", 0) or 0
    if position:
        market_price = position.get("market_price", market_price) or market_price

    cost_price = float(position.get("cost_price", market_price)) if position else market_price
    qty        = int(float(position.get("total_qty", 100))) if position else 100

    # ── Quote header ──────────────────────────────────────────────────────────
    q_c1, q_c2, q_c3, q_c4, q_c5 = st.columns(5)
    with q_c1:
        chg_color = pnl_color(quote.get("change", 0))
        st.markdown(f"""
        <div style="text-align:center;">
          <div style="font-size:28px;font-weight:700;color:#1A3A5C;">{fmt_price(market_price)}</div>
          <div style="font-size:14px;color:{chg_color};">{fmt_pct(quote.get('pct_change',0))} ({fmt_price(quote.get('change',0))})</div>
        </div>""", unsafe_allow_html=True)
    with q_c2:
        st.metric("Giá vốn", fmt_price(cost_price))
    with q_c3:
        cur_pnl = (market_price - cost_price) * qty
        cur_pnl_pct = (market_price / cost_price - 1) * 100 if cost_price > 0 else 0
        st.metric("P&L vị thế", fmt_price(cur_pnl), fmt_pct(cur_pnl_pct))
    with q_c4:
        st.metric("Khối lượng nắm", f"{qty:,} CP", fmt_price(market_price * qty))
    with q_c5:
        if financials:
            st.metric("P/E", f"{financials.get('pe', 0):.1f}x")
        else:
            st.metric("Vol / TB20", fmt_pct(quote.get("pct_change", 0)))

    st.markdown("---")

    # ── Technical signals ─────────────────────────────────────────────────────
    col_sig, col_chart = st.columns([1, 3])

    with col_sig:
        st.markdown('<div class="section-hdr">Tín hiệu kỹ thuật</div>', unsafe_allow_html=True)
        if not hist.empty:
            sig = compute_signal_score(hist)
            beta = compute_beta(hist, vnindex)

            # Composite score gauge
            score = sig["score"]
            st.markdown(f"""
            <div style="text-align:center;margin:8px 0;">
              <div style="font-size:13px;color:#6B7280;">Điểm tổng hợp</div>
              <div style="font-size:36px;font-weight:700;color:{sig['color']};">{score:+d}</div>
              {signal_badge(sig['label'], sig['color'])}
            </div>""", unsafe_allow_html=True)

            st.markdown("")

            # Individual signals
            for ind, (label, direction, detail) in sig.get("signals", {}).items():
                color = "#16A34A" if direction > 0 else ("#DC2626" if direction < 0 else "#6B7280")
                icon  = "▲" if direction > 0 else ("▼" if direction < 0 else "–")
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;padding:4px 0;
                            border-bottom:0.5px solid #E5E7EB;font-size:12px;">
                  <span style="color:#374151;">{ind}</span>
                  <span style="color:{color};font-weight:500;">{icon} {label.split('—')[0].strip()}</span>
                </div>""", unsafe_allow_html=True)

            st.markdown(f"""
            <div style="margin-top:10px;font-size:12px;">
              <b>Beta vs VNINDEX:</b> {beta}<br>
              <b>RSI (14):</b> {sig.get('rsi',50):.1f}<br>
              <b>MACD Hist:</b> {sig.get('macd_hist',0):.0f}
            </div>""", unsafe_allow_html=True)

            if financials:
                st.markdown(f"""
                <div style="margin-top:10px;font-size:12px;">
                  <b>P/E:</b> {financials.get('pe',0):.1f}x<br>
                  <b>P/B:</b> {financials.get('pb',0):.2f}x<br>
                  <b>ROE:</b> {financials.get('roe',0)*100:.1f}%<br>
                  <b>Nợ/VCP:</b> {financials.get('debt_equity',0):.1f}x
                </div>""", unsafe_allow_html=True)
        else:
            st.warning("Không đủ dữ liệu lịch sử.")
            sig = {"score": 0, "label": "N/A", "color": "#6B7280", "signals": {}}

    with col_chart:
        st.markdown('<div class="section-hdr">Biểu đồ giá + Kỹ thuật</div>', unsafe_allow_html=True)
        _res_c1, _res_c2 = st.columns([4, 1])
        with _res_c2:
            chart_res = st.selectbox(
                "", ["1D", "1H", "15m"], key="chart_res",
                label_visibility="collapsed",
                help="Khung thời gian biểu đồ"
            )
        _res_map  = {"1H": "60", "15m": "15"}
        _use_hist = hist
        if chart_res != "1D" and symbol:
            _intra = cached_intraday(symbol, _res_map[chart_res], 5)
            if not _intra.empty:
                _use_hist = _intra
        if not _use_hist.empty:
            df_ind = compute_indicators(_use_hist.copy())
            fig = make_subplots(
                rows=3, cols=1,
                shared_xaxes=True,
                row_heights=[0.6, 0.2, 0.2],
                vertical_spacing=0.02,
                subplot_titles=["", "RSI", "MACD"]
            )
            # Candlestick
            fig.add_trace(go.Candlestick(
                x=df_ind.index, open=df_ind["open"], high=df_ind["high"],
                low=df_ind["low"], close=df_ind["close"],
                name=symbol, increasing_line_color="#16A34A", decreasing_line_color="#DC2626",
                showlegend=False
            ), row=1, col=1)
            # EMAs
            for ema, color in [("ema20","#F59E0B"), ("ema50","#3B82F6"), ("ema200","#8B5CF6")]:
                if ema in df_ind.columns:
                    fig.add_trace(go.Scatter(
                        x=df_ind.index, y=df_ind[ema], name=ema.upper(),
                        line=dict(color=color, width=1.2)
                    ), row=1, col=1)
            # Cost price line
            if cost_price > 0 and position:
                fig.add_hline(y=cost_price, line_dash="dash", line_color="#DC2626",
                              annotation_text=f"Giá vốn {fmt_price(cost_price)}", row=1, col=1)
            # Volume
            colors_v = ["#16A34A" if c >= o else "#DC2626"
                        for c, o in zip(df_ind["close"], df_ind["open"])]
            fig.add_trace(go.Bar(
                x=df_ind.index, y=df_ind.get("volume", pd.Series()),
                marker_color=colors_v, name="Volume", showlegend=False, opacity=0.4
            ), row=1, col=1)
            # RSI
            if "rsi" in df_ind.columns:
                fig.add_trace(go.Scatter(
                    x=df_ind.index, y=df_ind["rsi"], name="RSI",
                    line=dict(color="#8B5CF6", width=1.5), showlegend=False
                ), row=2, col=1)
                fig.add_hline(y=70, line_dash="dot", line_color="#DC2626", line_width=0.8, row=2, col=1)
                fig.add_hline(y=30, line_dash="dot", line_color="#16A34A", line_width=0.8, row=2, col=1)
            # MACD
            if "macd_hist" in df_ind.columns:
                hist_colors = ["#16A34A" if v > 0 else "#DC2626" for v in df_ind["macd_hist"].fillna(0)]
                fig.add_trace(go.Bar(
                    x=df_ind.index, y=df_ind["macd_hist"], name="MACD Hist",
                    marker_color=hist_colors, showlegend=False, opacity=0.7
                ), row=3, col=1)
                if "macd" in df_ind.columns:
                    fig.add_trace(go.Scatter(
                        x=df_ind.index, y=df_ind["macd"], name="MACD",
                        line=dict(color="#3B82F6", width=1.2), showlegend=False
                    ), row=3, col=1)

            fig.update_layout(
                height=500, xaxis_rangeslider_visible=False,
                margin=dict(l=0, r=0, t=20, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(size=11)
            )
            fig.update_xaxes(showgrid=True, gridcolor="#F3F4F6")
            fig.update_yaxes(showgrid=True, gridcolor="#F3F4F6")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Không có dữ liệu lịch sử để vẽ biểu đồ." if _use_hist.empty else "Không có dữ liệu lịch sử để vẽ biểu đồ.")

    # ── Scenario Analysis ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-hdr">Kịch bản đầu tư tuần tới</div>', unsafe_allow_html=True)

    # Probability sliders
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        p_bull = st.slider("Xác suất Bull (%)", 0, 100, 30, 5, key="p_bull") / 100
    with col_p2:
        p_base = st.slider("Xác suất Base (%)", 0, 100, 45, 5, key="p_base") / 100
    with col_p3:
        p_bear = st.slider("Xác suất Bear (%)", 0, 100, 25, 5, key="p_bear") / 100

    total_p = p_bull + p_base + p_bear
    if abs(total_p - 1.0) > 0.05:
        st.warning(f"Tổng xác suất = {total_p*100:.0f}% (nên = 100%). Các slider tự động được chuẩn hóa.")
        if total_p > 0:
            p_bull /= total_p; p_base /= total_p; p_bear /= total_p

    # Analyst target input
    analyst_target = st.number_input(
        "Giá mục tiêu analyst (để trống nếu không có)",
        min_value=0.0, value=0.0, step=100.0, format="%.0f"
    )

    if not hist.empty and cost_price > 0:
        sc = generate_scenarios(
            symbol=symbol,
            cost_price=cost_price,
            market_price=market_price,
            qty=qty,
            hist_df=hist,
            index_df=vnindex if not vnindex.empty else None,
            analyst_target=analyst_target if analyst_target > 0 else None,
            portfolio_value=st.session_state.portfolio.total_market or 38_000_000,
            user_probs={"bull": p_bull, "base": p_base, "bear": p_bear},
        )

        # Primary recommendation banner
        st.markdown(f"""
        <div style="background:{sc['action_color']}22;border:1.5px solid {sc['action_color']};
             border-radius:8px;padding:12px 18px;display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <div style="font-size:22px;font-weight:700;color:{sc['action_color']};">{sc['primary_action']}</div>
          <div style="font-size:13px;color:#374151;">
            EV giữ: <b style="color:{pnl_color(sc['ev_hold'])};">{sc['ev_hold']:+,.0f}đ/CP</b>
            &nbsp;|&nbsp; R:R Bull: <b>{sc['rr_bull']:.1f}x</b>
            &nbsp;|&nbsp; Stop: <b style="color:#DC2626;">{fmt_price(sc['stop_loss'])}</b>
          </div>
        </div>""", unsafe_allow_html=True)

        # 3-scenario cards
        sc_cols = st.columns(3)
        scenario_data = [
            ("🟢 Bull", sc["bull_target"], sc["pnl_bull"], p_bull, "#16A34A",
             "TT phục hồi, catalyst tích cực, momentum tăng"),
            ("🟡 Base", sc["base_target"], sc["pnl_base"], p_base, "#F59E0B",
             "Thị trường giằng co, không có catalyst rõ, tích lũy vùng hiện tại"),
            ("🔴 Bear", sc["bear_target"], sc["pnl_bear"], p_bear, "#DC2626",
             "TT tiếp tục giảm, kỹ thuật xấu, macro bất lợi"),
        ]
        for col, (name, target, pnl_sc, prob, color, desc) in zip(sc_cols, scenario_data):
            with col:
                pnl_pct_sc = (pnl_sc / (cost_price * qty) * 100) if cost_price * qty > 0 else 0
                st.markdown(f"""
                <div style="border:1.5px solid {color};border-radius:10px;padding:14px;height:100%;">
                  <div style="font-size:14px;font-weight:600;color:{color};">{name} — {prob*100:.0f}%</div>
                  <div style="margin:8px 0;">
                    <div style="font-size:11px;color:#6B7280;">Target giá</div>
                    <div style="font-size:20px;font-weight:600;color:{color};">{fmt_price(target)}</div>
                  </div>
                  <div style="margin:8px 0;">
                    <div style="font-size:11px;color:#6B7280;">P&L kịch bản</div>
                    <div style="font-size:14px;font-weight:500;color:{pnl_color(pnl_sc)};">
                      {pnl_sc:+,.0f}đ ({pnl_pct_sc:+.1f}%)
                    </div>
                  </div>
                  <div style="font-size:11px;color:#6B7280;margin-top:6px;">{desc}</div>
                </div>""", unsafe_allow_html=True)

        # ── Order Plan ────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div class="section-hdr">Kế hoạch lệnh đề xuất</div>', unsafe_allow_html=True)

        for order in sc["orders"]:
            qty_ord = order.get("qty", 0)
            price_ord = order.get("price", 0)
            pnl_est = order.get("pnl_est", 0)
            border_color = "#DC2626" if "Stop" in order["name"] else (
                "#F59E0B" if "50%" in order["name"] else "#16A34A"
            )
            # Sell tax line — shown for all Bán orders
            _tax_info = ""
            if order.get("side") == "Bán":
                _ord_tax = round(price_ord * qty_ord * SELL_TAX_RATE)
                _net_pnl = pnl_est - _ord_tax
                _tax_info = (
                    f' &nbsp;|&nbsp; <span style="color:#B45309;">'
                    f'Thuế 0.1%: -{_ord_tax:,.0f}đ</span>'
                    f' → net: <span style="color:{pnl_color(_net_pnl)};font-weight:500;">{_net_pnl:+,.0f}đ</span>'
                )
            st.markdown(f"""
            <div class="order-card" style="border-left:4px solid {border_color};">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                  <span style="font-weight:600;color:#1A3A5C;">{order['name']}</span>
                  <span style="margin-left:8px;font-size:11px;background:#F3F4F6;
                    padding:1px 6px;border-radius:4px;">{order['type']}</span>
                </div>
                <div style="text-align:right;">
                  <div style="font-weight:600;color:{border_color};">{fmt_price(price_ord)}</div>
                  <div style="font-size:11px;color:#6B7280;">{qty_ord:,} CP · {fmt_price(price_ord*qty_ord)}</div>
                </div>
              </div>
              <div style="font-size:12px;color:#374151;margin-top:6px;">{order['note']}</div>
              <div style="font-size:11px;color:#6B7280;margin-top:4px;">
                Trigger: {order['trigger']} &nbsp;|&nbsp;
                P&L ước: <span style="color:{pnl_color(pnl_est)};font-weight:500;">{pnl_est:+,.0f}đ</span>{_tax_info}
              </div>
            </div>""", unsafe_allow_html=True)

        # ── Support / Resistance ──────────────────────────────────────────────
        sr = find_support_resistance(hist)
        if sr["resistance"] or sr["support"]:
            st.markdown("---")
            col_sr1, col_sr2 = st.columns(2)
            with col_sr1:
                st.markdown("**Kháng cự**")
                for r in sr["resistance"]:
                    upside = (r - market_price) / market_price * 100 if market_price else 0
                    st.markdown(f"🔴 {fmt_price(r)} &nbsp; <span style='color:#6B7280;font-size:11px;'>+{upside:.1f}% từ TT</span>", unsafe_allow_html=True)
            with col_sr2:
                st.markdown("**Hỗ trợ**")
                for s in sr["support"]:
                    downside = (s - market_price) / market_price * 100 if market_price else 0
                    st.markdown(f"🟢 {fmt_price(s)} &nbsp; <span style='color:#6B7280;font-size:11px;'>{downside:.1f}% từ TT</span>", unsafe_allow_html=True)

    # ── LO / ATO / ATC Builder ────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("📋 Bộ xây dựng lệnh LO / ATO / ATC"):
        lo_c0, lo_c1, lo_c2, lo_c3, lo_c4 = st.columns(5)
        with lo_c0:
            lo_order_type = st.selectbox("Loại lệnh", ["LO", "ATO", "ATC"], key="lo_order_type")
        with lo_c1:
            lo_side  = st.selectbox("Chiều", ["Bán", "Mua"])
        with lo_c2:
            lo_qty   = st.number_input("Khối lượng (CP)", min_value=10, value=qty//2, step=10)
        with lo_c3:
            if lo_order_type == "LO":
                lo_price = st.number_input(
                    "Giá đặt (đ)", min_value=0.0,
                    value=float(market_price or cost_price or 15000.0), step=100.0
                )
            else:
                lo_price = float(market_price or cost_price or 0)
                _timing = "08:30–09:00" if lo_order_type == "ATO" else "14:30–15:00"
                st.metric("Giá", f"{lo_price:,.2f}đ",
                          f"{lo_order_type} · khớp tự động · {_timing}")
        with lo_c4:
            lo_note  = st.text_input("Ghi chú", "")

        # Ceiling / floor warning (LO only)
        if lo_order_type == "LO" and market_price > 0:
            _lo_ceil, _lo_floor = compute_price_limits(market_price)
            st.markdown(
                f'<div class="alert-ok" style="margin:6px 0;font-size:12px;">'
                f'📊 Tham chiếu: <b>{market_price:,.2f}đ</b> &nbsp;|&nbsp; '
                f'<span style="color:#16A34A;font-weight:600;">Trần: {_lo_ceil:,.2f}đ</span> &nbsp;|&nbsp; '
                f'<span style="color:#DC2626;font-weight:600;">Sàn: {_lo_floor:,.2f}đ</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if lo_price > _lo_ceil + 0.001:
                st.markdown(
                    f'<div class="alert-danger">⚠️ Giá đặt <b>{lo_price:,.0f}đ</b> vượt giá trần'
                    f' <b>{_lo_ceil:,.2f}đ</b> — lệnh sẽ bị từ chối bởi HoSE!</div>',
                    unsafe_allow_html=True,
                )
            elif lo_price > 0 and lo_price < _lo_floor - 0.001:
                st.markdown(
                    f'<div class="alert-danger">⚠️ Giá đặt <b>{lo_price:,.0f}đ</b> dưới giá sàn'
                    f' <b>{_lo_floor:,.2f}đ</b> — lệnh sẽ bị từ chối bởi HoSE!</div>',
                    unsafe_allow_html=True,
                )

        if st.button("Tạo hướng dẫn lệnh", type="primary"):
            lo = build_lo_instruction(symbol, lo_side, int(lo_qty), lo_price, lo_note, lo_order_type)
            st.markdown("**Hướng dẫn đặt lệnh trên SSI iBoard:**")
            for i, step in enumerate(lo["steps"], 1):
                st.markdown(f"{i}. {step}")
            _lo_tax_str = (
                f" &nbsp;|&nbsp; <b>Thuế bán 0.1%:</b> {lo['sell_tax']:,.0f}đ"
                if lo.get("sell_tax", 0) > 0 else ""
            )
            st.markdown(f"""
            <div style="background:#DBEAFE;border-radius:8px;padding:12px;margin-top:10px;">
              <b>Loại lệnh:</b> {lo['order_type']} &nbsp;|&nbsp;
              <b>Giá trị ước:</b> {lo['value']:,.0f}đ &nbsp;|&nbsp;
              <b>Phí ước tính:</b> {lo['brokerage_est']:,.0f}đ{_lo_tax_str} &nbsp;|&nbsp;
              <b>Phiên hiện tại:</b> {lo['session']}
            </div>""", unsafe_allow_html=True)
            st.markdown("**Lưu ý quan trọng:**")
            for note in lo["important"]:
                st.markdown(f"• {note}")

    # ── Catalyst & Events ─────────────────────────────────────────────────────
    if symbol:
        with st.expander("📅 Catalyst & Sự kiện sắp tới"):
            with st.spinner("Loading corporate actions..."):
                corp_events = get_corporate_actions(symbol)
            if not corp_events:
                # Fallback to static config
                corp_events = [
                    {"date": e.get("date", ""), "event_type": e.get("type", ""),
                     "value": e.get("value", ""), "source": "config"}
                    for e in get_catalyst_calendar(symbol)
                ]
            if corp_events:
                ev_df = pd.DataFrame(corp_events)
                show_cols = [c for c in ["date", "event_type", "value", "source"] if c in ev_df.columns]
                ev_df = ev_df[show_cols]
                ev_df.columns = [c.replace("_", " ").title() for c in show_cols]
                st.dataframe(ev_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"Chưa có sự kiện nào cho {symbol} trong 12 tháng tới.")

    # ── Company Profile ───────────────────────────────────────────────────────
    if symbol:
        with st.expander("🏢 Hồ sơ công ty"):
            with st.spinner("Loading company profile..."):
                profile = get_company_profile(symbol)
            if profile:
                _pc1, _pc2 = st.columns(2)
                with _pc1:
                    st.markdown(f"**Tên công ty:** {profile.get('name', 'N/A')}")
                    st.markdown(f"**Ngành:** {profile.get('industry', 'N/A')}")
                    st.markdown(f"**Vốn điều lệ:** {profile.get('charter_capital', 'N/A')}")
                with _pc2:
                    ws = profile.get('website', '')
                    if ws:
                        st.markdown(f"**Website:** [{ws}]({ws})")
                    else:
                        st.markdown("**Website:** N/A")
                desc = profile.get('description', '')
                if desc:
                    st.markdown("**Hoạt động KD:**")
                    st.caption(desc[:600] + ("..." if len(desc) > 600 else ""))
            else:
                st.info(f"Không tải được hồ sơ công ty cho {symbol}.")

    # ── Company News ──────────────────────────────────────────────────────────
    if symbol:
        with st.expander("📰 Tin tức gần nhất (30 ngày)"):
            with st.spinner("Loading news..."):
                news_items = get_company_news(symbol, days=30)
            if news_items:
                for item in news_items[:10]:
                    date_str = item.get('date', '')[:10]
                    title    = item.get('title', '')
                    st.markdown(f"**{date_str}** — {title}")
                    st.divider()
            else:
                st.info(f"Không có tin tức nào cho {symbol} trong 30 ngày gần nhất.")

    # ── Buy Scenario ──────────────────────────────────────────────────────────
    if symbol and not hist.empty:
        st.markdown("---")
        with st.expander("🛒 Xem xét mua mới / tích lũy thêm"):
            pf_val = float(st.session_state.portfolio.total_market or 0) * 1000
            pf_val = max(pf_val, 1_000_000.0)  # total_market is thousands-VND → raw VND
            bs_pf_val = st.number_input(
                "Giá trị tài khoản (VND)",
                min_value=1_000_000.0, value=pf_val, step=1_000_000.0, format="%.0f",
                key="bs_pf_val",
                help="Tổng giá trị danh mục để tính khối lượng đề xuất theo 2% risk rule",
            )
            bs = generate_buy_scenarios(symbol, market_price, hist, bs_pf_val)

            # Ceiling / floor warning
            _bc, _bf = bs["ceiling"], bs["floor"]
            _entry  = bs["entry_price"]
            if _entry > _bc:
                st.warning(
                    f"⚠️ Giá tham chiếu {_entry:,.2f}đ đang trên giá trần {_bc:,.2f}đ — "
                    "thị trường đang điều chỉnh. Cân nhắc chờ phiên hôm sau."
                )

            bs_c1, bs_c2, bs_c3, bs_c4 = st.columns(4)
            with bs_c1:
                st.metric("Giá vào (TT)", f"{_entry:,.2f}đ")
            with bs_c2:
                _t1_pct = (_bs_t1 := bs['target1']) / _entry - 1
                st.metric("Target 1", f"{_bs_t1:,.2f}đ", f"+{_t1_pct*100:.1f}%")
            with bs_c3:
                _sl_pct = bs['stop_loss'] / _entry - 1
                st.metric("Stop Loss", f"{bs['stop_loss']:,.2f}đ", f"{_sl_pct*100:.1f}%")
            with bs_c4:
                st.metric("R:R", f"{bs['rr']:.1f}x",
                          "✅ Tốt" if bs["rr"] >= 1.5 else "⚠️ Cân nhắc")

            st.markdown(
                f'<div class="alert-ok" style="margin:8px 0;font-size:12px;">'
                f'Biên độ ngày: '
                f'<span style="color:#16A34A;font-weight:600;">Trần {_bc:,.2f}đ</span>'
                f' &nbsp;|&nbsp; '
                f'<span style="color:#DC2626;font-weight:600;">Sàn {_bf:,.2f}đ</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            st.markdown(f"""
            <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;
                        padding:12px;margin:8px 0;">
              <b>Đề xuất KL:</b>
              <span style="font-size:18px;font-weight:700;color:#15803D;">
                {bs['recommended_qty']:,} CP
              </span>
              &nbsp;|&nbsp; <b>Giá trị:</b> {bs['value']:,.0f}đ
              &nbsp;|&nbsp; <b>Phí:</b> {bs['brokerage_est']:,.0f}đ
              &nbsp;|&nbsp; <b>Tổng CF:</b> {bs['total_cost']:,.0f}đ
            </div>""", unsafe_allow_html=True)

            st.caption(
                f"⚡ Tín hiệu: {bs['signal_label']} (score {bs['signal_score']:+d}) "
                f"| RSI: {bs['rsi']:.1f} "
                f"| Target 2: {bs['target2']:,.2f}đ"
            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — MARKET OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

with tab_market:
    st.markdown("## Tổng quan thị trường")

    col_idx1, col_idx2, col_idx3 = st.columns(3)

    with st.spinner("Đang tải dữ liệu thị trường..."):
        vni_quote = cached_quote("VNINDEX")
        vn30_quote = cached_quote("VN30")
        vni_hist = cached_history("VNINDEX", 120)

    with col_idx1:
        st.metric("VNINDEX",
                  f"{vni_quote.get('price', 0):,.2f}",
                  fmt_pct(vni_quote.get("pct_change", 0)))
    with col_idx2:
        st.metric("VN30",
                  f"{vn30_quote.get('price', 0):,.2f}",
                  fmt_pct(vn30_quote.get("pct_change", 0)))
    with col_idx3:
        session_name, session_desc = current_session()
        st.metric("Phiên GD", session_name, session_desc)

    # VNINDEX chart
    if not vni_hist.empty:
        df_vni = compute_indicators(vni_hist.copy())
        fig_vni = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                row_heights=[0.75, 0.25], vertical_spacing=0.03)
        fig_vni.add_trace(go.Scatter(
            x=df_vni.index, y=df_vni["close"],
            fill="tozeroy", fillcolor="rgba(37,99,235,0.08)",
            line=dict(color="#2563EB", width=2), name="VNINDEX"
        ), row=1, col=1)
        for ema_n, color in [("ema20","#F59E0B"), ("ema50","#8B5CF6")]:
            if ema_n in df_vni.columns:
                fig_vni.add_trace(go.Scatter(
                    x=df_vni.index, y=df_vni[ema_n], name=ema_n.upper(),
                    line=dict(color=color, width=1.2, dash="dot")
                ), row=1, col=1)
        if "volume" in df_vni.columns:
            fig_vni.add_trace(go.Bar(
                x=df_vni.index, y=df_vni["volume"],
                marker_color="#93C5FD", name="Volume", showlegend=False, opacity=0.5
            ), row=2, col=1)
        fig_vni.update_layout(
            height=380, title="VNINDEX — 120 phiên",
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=1.08, x=0)
        )
        fig_vni.update_xaxes(showgrid=True, gridcolor="#F3F4F6")
        fig_vni.update_yaxes(showgrid=True, gridcolor="#F3F4F6")
        st.plotly_chart(fig_vni, use_container_width=True)

    # Portfolio vs VNINDEX relative performance
    if not st.session_state.portfolio.df.empty and not vni_hist.empty:
        st.markdown("---")
        st.markdown('<div class="section-hdr">Danh mục — hiệu suất tương đối vs VNINDEX</div>',
                    unsafe_allow_html=True)
        pf = st.session_state.portfolio
        total_pf_pnl = pf.total_pnl_pct
        vni_return = (vni_hist["close"].iloc[-1] / vni_hist["close"].iloc[0] - 1) * 100 if not vni_hist.empty else 0
        alpha = total_pf_pnl - vni_return

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Portfolio P&L", fmt_pct(total_pf_pnl))
        with m2:
            st.metric("VNINDEX 120 phiên", fmt_pct(vni_return))
        with m3:
            st.metric("Alpha", fmt_pct(alpha),
                       "Outperform" if alpha > 0 else "Underperform")

    # ── Market Breadth ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-hdr">Breadth thị trường — VN Watchlist</div>',
                unsafe_allow_html=True)
    with st.spinner("Đang tính breadth..."):
        _breadth_syms = [s for s in WATCHLIST_DEFAULT if s not in ("VNINDEX", "VN30")]
        # Use VN30 batch if all breadth symbols are in VN30 — 1 call vs N calls
        _breadth_quotes = get_quotes_batch(_breadth_syms)
        _breadth = compute_market_breadth(_breadth_syms, _breadth_quotes)

    _bc1, _bc2, _bc3, _bc4, _bc5 = st.columns(5)
    with _bc1:
        st.metric("Tăng (Advance)", _breadth["advance"],
                  help="Số mã tăng > 0.05% trong phiên")
    with _bc2:
        st.metric("Giảm (Decline)", _breadth["decline"],
                  help="Số mã giảm > 0.05%")
    with _bc3:
        st.metric("Không đổi", _breadth["unchanged"])
    with _bc4:
        _adr = _breadth["ad_ratio"]
        _adr_str = f"{_adr:.2f}" if _adr != float("inf") else "∞"
        _adr_label = "🟢 Bullish" if _adr > 1.5 else ("🔴 Bearish" if _adr < 0.7 else "🟡 Neutral")
        st.metric("A/D Ratio", _adr_str, _adr_label)
    with _bc5:
        st.metric("Breadth %", f"{_breadth['breadth_pct']:.1f}%",
                  help="% mã tăng trong watchlist")

    # ── Sector Heatmap ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-hdr">Hiệu suất ngành — VN30 (Sector Heatmap)</div>',
                unsafe_allow_html=True)
    with st.spinner("Đang tải sector data..."):
        _vn30_syms  = list(VN30_SECTORS.keys())
        # Use batch endpoint for VN30 sector quotes — 1 HTTP call
        _vn30_quotes = get_quotes_batch(_vn30_syms)
        _sector_rets = compute_sector_returns(_vn30_quotes)

    if _sector_rets:
        _sec_df = (
            pd.DataFrame(list(_sector_rets.items()), columns=["Ngành", "Return (%)"])
            .sort_values("Return (%)", ascending=True)
        )
        _bar_colors = [
            "#16A34A" if v > 0 else ("#DC2626" if v < -0.3 else "#F59E0B")
            for v in _sec_df["Return (%)"]
        ]
        _fig_sec = go.Figure(go.Bar(
            x=_sec_df["Return (%)"],
            y=_sec_df["Ngành"],
            orientation="h",
            marker_color=_bar_colors,
            text=[f"{v:+.2f}%" for v in _sec_df["Return (%)"]],
            textposition="outside",
        ))
        _fig_sec.update_layout(
            height=max(200, len(_sec_df) * 42),
            margin=dict(l=0, r=80, t=10, b=0),
            xaxis_title="Return trung bình ngành (%)",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
        )
        _fig_sec.update_xaxes(showgrid=True, gridcolor="#F3F4F6")
        st.plotly_chart(_fig_sec, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu ngành. Thực hiện Refresh giá ở sidebar trước.")

    # ── Foreign Flow (VN30 top liquidity) ─────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-hdr">Foreign Flow — Top VN30 (phiên hôm nay)</div>',
                unsafe_allow_html=True)
    _flow_syms = ["HPG", "VCB", "FPT", "TCB", "MBB", "MSN", "GAS", "VHM"]
    with st.spinner("Đang lấy dữ liệu khối ngoại..."):
        _flows = get_foreign_flow_batch(_flow_syms)

    if _flows:
        _flow_df = pd.DataFrame(_flows)
        _flow_df = _flow_df[["symbol", "foreign_buy_val", "foreign_sell_val",
                              "foreign_net_val"]].copy()
        _flow_df.columns = ["Mã CK", "NNN Mua (k.đ)", "NNN Bán (k.đ)", "Net (k.đ)"]
        _flow_df = _flow_df.sort_values("Net (k.đ)", ascending=False)

        def _flow_color(val):
            try:
                v = float(val)
                if v > 0:   return "color:#16A34A;font-weight:600"
                if v < 0:   return "color:#DC2626;font-weight:600"
            except Exception:
                pass
            return ""

        _total_net = _flow_df["Net (k.đ)"].sum()
        _styled_flow = (
            _flow_df.style
            .map(_flow_color, subset=["Net (k.đ)"])
            .format({"NNN Mua (k.đ)": "{:,.0f}", "NNN Bán (k.đ)": "{:,.0f}", "Net (k.đ)": "{:+,.0f}"})
        )
        st.dataframe(_styled_flow, use_container_width=True, hide_index=True)
        _net_label = f"Net toàn bộ: {'🟢 +' if _total_net >= 0 else '🔴 '}{_total_net:,.0f} k.đ"
        st.caption(_net_label)
    else:
        st.info("Dữ liệu khối ngoại chưa khả dụng. SSI endpoint có thể chưa trả dữ liệu phiên này.")

    # Macro watchlist
    st.markdown("---")
    st.markdown('<div class="section-hdr">Macro & Catalyst tracking</div>', unsafe_allow_html=True)
    macro_df = pd.DataFrame(MACRO_EVENTS, columns=["Ngày", "Mã/Chủ đề", "Nội dung", "Mức độ"])
    st.dataframe(macro_df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — TRADE LOG
# ══════════════════════════════════════════════════════════════════════════════

with tab_trade_log:
    st.markdown("## Trade Log & Hiệu suất")

    # Manual trade entry
    with st.expander("Thêm giao dịch thủ công"):
        tl_c = st.columns(5)
        with tl_c[0]: tl_date   = st.date_input("Ngày GD", dt.date.today())
        with tl_c[1]: tl_sym    = st.text_input("Mã CK", "").upper()
        with tl_c[2]: tl_side   = st.selectbox("Mua/Bán", ["Mua", "Bán"])
        with tl_c[3]: tl_qty    = st.number_input("KL", min_value=10, value=100, step=10)
        with tl_c[4]: tl_price  = st.number_input("Giá", min_value=0.0, value=0.0, step=100.0)
        if st.button("Ghi nhận giao dịch"):
            if tl_sym and tl_price > 0:
                log_entry = {
                    "date": str(tl_date), "symbol": tl_sym, "side": tl_side,
                    "qty": tl_qty, "price": tl_price, "value": tl_qty * tl_price,
                    "recorded_at": dt.datetime.now().isoformat()
                }
                log_file = TRADE_LOG_DIR / "trade_log.json"
                existing = []
                if log_file.exists():
                    with open(log_file) as f:
                        try: existing = json.load(f)
                        except: existing = []
                existing.append(log_entry)
                with open(log_file, "w") as f:
                    json.dump(existing, f, default=str, ensure_ascii=False, indent=2)
                st.success(f"Đã ghi: {tl_side} {tl_qty:,} {tl_sym} @ {fmt_price(tl_price)}")

    # Load and display trade log
    log_file = TRADE_LOG_DIR / "trade_log.json"
    if log_file.exists():
        try:
            with open(log_file) as f:
                trades = json.load(f)
            if trades:
                df_log = pd.DataFrame(trades)
                df_log["value"] = pd.to_numeric(df_log["value"], errors="coerce")
                df_log = df_log.sort_values("date", ascending=False)
                st.dataframe(df_log, use_container_width=True, hide_index=True)
                total_buy  = df_log[df_log["side"]=="Mua"]["value"].sum()
                total_sell = df_log[df_log["side"]=="Bán"]["value"].sum()
                m1, m2, m3 = st.columns(3)
                with m1: st.metric("Tổng mua", fmt_price(total_buy))
                with m2: st.metric("Tổng bán", fmt_price(total_sell))
                with m3: st.metric("Số giao dịch", len(df_log))
        except Exception as e:
            st.error(f"Lỗi đọc trade log: {e}")
    else:
        st.info("Chưa có giao dịch nào. Thêm giao dịch thủ công ở trên hoặc snapshot sẽ auto-detect.")

    # ── Performance Analytics ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-hdr">Hiệu Suất Danh Mục</div>', unsafe_allow_html=True)

    # ── Build equity curve from snapshot chain ────────────────────────────────
    _snapshots = sorted(TRADE_LOG_DIR.glob("snapshot_*.json"), reverse=False)
    _equity_series = None
    if len(_snapshots) >= 2:
        _eq_rows = []
        for _sf in _snapshots:
            try:
                with open(_sf) as _fp:
                    _snap_df = pd.DataFrame(json.load(_fp))
                _mv = pd.to_numeric(_snap_df.get("market_value", pd.Series(0)), errors="coerce").sum()
                _date_str = _sf.stem.replace("snapshot_", "")
                _eq_rows.append({"date": _date_str, "value": _mv})
            except Exception:
                continue
        if len(_eq_rows) >= 2:
            _eq_df = pd.DataFrame(_eq_rows)
            _eq_df["date"] = pd.to_datetime(_eq_df["date"], errors="coerce")
            _eq_df = _eq_df.dropna(subset=["date"]).sort_values("date").set_index("date")
            _equity_series = _eq_df["value"]

    # ── Compute returns for Sharpe/Sortino/MaxDD ──────────────────────────────
    _perf_returns = None
    if _equity_series is not None and len(_equity_series) >= 10:
        _perf_returns = _equity_series.pct_change().dropna()
    elif not st.session_state.portfolio.df.empty:
        _pf_syms = list(st.session_state.portfolio.df["symbol"].unique())
        _pf_wts  = pd.to_numeric(
            st.session_state.portfolio.df.get("weight_pct", pd.Series()), errors="coerce"
        ).fillna(0).values / 100
        _rm = cached_returns_matrix(tuple(_pf_syms), 120)
        if not _rm.empty:
            _valid = [s for s in _pf_syms if s in _rm.columns]
            if _valid:
                _w = _pf_wts[:len(_valid)]
                _w = _w / _w.sum() if _w.sum() > 0 else _w
                _perf_returns = _rm[_valid].fillna(0).dot(_w)
                _equity_series = (1 + _perf_returns).cumprod()

    # ── Compute metrics ───────────────────────────────────────────────────────
    _sharpe  = compute_sharpe(_perf_returns)   if _perf_returns is not None else float("nan")
    _sortino = compute_sortino(_perf_returns)  if _perf_returns is not None else float("nan")
    _max_dd  = compute_max_drawdown(_equity_series) if _equity_series is not None else 0.0

    # ── Load trade log for trade stats & monthly P&L ──────────────────────────
    _log_file = TRADE_LOG_DIR / "trade_log.json"
    _trade_df = pd.DataFrame()
    if _log_file.exists():
        try:
            with open(_log_file) as _f:
                _trades = json.load(_f)
            _trade_df = pd.DataFrame(_trades) if _trades else pd.DataFrame()
        except Exception:
            pass

    _stats = compute_trade_stats(_trade_df) if not _trade_df.empty else None

    # ── KPI Row ───────────────────────────────────────────────────────────────
    kp1, kp2, kp3, kp4, kp5 = st.columns(5)
    def _fmt_ratio(v):
        return f"{v:.2f}" if v == v else "N/A"   # NaN check

    with kp1:
        st.metric("Sharpe Ratio",   _fmt_ratio(_sharpe),
                  help="Lợi nhuận vượt trội / độ biến động. >1.5 xuất sắc, >1.0 tốt")
    with kp2:
        st.metric("Sortino Ratio",  _fmt_ratio(_sortino),
                  help="Như Sharpe nhưng chỉ tính biến động xuống — chính xác hơn cho F0")
    with kp3:
        st.metric("Max Drawdown",   f"{_max_dd:.1f}%",
                  help="Mức giảm tối đa từ đỉnh → đáy. <-15% là cảnh báo")
    with kp4:
        st.metric("Win Rate",       f"{_stats['win_rate']:.1f}%" if _stats else "N/A",
                  help="% giao dịch có lãi")
    with kp5:
        st.metric("Profit Factor",  f"{_stats['profit_factor']:.2f}" if _stats else "N/A",
                  help="Tổng lãi / tổng lỗ. >1.5 tốt, >2.0 xuất sắc")

    # ── Equity curve ──────────────────────────────────────────────────────────
    if _equity_series is not None and len(_equity_series) >= 2:
        st.markdown("---")
        st.markdown('<div class="section-hdr">Đường vốn (Equity Curve)</div>',
                    unsafe_allow_html=True)
        _fig_eq = go.Figure(go.Scatter(
            x=_equity_series.index, y=_equity_series.values,
            fill="tozeroy", fillcolor="rgba(37,99,235,0.08)",
            line=dict(color="#2563EB", width=2), name="Portfolio"
        ))
        _fig_eq.update_layout(
            height=280, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
        )
        _fig_eq.update_xaxes(showgrid=True, gridcolor="#F3F4F6")
        _fig_eq.update_yaxes(showgrid=True, gridcolor="#F3F4F6")
        st.plotly_chart(_fig_eq, use_container_width=True)
    else:
        st.info(
            f"Cần ít nhất 2 snapshot để vẽ đường vốn. "
            f"Hiện có {len(_snapshots)} snapshot — nhấn '↓ Lưu snapshot' mỗi ngày giao dịch."
        )

    # ── Trade stats breakdown ─────────────────────────────────────────────────
    if _stats and _stats["total"] > 0:
        st.markdown("---")
        st.markdown('<div class="section-hdr">Thống kê giao dịch</div>', unsafe_allow_html=True)
        ts1, ts2, ts3, ts4 = st.columns(4)
        with ts1: st.metric("Tổng GD",     _stats["total"])
        with ts2: st.metric("Lãi / Lỗ",   f"{_stats['wins']} / {_stats['losses']}")
        with ts3: st.metric("Avg Win %",   f"+{_stats['avg_win_pct']:.2f}%")
        with ts4: st.metric("Avg R:R",     f"{_stats['avg_rr']:.2f}x")

    # ── Monthly P&L calendar ──────────────────────────────────────────────────
    if not _trade_df.empty:
        _monthly = build_monthly_pnl(_trade_df)
        if not _monthly.empty:
            st.markdown("---")
            st.markdown('<div class="section-hdr">P&L Hàng Tháng (từ trade log)</div>',
                        unsafe_allow_html=True)
            _mpnl = _monthly.pivot_table(
                index="month", columns="year", values="pnl_vnd", aggfunc="sum"
            ).fillna(0)
            _month_names = {
                1:"T1",2:"T2",3:"T3",4:"T4",5:"T5",6:"T6",
                7:"T7",8:"T8",9:"T9",10:"T10",11:"T11",12:"T12",
            }
            _mpnl.index = [_month_names.get(m, str(m)) for m in _mpnl.index]
            _fig_cal = go.Figure(go.Heatmap(
                z=_mpnl.values,
                x=[str(c) for c in _mpnl.columns],
                y=_mpnl.index.tolist(),
                colorscale=[
                    [0.00, "#7F1D1D"], [0.40, "#DC2626"],
                    [0.50, "#F8FAFC"],
                    [0.60, "#16A34A"], [1.00, "#14532D"],
                ],
                zmid=0,
                text=[[f"{v:+,.0f}đ" for v in row] for row in _mpnl.values],
                texttemplate="%{text}",
                textfont=dict(size=10),
                colorbar=dict(title="P&L (đ)", thickness=12),
            ))
            _fig_cal.update_layout(
                height=max(200, len(_mpnl) * 35 + 80),
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(size=11),
            )
            st.plotly_chart(_fig_cal, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — RISK DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

with tab_risk:
    st.markdown("## ⚡ Risk Dashboard — Phân Tích Rủi Ro")
    pf = st.session_state.portfolio

    if pf.df.empty:
        st.info("▶ Upload file Excel SSI iBoard ở sidebar để phân tích rủi ro.")
    else:
        symbols = list(pf.df["symbol"].unique())
        weight_col = pf.df.get("weight_pct", pd.Series(np.zeros(len(pf.df))))
        weights    = pd.to_numeric(weight_col, errors="coerce").fillna(0).values / 100

        # ── Load returns matrix ───────────────────────────────────────────────
        with st.spinner("Đang tính VaR & hiệp phương sai..."):
            ret_matrix = cached_returns_matrix(tuple(symbols), 252)

        # ── SECTION A: VaR ────────────────────────────────────────────────────
        st.markdown('<div class="section-hdr">Value-at-Risk (95% VaR, 1 ngày)</div>',
                    unsafe_allow_html=True)

        var_rows = []
        for i, (_, row) in enumerate(pf.df.iterrows()):
            sym    = row["symbol"]
            w      = float(weights[i]) if i < len(weights) else 0.0
            cost_p = float(row.get("cost_price",   0) or 0)
            mkt_p  = float(row.get("market_price", 0) or 0)
            pnl_vs_cost = (mkt_p / cost_p - 1) * 100 if cost_p > 0 else 0

            v = compute_var(ret_matrix[sym]) if sym in ret_matrix.columns \
                else {"var_pct": 0.0, "cvar_pct": 0.0}

            # Current drawdown from rolling high (using available return history)
            dd_now = 0.0
            if sym in ret_matrix.columns:
                cum        = (1 + ret_matrix[sym]).cumprod()
                rolling_hi = cum.cummax()
                dd_now     = float((cum / rolling_hi - 1).iloc[-1] * 100)

            var_rows.append({
                "Mã":           sym,
                "Tỷ trọng":     f"{w*100:.1f}%",
                "VaR 1D (%)":   v["var_pct"],
                "CVaR 1D (%)":  v["cvar_pct"],
                "P&L vs Vốn":   pnl_vs_cost,
                "DD hiện tại":  dd_now,
            })

        if var_rows:
            var_df = pd.DataFrame(var_rows)

            # Weighted portfolio VaR (conservative: ignores diversification)
            pf_var = float(
                (pd.to_numeric(var_df["VaR 1D (%)"], errors="coerce").fillna(0).values
                 * weights[:len(var_df)]).sum()
            ) if len(weights) >= len(var_df) else 0.0

            kv1, kv2, kv3, kv4 = st.columns(4)
            with kv1:
                st.metric("Portfolio VaR 1D (95%)", f"{pf_var:.2f}%",
                          help="Tổn thất tối đa trong 1 ngày với xác suất 95%")
            with kv2:
                worst_var = var_df.nsmallest(1, "VaR 1D (%)").iloc[0]
                st.metric("Vị thế rủi ro nhất", worst_var["Mã"],
                          f"VaR {worst_var['VaR 1D (%)']:.2f}%")
            with kv3:
                w_sq      = float((weights ** 2).sum() * 100)
                hhi_label = ("🎯 Tập trung cao" if w_sq > 40
                             else ("🔶 Vừa phải"     if w_sq > 20 else "✅ Đa dạng hóa tốt"))
                st.metric("HHI Tập trung", f"{w_sq:.1f}", hhi_label,
                          help="Herfindahl Index: <20 tốt, >40 tập trung rủi ro")
            with kv4:
                avg_pnl = var_df["P&L vs Vốn"].mean()
                st.metric("P&L TB vs vốn", f"{avg_pnl:+.1f}%")

            st.markdown("")

            def _risk_color(val):
                try:
                    v = float(str(val).replace("%", "").replace("+", ""))
                    if v < -3:  return "color:#DC2626;font-weight:600"
                    if v < -1:  return "color:#F59E0B"
                    if v > 5:   return "color:#16A34A;font-weight:600"
                except Exception:
                    pass
                return ""

            styled_var = (
                var_df.style
                .map(_risk_color, subset=["VaR 1D (%)", "CVaR 1D (%)", "P&L vs Vốn", "DD hiện tại"])
                .format({
                    "VaR 1D (%)":   "{:.2f}%",
                    "CVaR 1D (%)":  "{:.2f}%",
                    "P&L vs Vốn":   "{:+.1f}%",
                    "DD hiện tại":  "{:+.1f}%",
                })
            )
            st.dataframe(styled_var, use_container_width=True, hide_index=True)

            # VaR bar chart
            fig_var = go.Figure(go.Bar(
                x=var_df["Mã"],
                y=var_df["VaR 1D (%)"],
                text=[f"{v:.2f}%" for v in var_df["VaR 1D (%)"]],
                textposition="outside",
                marker_color=[
                    "#DC2626" if v < -2 else ("#F59E0B" if v < -1 else "#16A34A")
                    for v in var_df["VaR 1D (%)"]
                ],
            ))
            fig_var.update_layout(
                title="VaR 1D (%) theo vị thế",
                height=260, margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(size=11),
            )
            fig_var.update_yaxes(showgrid=True, gridcolor="#F3F4F6")
            st.plotly_chart(fig_var, use_container_width=True)

        # ── SECTION B: Correlation Matrix ─────────────────────────────────────
        valid_syms = [s for s in symbols if s in ret_matrix.columns]
        if len(valid_syms) > 1:
            st.markdown("---")
            st.markdown('<div class="section-hdr">Ma Trận Tương Quan (252 phiên)</div>',
                        unsafe_allow_html=True)

            corr = ret_matrix[valid_syms].corr()
            fig_corr = go.Figure(go.Heatmap(
                z=corr.values,
                x=corr.columns.tolist(),
                y=corr.index.tolist(),
                colorscale=[
                    [0.00, "#1E40AF"],
                    [0.50, "#F8FAFC"],
                    [1.00, "#7F1D1D"],
                ],
                zmid=0, zmin=-1, zmax=1,
                text=[[f"{v:.2f}" for v in row] for row in corr.values],
                texttemplate="%{text}",
                textfont=dict(size=11),
                colorbar=dict(title="Corr", thickness=12),
            ))
            fig_corr.update_layout(
                height=max(320, len(corr) * 48 + 60),
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(size=11),
            )
            st.plotly_chart(fig_corr, use_container_width=True)

            # Diversification insight
            off_diag  = corr.where(corr != 1.0).stack()
            avg_corr  = float(off_diag.mean()) if not off_diag.empty else 0
            if avg_corr > 0.7:
                st.markdown(
                    f'<div class="alert-danger">⚠️ <b>Tương quan cao</b> (avg = {avg_corr:.2f}) '
                    f'— danh mục thiếu đa dạng hóa, giảm tác dụng phân tán rủi ro.</div>',
                    unsafe_allow_html=True,
                )
            elif avg_corr > 0.4:
                st.markdown(
                    f'<div class="alert-warn">🔶 <b>Tương quan trung bình</b> (avg = {avg_corr:.2f}) '
                    f'— cân nhắc thêm mã có tương quan thấp.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="alert-ok">✅ <b>Đa dạng hóa tốt</b> (avg = {avg_corr:.2f}) '
                    f'— các vị thế ít tương quan nhau.</div>',
                    unsafe_allow_html=True,
                )

        # ── SECTION C: Kelly Criterion Optimal Sizing ─────────────────────────
        st.markdown("---")
        st.markdown('<div class="section-hdr">Quy Mô Vị Thế Tối Ưu — Kelly Criterion</div>',
                    unsafe_allow_html=True)

        kelly_rows = []
        for i, sym in enumerate(symbols):
            if sym not in ret_matrix.columns:
                continue
            r = ret_matrix[sym].dropna()
            if len(r) < 20:
                continue
            wins     = r[r > 0]
            losses   = r[r < 0]
            win_rate = len(wins) / len(r) if len(r) > 0 else 0
            avg_win  = float(wins.mean())        if len(wins)   > 0 else 0
            avg_loss = float(abs(losses.mean())) if len(losses) > 0 else 0.01
            b        = avg_win / avg_loss
            f_kelly  = max(0.0, min((win_rate * b - (1 - win_rate)) / b if b > 0 else 0, 0.5))
            f_half   = f_kelly * 0.5

            cur_w = float(weights[i]) if i < len(weights) else 0.0
            diff  = cur_w - f_half
            adj   = ("✅ OK"    if abs(diff) < 0.03
                     else ("⬆️ Tăng"  if diff < 0 else "⬇️ Giảm"))

            kelly_rows.append({
                "Mã":             sym,
                "Win Rate":       f"{win_rate*100:.0f}%",
                "Avg Win":        f"{avg_win*100:.2f}%",
                "Avg Loss":       f"{avg_loss*100:.2f}%",
                "Payoff (B)":     round(b, 2),
                "Full Kelly":     f"{f_kelly*100:.1f}%",
                "½ Kelly (rec)":  f"{f_half*100:.1f}%",
                "% Hiện tại":     f"{cur_w*100:.1f}%",
                "Điều chỉnh":     adj,
            })

        if kelly_rows:
            st.dataframe(pd.DataFrame(kelly_rows), use_container_width=True, hide_index=True)
            st.caption(
                "½ Kelly (half-Kelly) là mức an toàn được khuyến nghị — giảm rủi ro phá vỡ "
                "(ruin risk) so với Full Kelly mà chỉ tốn ~25% lợi nhuận kỳ vọng."
            )
        else:
            st.info("Không đủ dữ liệu lịch sử để tính Kelly. Thử Refresh giá trước.")


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-REFRESH ENGINE
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.get("auto_refresh"):
    _elapsed  = time.time() - st.session_state.last_refresh
    _interval = st.session_state.get("refresh_interval", 60)
    if _elapsed >= _interval:
        refresh_quotes()
        st.rerun()
    else:
        time.sleep(1)   # tick every second to animate countdown
        st.rerun()
