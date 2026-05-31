"""
app.py — NewTradingOS v14.0
Vietnam Multi-Timeframe Trading Platform
Captain Seventh | Powered by Claude Sonnet 4.6

Main workspaces:
    - 🌐 Macro Pulse
    - 🔎 Signal Review (guided by default, advanced scanner tabs optional)
    - 🧠 ML Forecast
    - 🧪 Backtest
    - 💼 Portfolio
    - 📜 Audit Log
    - 📖 Guide
"""
from __future__ import annotations

from datetime import datetime
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
    html, body, [class*="css"]  { font-family:"Segoe UI Variable","Segoe UI","Helvetica Neue",sans-serif; }
  .main          { background:#0e1117 }
  div[data-testid="metric-container"] {
            background:#151b28;border:1px solid #232b3d;border-radius:12px;padding:12px 14px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.16)
  }
    .block-container { padding-top:0.8rem; padding-bottom:2rem }
    div[data-testid="stTabs"] button { padding:0.65rem 0.9rem; border-radius:10px 10px 0 0 }
    div[data-testid="stAlert"] { border-radius:12px }
    .stMarkdown p { line-height:1.45 }
    @media (max-width: 960px) {
            .block-container { padding-left:0.65rem; padding-right:0.65rem; }
            div[data-testid="metric-container"] { padding:10px 11px; border-radius:10px; }
            div[data-testid="stTabs"] button { padding:0.55rem 0.7rem; font-size:0.9rem; }
            h1 { font-size:1.75rem !important; }
            h3 { font-size:1.1rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# ─── Local imports ────────────────────────────────────────────
from config import (
    MARKET_SCAN_LIST, DEFAULT_WATCHLIST, TIMEFRAME_CONFIG,
    INITIAL_CAPITAL, VN_SESSIONS_YEAR,
    VN30_LIST, VN100_LIST, HOSE_LIST, HNX_LIST, UPCOM_LIST,
)
from core.data_fetcher import batch_download
from core.macro_data import fetch_macro_indicators, get_macro_score
from core.regime import detect_regime
from core.universe import get_cached_exchange_counts, resolve_universe_symbols
from core.audit import log_event, ACTION_LOAD, ACTION_MACRO
from portfolio.tracker import Portfolio
from ui.components import render_guidance_callout, render_trust_ribbon

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
    if "data_loaded_at" not in st.session_state:
        st.session_state.data_loaded_at = None
    if "macro_data" not in st.session_state:
        st.session_state.macro_data    = {}
    if "macro_updated_at" not in st.session_state:
        st.session_state.macro_updated_at = None
    if "regime_result" not in st.session_state:
        st.session_state.regime_result = None
    if "regime_updated_at" not in st.session_state:
        st.session_state.regime_updated_at = None
    if "regime_stale" not in st.session_state:
        st.session_state.regime_stale = False
    if "regime_source" not in st.session_state:
        st.session_state.regime_source = "—"
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
    if "universe_meta" not in st.session_state:
        st.session_state.universe_meta = {}
    if "foreign_flow_meta" not in st.session_state:
        st.session_state.foreign_flow_meta = {}

_init_session()
lang = st.session_state.lang


def _source_mix_label(data_dict: dict) -> str:
    counts: dict[str, int] = {}
    for _, (_, source) in data_dict.items():
        src = source or "UNKNOWN"
        counts[src] = counts.get(src, 0) + 1
    if not counts:
        return "—"
    return ", ".join(f"{src}:{counts[src]}" for src in sorted(counts))


def _latest_bar_date_label(data_dict: dict) -> str:
    latest = None
    for df, _ in data_dict.values():
        if df is None or df.empty:
            continue
        idx = df.index[-1]
        try:
            idx = idx.date()
        except AttributeError:
            pass
        latest = idx if latest is None or idx > latest else latest
    return str(latest) if latest is not None else "—"


def _foreign_flow_basis_label(foreign_flows: dict) -> str:
    if not foreign_flows:
        return "Not loaded"
    counts: dict[str, int] = {}
    for payload in foreign_flows.values():
        basis = payload.get("basis") or "unknown"
        counts[basis] = counts.get(basis, 0) + 1
    return ", ".join(
        f"{basis}:{counts[basis]}"
        for basis in sorted(counts)
    )


def _foreign_flow_coverage(foreign_flows: dict) -> dict[str, int]:
    if not foreign_flows:
        return {
            "full_history": 0,
            "snapshot_proxy": 0,
            "unavailable": 0,
            "other": 0,
        }

    full_history = snapshot_proxy = unavailable = other = 0
    for payload in foreign_flows.values():
        history_sessions = int(payload.get("history_sessions", 0) or 0)
        basis = str(payload.get("basis") or "")
        if payload.get("is_20d_proxy"):
            snapshot_proxy += 1
        elif history_sessions >= 20:
            full_history += 1
        elif basis == "not_available":
            unavailable += 1
        else:
            other += 1

    return {
        "full_history": full_history,
        "snapshot_proxy": snapshot_proxy,
        "unavailable": unavailable,
        "other": other,
    }


def _is_vni_regime_stale(vni_df, max_age_days: int = 5) -> bool:
    if vni_df is None or getattr(vni_df, "empty", True):
        return True
    try:
        latest = vni_df.index[-1]
    except Exception:
        return False

    try:
        latest_date = latest.date()
    except AttributeError:
        try:
            latest_date = datetime.fromisoformat(str(latest)).date()
        except Exception:
            return False

    return (datetime.now().date() - latest_date).days > max_age_days


def _regime_source_label(vni_df) -> str:
    if vni_df is None or getattr(vni_df, "empty", True):
        return "unavailable"

    source_mode = str(vni_df.attrs.get("source_mode") or "unknown").strip().lower()
    source_name = str(vni_df.attrs.get("source_name") or "").strip()

    if source_mode == "cache":
        return "cache"
    if source_mode == "live":
        return f"live ({source_name})" if source_name else "live"
    return source_name or "unknown"


def _workflow_state(
    data_dict: dict,
    macro_data: dict,
    macro_stale: list[str],
) -> dict[str, str]:
    data_ready = bool(data_dict)
    macro_loaded = bool(macro_data)
    macro_partial = bool(macro_loaded and macro_stale)
    review_ready = data_ready and macro_loaded

    if not data_ready:
        next_action = "1. Tải Dữ Liệu"
        next_hint = "Chọn universe và tải giá trước khi review"
    elif not macro_loaded:
        next_action = "2. Cập Nhật Macro"
        next_hint = "Nạp regime, macro score, foreign-flow trước khi quét"
    elif macro_partial:
        next_action = "3. Review Thận Trọng"
        next_hint = f"Macro còn thiếu: {', '.join(macro_stale)}"
    else:
        next_action = "3. Review Tín Hiệu"
        next_hint = "Mở Signal Review để đọc ý tưởng và diagnostics"

    return {
        "data_value": "✅ Ready" if data_ready else "⏳ Pending",
        "data_delta": f"{len(data_dict)} mã | {_latest_bar_date_label(data_dict)}"
        if data_ready else "Tải dữ liệu từ sidebar",
        "macro_value": "⚠️ Partial" if macro_partial else "✅ Ready" if macro_loaded else "⏳ Pending",
        "macro_delta": st.session_state.get("macro_updated_at") or "Cập nhật Macro từ sidebar",
        "review_value": "✅ Reviewable" if review_ready else "⏳ Chưa sẵn sàng",
        "review_delta": "Signal + trust surfaces đã sẵn sàng" if review_ready else "Cần dữ liệu và macro trước",
        "next_action": next_action,
        "next_hint": next_hint,
    }


def _universe_label(key: str) -> str:
    live_counts = get_cached_exchange_counts()
    labels = {
        "Watchlist": f"Watchlist ({len(st.session_state.get('watchlist', []))} mã)",
        "VN30": f"VN30 ({len(VN30_LIST)} mã)",
        "VN100": f"VN100 ({len(VN100_LIST)} mã)",
        "Market Scan": f"Market Scan ({len(MARKET_SCAN_LIST)} configured)",
        "HOSE": f"HOSE ({live_counts.get('HOSE')} live cached)" if live_counts.get("HOSE") else "HOSE (live listing)",
        "HNX": f"HNX ({live_counts.get('HNX')} live cached)" if live_counts.get("HNX") else "HNX (live listing)",
        "UPCOM": f"UPCOM ({live_counts.get('UPCOM')} live cached)" if live_counts.get("UPCOM") else "UPCOM (live listing)",
    }
    return labels.get(key, key)

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

review_layout = sb.radio(
    "Chế độ review",
    ["Guided review", "Advanced tabs"],
    index=0,
    help="Guided review gom scanner vào một workspace; Advanced tabs giữ 5 tab scanner riêng.",
)

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
    "Scan universe",
    ["Watchlist", "VN30", "VN100", "Market Scan", "HOSE", "HNX", "UPCOM"],
    default=["Watchlist"],
    format_func=_universe_label,
    key="data_universe",
)
sb.caption(
    f"Market Scan giữ curated universe ({len(MARKET_SCAN_LIST)} mã). "
    "HOSE/HNX/UPCOM dùng live listing master khi khả dụng và sẽ fallback về bucket cấu hình nếu nguồn live không sẵn sàng."
)
days_back = sb.slider("Lookback days", 180, 1095, 730, step=90, key="days_back")

# Load / Refresh
if sb.button("🔄 Tải Dữ Liệu", type="primary", key="btn_load"):
    sb.caption("🔎 Đang resolve universe…")
    symbols, universe_meta = resolve_universe_symbols(
        universe_choices or ["Watchlist"],
        st.session_state.watchlist,
    )
    st.session_state.universe_meta = universe_meta
    _total = len(symbols)
    _chunked_load = _total > 120
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
        symbols,
        days=days_back,
        max_workers=6 if _chunked_load else 8,
        chunk_size=120,
        on_progress=_on_progress,
    )
    st.session_state.data_loaded_at = _t.strftime("%Y-%m-%d %H:%M:%S")
    _prog.empty()
    _stat.empty()
    _loaded = sum(1 for df, _ in st.session_state.data_dict.values() if not df.empty)
    sb.success(f"✅ Đã tải {_loaded}/{_total} mã")
    universe_source = ", ".join(
        f"{bucket}:{source}"
        for bucket, source in sorted(universe_meta.get("selection_sources", {}).items())
    ) or "unknown"
    sb.caption(f"Universe source: {universe_source}")
    if _chunked_load:
        sb.caption("Large-universe mode: chunked download enabled.")
    for warning in universe_meta.get("warnings", []):
        sb.warning(warning)
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
            "universe_source": universe_source,
            "universe_warnings": universe_meta.get("warnings", []),
            "chunked_load": _chunked_load,
        },
        result="ok" if _loaded == _total else "partial",
    )

