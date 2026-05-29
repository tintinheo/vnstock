"""
app.py — NewTradingOS v14.0
Vietnam Multi-Timeframe Trading Platform
Captain Seventh | Powered by Claude Sonnet 4.6

Tabs:
  0  🌐 Macro Pulse
  1  ⚡ 1W Scanner
  2  📅 2W Scanner
  3  📆 1M Scanner
  4  📊 3M Scanner
  5  🎯 5M Scanner
  6  🧠 ML Forecast
  7  🧪 Backtest
  8  💼 Portfolio
  9  📖 Guide
"""
from __future__ import annotations

import logging
import os
import sys

import streamlit as st

# ─── Path setup (must run before local imports) ───────────────
sys.path.insert(0, os.path.dirname(__file__))

# ─── Page config (must be first Streamlit call) ───────────────
st.set_page_config(
    page_title="NewTradingOS v14.0",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .main          { background:#0e1117 }
  div[data-testid="metric-container"] {
      background:#1a1f2e;border-radius:8px;padding:10px
  }
  .block-container { padding-top:1rem }
</style>
""", unsafe_allow_html=True)

# ─── Local imports ────────────────────────────────────────────
from config import (
    MARKET_SCAN_LIST, DEFAULT_WATCHLIST, TIMEFRAME_CONFIG,
    INITIAL_CAPITAL, VN_SESSIONS_YEAR,
    VN30_LIST, VN100_LIST, HOSE_LIST, HNX_LIST,
)
from core.data_fetcher import batch_download
from core.macro_data import fetch_macro_indicators, get_macro_score
from core.regime import detect_regime
from portfolio.tracker import Portfolio

# ─── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("TradingOS.app")

# ─────────────────────────────────────────────────────────────
# SESSION STATE INITIALISATION
# ─────────────────────────────────────────────────────────────
def _init_session():
    if "data_dict" not in st.session_state:
        st.session_state.data_dict     = {}
    if "macro_data" not in st.session_state:
        st.session_state.macro_data    = {}
    if "regime_result" not in st.session_state:
        st.session_state.regime_result = None
    if "macro_score" not in st.session_state:
        st.session_state.macro_score   = 5.0
    if "macro_regime" not in st.session_state:
        st.session_state.macro_regime  = "sideways"
    if "portfolio" not in st.session_state:
        st.session_state.portfolio     = Portfolio.load()
    if "lang" not in st.session_state:
        st.session_state.lang          = "VI"
    if "watchlist" not in st.session_state:
        st.session_state.watchlist     = DEFAULT_WATCHLIST.copy()

_init_session()
lang = st.session_state.lang

# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
sb = st.sidebar
sb.title("🏛️ NewTradingOS v14.0")
sb.caption("Vietnam Multi-Timeframe Trading Platform")
sb.divider()

# Language
lang_choice = sb.radio(
    "🌐 Language / Ngôn ngữ",
    ["Tiếng Việt 🇻🇳", "English 🇬🇧"],
    index=0 if lang == "VI" else 1,
    horizontal=True,
)
st.session_state.lang = "VI" if "Việt" in lang_choice else "EN"
lang = st.session_state.lang

sb.divider()
sb.subheader("⚙️ Cài đặt" if lang == "VI" else "⚙️ Settings")

# Watchlist editor
wl_str = sb.text_area(
    "Watchlist (mỗi mã 1 dòng)",
    value="\n".join(st.session_state.watchlist),
    height=180,
    key="wl_editor",
)
new_wl = [s.strip().upper() for s in wl_str.split("\n") if s.strip()]
if new_wl != st.session_state.watchlist:
    st.session_state.watchlist = new_wl

# Data controls
sb.divider()
universe_choices = sb.multiselect(
    "Universe",
    ["Watchlist", "VN30", "VN100", "HOSE", "HNX"],
    default=["Watchlist"],
    key="data_universe",
)
days_back = sb.slider("Lookback days", 180, 1095, 730, step=90, key="days_back")

# Load / Refresh
if sb.button("🔄 Tải Dữ Liệu", type="primary", key="btn_load"):
    _sym: set[str] = set()
    for _u in (universe_choices or ["Watchlist"]):
        if _u == "Watchlist":  _sym.update(st.session_state.watchlist)
        elif _u == "VN30":    _sym.update(VN30_LIST)
        elif _u == "VN100":   _sym.update(VN100_LIST)
        elif _u == "HOSE":    _sym.update(HOSE_LIST)
        elif _u == "HNX":     _sym.update(HNX_LIST)
    symbols = sorted(_sym) if _sym else st.session_state.watchlist
    with st.spinner(f"Đang tải {len(symbols)} mã…"):
        st.session_state.data_dict = batch_download(symbols, days=days_back)
    st.success(
        f"✅ Loaded {sum(1 for df, _ in st.session_state.data_dict.values() if not df.empty)}"
        f"/{len(symbols)} tickers"
    )

if sb.button("🌐 Cập nhật Macro", key="btn_macro"):
    with st.spinner("Đang tải dữ liệu vĩ mô…"):
        macro = fetch_macro_indicators()
        st.session_state.macro_data  = macro
        ms, ml = get_macro_score(macro)
        st.session_state.macro_score  = ms
        st.session_state.macro_regime = ml

        # Detect regime from VNI
        from core.data_fetcher import download_data as _dl
        vni_df, _ = _dl("VNINDEX", days=365)
        if not vni_df.empty:
            rr = detect_regime(vni_df["Close"])
            st.session_state.regime_result = rr
    st.success("✅ Macro updated")

sb.divider()
from ml.lstm_model import TF_AVAILABLE
from ml.classical_models import XGB_AVAILABLE, PROPHET_AVAILABLE, ARIMA_AVAILABLE
from core.regime import HMMLEARN_AVAILABLE as _HMM_OK

sb.caption("**Model availability:**")
sb.caption(f"  LSTM (TF): {'✅' if TF_AVAILABLE else '❌'}")
sb.caption(f"  XGBoost:   {'✅' if XGB_AVAILABLE else '❌'}")
sb.caption(f"  Prophet:   {'✅' if PROPHET_AVAILABLE else '❌'}")
sb.caption(f"  ARIMA:     {'✅' if ARIMA_AVAILABLE else '❌'}")
sb.caption(f"  HMM:       {'✅' if _HMM_OK else '❌'}")
sb.divider()
sb.caption("⚠️ Chỉ tham khảo, không phải tư vấn đầu tư")

# ─────────────────────────────────────────────────────────────
# MAIN TITLE
# ─────────────────────────────────────────────────────────────
st.title("🏛️ NewTradingOS v14.0 — Vietnam Multi-Timeframe Trading")

regime_result = st.session_state.regime_result
regime_label  = regime_result.regime if regime_result else "sideways"
macro_score   = st.session_state.macro_score
macro_data    = st.session_state.macro_data
data_dict     = st.session_state.data_dict
portfolio     = st.session_state.portfolio

if not data_dict:
    st.info(
        "👈 Nhấn **Tải Dữ Liệu** ở sidebar để bắt đầu, "
        "sau đó nhấn **Cập nhật Macro**."
    )

# Status bar
c1, c2, c3, c4 = st.columns(4)
c1.metric("Tickers loaded", len(data_dict))
if regime_result:
    from core.regime import regime_label_vi, regime_emoji
    c2.metric(
        "VNI Regime",
        f"{regime_emoji(regime_result.regime)} {regime_label_vi(regime_result.regime)}",
        f"Prob {regime_result.probability:.0%}",
    )
else:
    c2.metric("VNI Regime", "—")
c3.metric("Macro Score", f"{macro_score:.1f}/10")
c4.metric("Portfolio Value", f"{portfolio.total_value:,.0f} VND")

st.divider()

# ─────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────
tabs = st.tabs([
    "🌐 Macro Pulse",
    "⚡ 1W Scanner",
    "📅 2W Scanner",
    "📆 1M Scanner",
    "📊 3M Scanner",
    "🎯 5M Scanner",
    "🧠 ML Forecast",
    "🧪 Backtest",
    "💼 Portfolio",
    "📖 Hướng Dẫn",
])

# ── Tab 0: Macro Pulse ────────────────────────────────────────
with tabs[0]:
    from ui.macro_tab import render_macro_tab
    if macro_data:
        if regime_result is None:
            from core.regime import RegimeResult
            regime_result = RegimeResult("sideways", 0.5, [], "rule", {})
        render_macro_tab(macro_data, regime_result, lang)
    else:
        st.info("Nhấn **Cập nhật Macro** để tải dữ liệu vĩ mô.")

# ── Tabs 1-5: Scanners ────────────────────────────────────────
from ui.scanner_tab import render_scanner_tab

_TF_MAP = {"⚡ 1W": "1W", "📅 2W": "2W", "📆 1M": "1M", "📊 3M": "3M", "🎯 5M": "5M"}
for i, tf in enumerate(["1W", "2W", "1M", "3M", "5M"], start=1):
    with tabs[i]:
        if not data_dict:
            st.info("Tải dữ liệu trước để quét tín hiệu.")
        else:
            render_scanner_tab(
                tf=tf,
                data_dict=data_dict,
                regime=regime_label,
                macro_score=macro_score,
                foreign_flows={},   # extend: fetch_foreign_flow_ticker per symbol
                lang=lang,
            )

# ── Tab 6: ML Forecast ────────────────────────────────────────
with tabs[6]:
    from ui.ml_tab import render_ml_tab
    if not data_dict:
        st.info("Tải dữ liệu trước.")
    else:
        render_ml_tab(data_dict, regime_label, macro_data, lang)

# ── Tab 7: Backtest ───────────────────────────────────────────
with tabs[7]:
    from ui.backtest_tab import render_backtest_tab
    if not data_dict:
        st.info("Tải dữ liệu trước.")
    else:
        render_backtest_tab(data_dict, lang)

# ── Tab 8: Portfolio ──────────────────────────────────────────
with tabs[8]:
    from ui.portfolio_tab import render_portfolio_tab
    updated_pf = render_portfolio_tab(portfolio, data_dict, lang)
    st.session_state.portfolio = updated_pf

# ── Tab 9: Guide ─────────────────────────────────────────────
with tabs[9]:
    st.header("📖 Hướng Dẫn Sử Dụng NewTradingOS v14.0")
    st.markdown("""
### 🚀 Quick Start

1. **Sidebar → Tải Dữ Liệu**: Chọn Watchlist hoặc Market Scan, nhấn Tải.
2. **Sidebar → Cập nhật Macro**: Tải VNI regime, DXY, VIX, foreign flow.
3. **Macro Pulse tab**: Xem điều kiện thị trường tổng thể.
4. **Scanner tabs (1W–5M)**: Quét tín hiệu theo từng horizon đầu tư.
5. **ML Forecast**: Dự báo giá bằng ensemble 6 mô hình.
6. **Backtest**: Kiểm tra chiến lược trên dữ liệu lịch sử.
7. **Portfolio**: Quản lý vị thế, position sizing theo Kelly.

---

### ⏱️ Timeframe Strategy Guide

| TF | Horizon | Chiến lược | Regime phù hợp |
|---|---|---|---|
| 1W | ~5 phiên | Momentum breakout | Bull only |
| 2W | ~10 phiên | Swing + MACD cross | Bull + Sideways |
| 1M | ~22 phiên | Trend following | Bull + Sideways |
| 3M | ~66 phiên | Positional + KQKD | Mọi regime |
| 5M | ~110 phiên | Macro-driven position | Mọi regime |

---

### 📊 Score Interpretation

| Score | Action | Ý nghĩa |
|---|---|---|
| 80-100 | 🟢 STRONG BUY | Tất cả yếu tố hội tụ, tin tưởng cao |
| 65-79 | 🟢 BUY | Tín hiệu tốt, phù hợp vào lệnh |
| 45-64 | 🟡 HOLD | Trung tính, theo dõi |
| 30-44 | ⚪ WATCH | Chưa đủ điều kiện |
| 0-29 | 🔴 SELL | Tín hiệu xấu, cân nhắc cắt lỗ |

---

### ⚠️ Risk Management

- **Stop Loss**: Dùng ATR-based (không dùng % cố định)
- **Position Sizing**: Kelly Criterion (half-Kelly = an toàn hơn)
- **Max vị thế**: Tối đa theo `max_positions` trong config
- **T+2**: Chỉ bán sau 2 phiên từ ngày mua

---

### 📡 Data Sources

| Source | Ưu điểm |
|---|---|
| DNSE Entrade | Nhanh nhất, không cần auth, HOSE/HNX/UPCOM |
| SSI iBoard | Ổn định, HOSE chính xác |
| CafeF HTML | Backup cho UPCOM, IDC, OIL... |

---

> **Disclaimer**: Ứng dụng này chỉ mang tính chất tham khảo nghiên cứu.
> Không phải tư vấn đầu tư. Mọi quyết định đầu tư là trách nhiệm của nhà đầu tư.
""")
