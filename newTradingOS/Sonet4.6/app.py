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
from core.audit import log_event, ACTION_LOAD, ACTION_MACRO
from portfolio.tracker import Portfolio

# ─── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("TradingOS.app")

# Suppress harmless tornado WebSocket-closed noise that floods the terminal
# when the browser reconnects while a long batch_download is still running.
class _SuppressWsNoise(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.ERROR:
            msg = record.getMessage()
            if "WebSocketClosedError" in msg or "Stream is closed" in msg:
                return False
        return True

_asyncio_log = logging.getLogger("asyncio")
if not any(isinstance(f, _SuppressWsNoise) for f in _asyncio_log.filters):
    _asyncio_log.addFilter(_SuppressWsNoise())

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
    if "macro_stale" not in st.session_state:
        st.session_state.macro_stale   = []
    if "foreign_flows_cache" not in st.session_state:
        st.session_state.foreign_flows_cache = {}
    if "portfolio" not in st.session_state:
        st.session_state.portfolio     = Portfolio.load()
    if "lang" not in st.session_state:
        st.session_state.lang          = "VI"
    if "watchlist" not in st.session_state:
        st.session_state.watchlist     = DEFAULT_WATCHLIST.copy()
    if "data_version" not in st.session_state:
        st.session_state.data_version  = 0

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
    _total = len(symbols)
    _prog  = sb.progress(0, text=f"0 / {_total} mã…")
    _stat  = sb.empty()
    _last_upd: list[float] = [0.0]   # mutable sentinel for closure
    import time as _t
    def _on_progress(done: int, total: int, sym: str) -> None:
        now = _t.monotonic()
        # Throttle: max 1 WebSocket write/second to keep Tornado queue small.
        # Always flush at 100 % so the bar reaches completion.
        if done == total or now - _last_upd[0] >= 1.0:
            _prog.progress(done / max(total, 1),
                           text=f"{done} / {total} — {sym}")
            _stat.caption(f"⏳ {sym}")
            _last_upd[0] = now
    st.session_state.data_dict = batch_download(
        symbols, days=days_back, on_progress=_on_progress
    )
    _prog.empty()
    _stat.empty()
    _loaded = sum(1 for df, _ in st.session_state.data_dict.values() if not df.empty)
    sb.success(f"✅ Đã tải {_loaded}/{_total} mã")
    # Bump version so scanner cache is invalidated for new data
    st.session_state.data_version += 1
    st.session_state.pop("_scan_cache", None)
    log_event(
        ACTION_LOAD,
        detail={
            "universe":    universe_choices or ["Watchlist"],
            "symbols":     symbols,
            "days_back":   days_back,
            "loaded":      _loaded,
            "total":       _total,
        },
        result="ok" if _loaded == _total else "partial",
    )

if sb.button("🌐 Cập nhật Macro", key="btn_macro"):
    with st.spinner("Đang tải dữ liệu vĩ mô…"):
        macro = fetch_macro_indicators()
        st.session_state.macro_data  = macro
        ms, ml, stale = get_macro_score(macro)
        st.session_state.macro_score  = ms
        st.session_state.macro_regime = ml
        st.session_state.macro_stale  = stale

        # Detect regime from VNI — use fetch_vni_data() which has a
        # Yahoo Finance fallback when DNSE/SSI cannot serve index data.
        from core.macro_data import fetch_vni_data as _fetch_vni
        vni_df = _fetch_vni(days=365)
        if not vni_df.empty and "Close" in vni_df.columns:
            rr = detect_regime(vni_df["Close"])
            st.session_state.regime_result = rr

        # Fetch per-ticker foreign flow with 20d trend for all loaded tickers.
        # Only meaningful for 1M/3M/5M timeframes; short TFs ignore it.
        # Runs in background after world market fetch to minimise UI wait time.
        _loaded_tickers = list(st.session_state.get("data_dict", {}).keys())
        if _loaded_tickers:
            from core.macro_data import fetch_foreign_flow_tickers

            st.session_state.foreign_flows_cache = fetch_foreign_flow_tickers(
                _loaded_tickers
            )

    if stale:
        st.warning(
            f"⚠️ Macro data incomplete — could not fetch: {', '.join(stale)}. "
            "Score defaulted to neutral for missing components."
        )
    else:
        st.success("✅ Macro updated")
    log_event(
        ACTION_MACRO,
        detail={
            "macro_score":  st.session_state.macro_score,
            "macro_regime": st.session_state.macro_regime,
            "regime":       st.session_state.regime_result.regime
                            if st.session_state.regime_result else "unknown",
        },
    )

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
# Portfolio value: mark-to-market dùng giá hiện tại (thay vì total_value dùng giá vào)
_mtm_prices = {
    t: float(df["Close"].iloc[-1])
    for t, (df, _) in data_dict.items()
    if df is not None and not df.empty
}
c4.metric("Portfolio Value", f"{portfolio.market_value(_mtm_prices):,.0f} VND")

# Persistent stale-data banner (shown below metrics, cleared on next successful macro update)
_stale = st.session_state.get("macro_stale", [])
if _stale:
    st.warning(
        f"⚠️ **Macro data partial** — thiếu: {', '.join(_stale)}. "
        "Nhấn **Cập nhật Macro** để thử lại. Kết quả hiện tại dùng giá trị mặc định (neutral)."
    )

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
    "� Audit Log",
    "�📖 Hướng Dẫn",
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
from config import TICKER_EXCHANGE as _TICKER_EXCHANGE

# Build exchange map once for all scanner tabs.
# Tickers not in TICKER_EXCHANGE default to HOSE (±7%).
_exchange_map: dict[str, str] = {
    t: _TICKER_EXCHANGE.get(t, "HOSE") for t in data_dict
}

# Use cached foreign flows from session_state (populated during Macro update
# via fetch_foreign_flow_ticker per symbol). Falls back to {} if not loaded.
_foreign_flows: dict = st.session_state.get("foreign_flows_cache", {})

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
                foreign_flows=_foreign_flows,
                lang=lang,
                exchange_map=_exchange_map,
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

# ── Tab 9: Audit Log ──────────────────────────────────────────
with tabs[9]:
    from ui.audit_tab import render_audit_tab
    render_audit_tab(lang)

# ── Tab 10: Guide ─────────────────────────────────────────────
with tabs[10]:
    from ui.guide_tab import render_guide_tab
    render_guide_tab(lang)