if sb.button("🌐 Cập nhật Macro", key="btn_macro"):
    with st.spinner("Đang tải dữ liệu vĩ mô…"):
        macro = fetch_macro_indicators()
        st.session_state.macro_data  = macro
        ms, ml, stale = get_macro_score(macro)
        stale = list(stale)
        st.session_state.macro_score  = ms
        st.session_state.macro_regime = ml
        st.session_state.macro_updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Detect regime from VNI — use fetch_vni_data() which has a
        # Yahoo Finance fallback when DNSE/SSI cannot serve index data.
        from core.macro_data import fetch_vni_data as _fetch_vni
        vni_df = _fetch_vni(days=365)
        st.session_state.regime_source = _regime_source_label(vni_df)
        if not vni_df.empty and "Close" in vni_df.columns:
            rr = detect_regime(vni_df["Close"])
            st.session_state.regime_result = rr
            st.session_state.regime_updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.regime_stale = _is_vni_regime_stale(vni_df)
        else:
            st.session_state.regime_stale = True

        st.session_state.macro_stale  = stale

        # Fetch per-ticker foreign flow snapshot for all loaded tickers.
        # KBS currently provides session-level net flow only; true 20-session
        # continuity is not available from this endpoint.
        _loaded_tickers = list(st.session_state.get("data_dict", {}).keys())
        if _loaded_tickers:
            from core.macro_data import fetch_foreign_flow_tickers

            st.session_state.foreign_flows_cache = fetch_foreign_flow_tickers(
                _loaded_tickers
            )
            ff_meta = _foreign_flow_coverage(st.session_state.foreign_flows_cache)
            ff_meta["requested_symbols"] = len(_loaded_tickers)
            ff_meta["bounded_mode"] = len(_loaded_tickers) > 120
            st.session_state.foreign_flow_meta = ff_meta
        else:
            st.session_state.foreign_flows_cache = {}
            st.session_state.foreign_flow_meta = {}

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

workflow_state = _workflow_state(
    st.session_state.get("data_dict", {}),
    st.session_state.get("macro_data", {}),
    st.session_state.get("macro_stale", []),
)
sb.markdown("#### 🧭 Workflow")
sb.caption(f"Dữ liệu: {workflow_state['data_value']}")
sb.caption(f"Macro: {workflow_state['macro_value']}")
sb.caption(f"Tiếp theo: {workflow_state['next_action']}")

with sb.expander("🧪 System & Model Status", expanded=False):
    st.caption("**Model availability:**")
    st.caption(f"LSTM (TF): {'✅' if TF_AVAILABLE else '❌'}")
    st.caption(f"XGBoost: {'✅' if XGB_AVAILABLE else '❌'}")
    st.caption(f"Prophet: {'✅' if PROPHET_AVAILABLE else '❌'}")
    st.caption(f"ARIMA: {'✅' if ARIMA_AVAILABLE else '❌'}")
    st.caption(f"HMM: {'✅' if _HMM_OK else '❌'}")
    st.divider()
    st.caption("⚠️ Chỉ tham khảo, không phải tư vấn đầu tư")

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

workflow_state = _workflow_state(
    data_dict,
    macro_data,
    st.session_state.get("macro_stale", []),
)

st.subheader("🧭 Review Workflow")
wf1, wf2, wf3, wf4 = st.columns(4)
wf1.metric("1. Dữ liệu", workflow_state["data_value"], workflow_state["data_delta"])
wf2.metric("2. Macro", workflow_state["macro_value"], workflow_state["macro_delta"])
wf3.metric("3. Review", workflow_state["review_value"], workflow_state["review_delta"])
wf4.metric("Next Action", workflow_state["next_action"], workflow_state["next_hint"])
st.caption(
    "Guided flow: tải dữ liệu -> cập nhật macro -> mở review workspace. "
    "Advanced tabs vẫn khả dụng nếu cần so sánh nhiều timeframe song song."
)
st.divider()

# Status bar
c1, c2, c3, c4 = st.columns(4)
c1.metric("Tickers loaded", len(data_dict))
if regime_result:
    from core.regime import regime_label_vi, regime_emoji
    regime_delta = f"Prob {regime_result.probability:.0%}"
    if st.session_state.get("regime_stale"):
        regime_delta += " | stale"
    c2.metric(
        "VNI Regime",
        f"{regime_emoji(regime_result.regime)} {regime_label_vi(regime_result.regime)}",
        regime_delta,
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

# Global trust ribbon: provenance + freshness for price and macro inputs.
_ff_basis = _foreign_flow_basis_label(st.session_state.get("foreign_flows_cache", {}))
render_trust_ribbon([
    ("Price bars as-of", _latest_bar_date_label(data_dict)),
    ("Source mix", _source_mix_label(data_dict)),
    ("Macro updated", st.session_state.get("macro_updated_at") or "—"),
    ("VNI regime source", st.session_state.get("regime_source") or "—"),
    ("Foreign flow basis", _ff_basis),
])

st.caption(
    "Decision-support mode only. Review data freshness, source mix, and proxy labels before acting on any BUY/STRONG BUY signal."
)

# Persistent stale-data banner (shown below metrics, cleared on next successful macro update)
_stale = st.session_state.get("macro_stale", [])
if _stale:
    render_guidance_callout(
        "Macro data partial",
        f"Thiếu: {', '.join(_stale)}. Nhấn Cập nhật Macro để thử lại; kết quả hiện tại dùng mặc định neutral.",
        tone="warning",
    )

if st.session_state.get("regime_stale"):
    _regime_msg = (
        "Không thể làm mới VNINDEX gần đây; app đang giữ regime trước đó và đánh dấu stale trong metric."
        if st.session_state.get("regime_result")
        else "Không thể làm mới VNINDEX; app tạm giữ regime mặc định sideways cho tới khi lần cập nhật sau thành công."
    )
    render_guidance_callout(
        "VNI regime stale",
        _regime_msg,
        tone="warning",
    )

_ff_meta = st.session_state.get("foreign_flow_meta", {})
if _ff_meta.get("bounded_mode"):
    render_guidance_callout(
        "Foreign-flow coverage bounded",
        f"Universe lớn ({_ff_meta.get('requested_symbols', 0)} mã): CafeF history {_ff_meta.get('full_history', 0)} | "
        f"KBS snapshot {_ff_meta.get('snapshot_proxy', 0)} | unavailable {_ff_meta.get('unavailable', 0)}. "
        "App bỏ qua live CafeF batch để tránh macro refresh treo; review score cần ưu tiên đọc trust ribbon trước khi hành động.",
        tone="info",
    )

st.divider()

# ─────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────
advanced_scanners = review_layout == "Advanced tabs"
tab_labels = ["🌐 Macro Pulse"]
if advanced_scanners:
    tab_labels.extend([
        "⚡ 1W Scanner",
        "📅 2W Scanner",
        "📆 1M Scanner",
        "📊 3M Scanner",
        "🎯 5M Scanner",
    ])
else:
    tab_labels.append("🔎 Signal Review")
tab_labels.extend([
    "🧠 ML Forecast",
    "🧪 Backtest",
    "💼 Portfolio",
    "📜 Audit Log",
    "📖 Hướng Dẫn",
])
tabs = st.tabs(tab_labels)
tab_idx = 0

# ── Tab 0: Macro Pulse ────────────────────────────────────────
with tabs[tab_idx]:
    from ui.macro_tab import render_macro_tab
    if macro_data:
        if regime_result is None:
            from core.regime import RegimeResult
            regime_result = RegimeResult("sideways", 0.5, [], "rule", {})
        render_macro_tab(macro_data, regime_result, lang)
    else:
        st.info("Nhấn **Cập nhật Macro** để tải dữ liệu vĩ mô.")
tab_idx += 1

# ── Signal Review / Advanced Scanner Tabs ─────────────────────
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
if advanced_scanners:
    for tf in ["1W", "2W", "1M", "3M", "5M"]:
        with tabs[tab_idx]:
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
        tab_idx += 1
else:
    with tabs[tab_idx]:
        st.subheader("🔎 Signal Review Workspace")
        if not data_dict:
            st.info("Tải dữ liệu trước để bắt đầu review tín hiệu.")
        else:
            review_col1, review_col2 = st.columns([3, 2])
            with review_col1:
                selected_tf = st.radio(
                    "Timeframe review",
                    ["1W", "2W", "1M", "3M", "5M"],
                    index=2,
                    horizontal=True,
                    format_func=lambda tf: TIMEFRAME_CONFIG[tf]["label"],
                    key="guided_review_tf",
                )
            with review_col2:
                review_basis = _foreign_flow_basis_label(_foreign_flows)
                st.metric(
                    "Review context",
                    f"{TIMEFRAME_CONFIG[selected_tf]['label']} | {regime_label}",
                    f"Macro {macro_score:.1f}/10",
                )
            st.caption(
                "Guided review mode gom tất cả scanner vào một workspace. "
                f"Foreign-flow basis hiện tại: {review_basis}."
            )
            render_scanner_tab(
                tf=selected_tf,
                data_dict=data_dict,
                regime=regime_label,
                macro_score=macro_score,
                foreign_flows=_foreign_flows,
                lang=lang,
                exchange_map=_exchange_map,
            )
    tab_idx += 1

# ── Tab 6: ML Forecast ────────────────────────────────────────
with tabs[tab_idx]:
    from ui.ml_tab import render_ml_tab
    if not data_dict:
        st.info("Tải dữ liệu trước.")
    else:
        render_ml_tab(data_dict, regime_label, macro_data, lang)
tab_idx += 1

# ── Tab 7: Backtest ───────────────────────────────────────────
with tabs[tab_idx]:
    from ui.backtest_tab import render_backtest_tab
    if not data_dict:
        st.info("Tải dữ liệu trước.")
    else:
        render_backtest_tab(data_dict, lang)
tab_idx += 1

# ── Tab 8: Portfolio ──────────────────────────────────────────
with tabs[tab_idx]:
    from ui.portfolio_tab import render_portfolio_tab
    updated_pf = render_portfolio_tab(portfolio, data_dict, lang)
    st.session_state.portfolio = updated_pf
tab_idx += 1

# ── Tab 9: Audit Log ──────────────────────────────────────────
with tabs[tab_idx]:
    from ui.audit_tab import render_audit_tab
    render_audit_tab(lang)
tab_idx += 1

# ── Tab 10: Guide ─────────────────────────────────────────────
with tabs[tab_idx]:
    from ui.guide_tab import render_guide_tab
    render_guide_tab(lang)
