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

import pandas as pd
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
    INITIAL_CAPITAL,
    TICKER_EXCHANGE, VN30_LIST, VN100_LIST, HOSE_LIST, HNX_LIST, UPCOM_LIST,
)
from core.data_fetcher import batch_download
from core.market_calendar import calendar_basis_summary
from core.macro_data import fetch_macro_indicators, fetch_vni_data, get_macro_score
from core.regime import detect_regime
from core.universe import get_cached_exchange_counts, resolve_universe_symbols
from core.audit import log_event, ACTION_LOAD, ACTION_MACRO
from portfolio.tracker import Portfolio
from ui.components import render_decision_panel, render_guidance_callout, render_trust_ribbon

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
    if "regime_last_attempt_at" not in st.session_state:
        st.session_state.regime_last_attempt_at = None
    if "vni_df" not in st.session_state:
        st.session_state.vni_df = None
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
    if "exchange_map" not in st.session_state:
        st.session_state.exchange_map = {}
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


def _is_vni_regime_stale(vni_df, max_age_days: int = 1) -> bool:
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


def _refresh_vni_regime(*, force: bool = False, max_age_days: int = 1) -> bool:
    current_vni = st.session_state.get("vni_df")
    if not force and not _is_vni_regime_stale(current_vni, max_age_days=max_age_days):
        st.session_state.regime_stale = False
        return False

    if not force:
        last_attempt = st.session_state.get("regime_last_attempt_at")
        if last_attempt:
            try:
                last_attempt_dt = datetime.fromisoformat(str(last_attempt))
                if (datetime.now() - last_attempt_dt).total_seconds() < 300:
                    return False
            except Exception:
                pass

    st.session_state.regime_last_attempt_at = datetime.now().isoformat(timespec="seconds")
    vni_days = _vni_history_days_for_loaded_data(
        st.session_state.get("data_dict", {}),
        default_days=365,
    )
    vni_df = fetch_vni_data(days=vni_days)
    st.session_state.vni_df = vni_df
    st.session_state.regime_source = _regime_source_label(vni_df)

    if not vni_df.empty and "Close" in vni_df.columns:
        rr = detect_regime(vni_df["Close"])
        st.session_state.regime_result = rr
        st.session_state.regime_updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.regime_stale = _is_vni_regime_stale(vni_df, max_age_days=max_age_days)
        return True

    st.session_state.regime_stale = True
    return False


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


def _vni_history_days_for_loaded_data(data_dict: dict, default_days: int = 365) -> int:
    earliest_date = None
    for payload in (data_dict or {}).values():
        if not isinstance(payload, tuple) or not payload:
            continue
        df = payload[0]
        if df is None or getattr(df, "empty", True):
            continue
        index = pd.to_datetime(getattr(df, "index", []), errors="coerce")
        index = index[~index.isna()]
        if len(index) == 0:
            continue
        current_earliest = index.min().date()
        if earliest_date is None or current_earliest < earliest_date:
            earliest_date = current_earliest

    baseline = max(365, int(default_days or 365))
    if earliest_date is None:
        return baseline

    required_days = (datetime.now().date() - earliest_date).days + 30
    return max(baseline, min(required_days, 3650))


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


if _is_vni_regime_stale(st.session_state.get("vni_df"), max_age_days=1):
    with st.spinner("Đang đồng bộ VNI regime mới nhất…"):
        _refresh_vni_regime(force=False, max_age_days=1)

# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
sb = st.sidebar
sb.title("🏛️ NewTradingOS v14.0")
sb.caption("Vietnam Multi-Timeframe Trading Platform")
sb.divider()

# ── Universe & Controls ───────────────────────────────────────
with sb.expander("⚙️ Universe & Controls", expanded=True):
    # Language
    lang_choice = st.radio(
        "🌐 Language",
        ["Tiếng Việt 🇻🇳", "English 🇬🇧"],
        index=0 if lang == "VI" else 1,
        horizontal=True,
    )
    st.session_state.lang = "VI" if "Việt" in lang_choice else "EN"
    lang = st.session_state.lang

    st.divider()

    review_layout = st.radio(
        "Chế độ review",
        ["Guided review", "Advanced tabs"],
        index=0,
        help="Guided review gom scanner vào một workspace; Advanced tabs giữ 5 tab scanner riêng.",
    )

    # Watchlist editor
    wl_str = st.text_area(
        "Watchlist (mỗi mã 1 dòng)",
        value="\n".join(st.session_state.watchlist),
        height=130,
        key="wl_editor",
    )
    new_wl = [s.strip().upper() for s in wl_str.split("\n") if s.strip()]
    if new_wl != st.session_state.watchlist:
        st.session_state.watchlist = new_wl

    universe_choices = st.multiselect(
        "Scan universe",
        ["Watchlist", "VN30", "VN100", "Market Scan", "HOSE", "HNX", "UPCOM"],
        default=["Watchlist"],
        format_func=_universe_label,
        key="data_universe",
    )
    st.caption(
        f"Market Scan giữ curated universe ({len(MARKET_SCAN_LIST)} mã). "
        "HOSE/HNX/UPCOM dùng live listing master khi khả dụng."
    )
    days_back = st.slider("Lookback days", 180, 1095, 730, step=90, key="days_back")

sb.divider()
universe_choices = st.session_state.get("data_universe", ["Watchlist"])
days_back = st.session_state.get("days_back", 730)

# ── Session Actions ───────────────────────────────────────────
_btn_col1, _btn_col2 = sb.columns(2)
_do_refresh = _btn_col1.button("🔄 Tải & Macro", type="primary", key="btn_refresh_all",
                               help="Tải dữ liệu giá + cập nhật macro trong một bước.",
                               use_container_width=True)
_do_macro_only = _btn_col2.button("🌐 Macro only", key="btn_macro_only",
                                  help="Chỉ cập nhật macro/regime, giữ nguyên dữ liệu giá.",
                                  use_container_width=True)
_do_load_only = sb.button("📥 Chỉ tải dữ liệu giá", key="btn_load_only",
                          help="Tải/làm mới dữ liệu giá mà không cập nhật macro.",
                          use_container_width=True)

# ── Shared load-data logic ───────────────────────────────────
def _run_load_data() -> None:
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
    _resolved_exchange_map = universe_meta.get("exchange_map", {})
    st.session_state.exchange_map = {
        symbol: str(_resolved_exchange_map.get(symbol, TICKER_EXCHANGE.get(symbol, "HOSE"))).strip().upper() or "HOSE"
        for symbol in st.session_state.data_dict
    }
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

# ── Shared macro-update logic ────────────────────────────────
def _run_macro_update() -> None:
    with st.spinner("Đang tải dữ liệu vĩ mô…"):
        macro = fetch_macro_indicators()
        st.session_state.macro_data  = macro
        ms, ml, stale = get_macro_score(macro)
        stale = list(stale)
        st.session_state.macro_score  = ms
        st.session_state.macro_regime = ml
        st.session_state.macro_updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        _refresh_vni_regime(force=True, max_age_days=1)

        st.session_state.macro_stale  = stale

        _loaded_tickers = list(st.session_state.get("data_dict", {}).keys())
        if _loaded_tickers:
            from core.macro_data import fetch_foreign_flow_tickers

            st.session_state.foreign_flows_cache = fetch_foreign_flow_tickers(
                _loaded_tickers,
                exchange_map=st.session_state.get("exchange_map", {}),
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

if _do_refresh or _do_load_only:
    _run_load_data()
if _do_refresh or _do_macro_only:
    _run_macro_update()

sb.divider()
from ml.lstm_model import TF_AVAILABLE
from ml.classical_models import XGB_AVAILABLE, PROPHET_AVAILABLE, ARIMA_AVAILABLE
from core.regime import HMMLEARN_AVAILABLE as _HMM_OK

workflow_state = _workflow_state(
    st.session_state.get("data_dict", {}),
    st.session_state.get("macro_data", {}),
    st.session_state.get("macro_stale", []),
)
with sb.expander("🧭 Workflow Status", expanded=False):
    st.caption(f"Dữ liệu: {workflow_state['data_value']}")
    st.caption(f"Macro: {workflow_state['macro_value']}")
    st.caption(f"Tiếp theo: **{workflow_state['next_action']}**")

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
    # ── Onboarding card ───────────────────────────────────────
    _step1_done = bool(data_dict)
    _step2_done = bool(macro_data)
    _s = lambda done: "✅" if done else "○"
    st.markdown(
        f"""
<div style='border:1px solid #232b3d;border-radius:14px;padding:1.1rem 1.4rem;
background:#151b28;margin-bottom:1rem;'>
  <div style='font-size:0.82rem;color:#9db0c9;margin-bottom:0.6rem;'>🚀 Bắt đầu trong 3 bước</div>
  <div style='display:flex;flex-wrap:wrap;gap:1.5rem;'>
    <div style='flex:1;min-width:150px;'>
      <div style='font-weight:700;color:#fafafa;'>① Tải Dữ Liệu</div>
      <div style='font-size:0.82rem;color:#9db0c9;margin-top:2px;'>Chọn universe → Nhấn 🔄 Tải & Macro</div>
      <div style='margin-top:4px;font-size:0.9rem;'>⏳ Chưa hoàn thành</div>
    </div>
    <div style='flex:1;min-width:150px;opacity:0.5;'>
      <div style='font-weight:700;color:#fafafa;'>② Cập nhật Macro</div>
      <div style='font-size:0.82rem;color:#9db0c9;margin-top:2px;'>Nạp regime, VIX, foreign flow</div>
      <div style='margin-top:4px;font-size:0.9rem;'>○ Cần bước 1 trước</div>
    </div>
    <div style='flex:1;min-width:150px;opacity:0.3;'>
      <div style='font-weight:700;color:#fafafa;'>③ Review Signals</div>
      <div style='font-size:0.82rem;color:#9db0c9;margin-top:2px;'>Dùng scanner + macro để lọc mã</div>
      <div style='margin-top:4px;font-size:0.9rem;'>○ Cần bước 1+2</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

workflow_state = _workflow_state(
    data_dict,
    macro_data,
    st.session_state.get("macro_stale", []),
)

# ── Session Status Bar (replaces 4-metric row + trust ribbon + decision panel) ──
from core.regime import regime_label_vi, regime_emoji as _regime_emoji_fn
_mtm_prices = {
    t: float(df["Close"].iloc[-1])
    for t, (df, _) in data_dict.items()
    if df is not None and not df.empty
}
_ff_basis = _foreign_flow_basis_label(st.session_state.get("foreign_flows_cache", {}))
_calendar_basis = calendar_basis_summary(st.session_state.get("exchange_map", {}))
_stale = st.session_state.get("macro_stale", [])
_regime_stale = st.session_state.get("regime_stale", False)
_ff_meta = st.session_state.get("foreign_flow_meta", {})
_alert_count = len(_stale) + (1 if _regime_stale else 0) + (1 if _ff_meta.get("bounded_mode") else 0)

if regime_result:
    _regime_str = f"{_regime_emoji_fn(regime_result.regime)} {regime_label_vi(regime_result.regime)} {regime_result.probability:.0%}"
    _regime_stale_label = " ⚠️stale" if _regime_stale else ""
    _regime_display = f"{_regime_str}{_regime_stale_label}"
else:
    _regime_display = "—"

_status_items = [
    ("🏛️ Regime", _regime_display),
    ("📊 Macro", f"{macro_score:.1f}/10"),
    ("📦 Tickers", str(len(data_dict))),
    ("💼 Portfolio", f"{portfolio.market_value(_mtm_prices):,.0f} VND" if data_dict else "—"),
    ("📡 Price as-of", _latest_bar_date_label(data_dict)),
    ("🔗 Sources", _source_mix_label(data_dict) or "—"),
]
if _alert_count:
    _status_items.append(("⚠️ Alerts", f"{_alert_count} issue{'s' if _alert_count > 1 else ''}"))

_status_html_parts = "".join(
    f"<span style='margin-right:1.4rem;white-space:nowrap;'>"
    f"<span style='color:#7a8fa8;font-size:0.78rem;'>{lbl}&nbsp;</span>"
    f"<span style='color:#e8ecf4;font-size:0.85rem;font-weight:600;'>{val}</span>"
    f"</span>"
    for lbl, val in _status_items
)
st.markdown(
    f"<div style='background:#151b28;border:1px solid #232b3d;border-radius:10px;"
    f"padding:0.55rem 1rem;margin-bottom:0.6rem;display:flex;flex-wrap:wrap;align-items:center;'>"
    f"{_status_html_parts}</div>",
    unsafe_allow_html=True,
)

# Stale/alert callouts (below status bar, collapsed by default when no alerts)
if _stale or _regime_stale or _ff_meta.get("bounded_mode"):
    with st.expander(f"⚠️ {_alert_count} data alert{'s' if _alert_count > 1 else ''}", expanded=False):
        if _stale:
            render_guidance_callout(
                "Macro data partial",
                f"Thiếu: {', '.join(_stale)}. Nhấn 🔄 Tải & Macro để thử lại.",
                tone="warning",
            )
        if _regime_stale:
            _regime_msg = (
                "Không thể làm mới VNINDEX gần đây; app đang giữ regime trước đó và đánh dấu stale."
                if st.session_state.get("regime_result")
                else "Không thể làm mới VNINDEX; app tạm giữ regime mặc định sideways."
            )
            render_guidance_callout("VNI regime stale", _regime_msg, tone="warning")
        if _ff_meta.get("bounded_mode"):
            render_guidance_callout(
                "Foreign-flow coverage bounded",
                f"Universe lớn ({_ff_meta.get('requested_symbols', 0)} mã): "
                f"CafeF history {_ff_meta.get('full_history', 0)} | "
                f"KBS snapshot {_ff_meta.get('snapshot_proxy', 0)} | unavailable {_ff_meta.get('unavailable', 0)}.",
                tone="info",
            )

st.caption("Decision-support mode only. Review data freshness and source mix before acting on any signal.")
st.divider()

# ─────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────
# TWO-TIER NAVIGATION: Analysis | Management
# ─────────────────────────────────────────────────────────────
advanced_scanners = review_layout == "Advanced tabs"

from ui.scanner_tab import render_scanner_tab

if data_dict and _is_vni_regime_stale(st.session_state.get("vni_df"), max_age_days=1):
    with st.spinner("Đang làm mới VNI regime trước khi quét…"):
        _refresh_vni_regime(force=False, max_age_days=1)
    regime_result = st.session_state.get("regime_result")
    regime_label = regime_result.regime if regime_result else "sideways"

_exchange_map: dict[str, str] = {
    t: str(st.session_state.get("exchange_map", {}).get(t, TICKER_EXCHANGE.get(t, "HOSE"))).strip().upper() or "HOSE"
    for t in data_dict
}
_foreign_flows: dict = st.session_state.get("foreign_flows_cache", {})

# ── Tier 1: Analysis tabs ─────────────────────────────────────
_analysis_labels = ["🌐 Macro Pulse"]
if advanced_scanners:
    _analysis_labels += ["⚡ 1W", "📅 2W", "📆 1M", "📊 3M", "🎯 5M"]
else:
    _analysis_labels.append("🔎 Signal Review")
_analysis_labels += ["🧠 ML Forecast", "🧪 Backtest"]

_analysis_tabs = st.tabs(_analysis_labels)
_aidx = 0

# Macro Pulse
with _analysis_tabs[_aidx]:
    from ui.macro_tab import render_macro_tab
    if macro_data:
        if regime_result is None:
            from core.regime import RegimeResult
            regime_result = RegimeResult("sideways", 0.5, [], "rule", {})
        render_macro_tab(macro_data, regime_result, lang)
    else:
        st.info("Nhấn **🔄 Tải & Macro** để tải dữ liệu vĩ mô.")
_aidx += 1

# Signal Review / Advanced Scanners
if advanced_scanners:
    for _tf in ["1W", "2W", "1M", "3M", "5M"]:
        with _analysis_tabs[_aidx]:
            if not data_dict:
                st.info("Tải dữ liệu trước để quét tín hiệu.")
            else:
                render_scanner_tab(
                    tf=_tf,
                    data_dict=data_dict,
                    regime=regime_label,
                    macro_score=macro_score,
                    foreign_flows=_foreign_flows,
                    lang=lang,
                    exchange_map=_exchange_map,
                )
        _aidx += 1
else:
    with _analysis_tabs[_aidx]:
        st.subheader("🔎 Signal Review Workspace")
        if not data_dict:
            st.info("Tải dữ liệu trước để bắt đầu review tín hiệu.")
        else:
            _rc1, _rc2 = st.columns([3, 2])
            with _rc1:
                selected_tf = st.radio(
                    "Timeframe review",
                    ["1W", "2W", "1M", "3M", "5M"],
                    index=2,
                    horizontal=True,
                    format_func=lambda tf: TIMEFRAME_CONFIG[tf]["label"],
                    key="guided_review_tf",
                )
            with _rc2:
                st.metric(
                    "Review context",
                    f"{TIMEFRAME_CONFIG[selected_tf]['label']} | {regime_label}",
                    f"Macro {macro_score:.1f}/10",
                )
            st.caption(
                "Guided review mode. "
                f"Foreign-flow basis: {_foreign_flow_basis_label(_foreign_flows)}."
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
    _aidx += 1

# ML Forecast
with _analysis_tabs[_aidx]:
    from ui.ml_tab import render_ml_tab
    if not data_dict:
        st.info("Tải dữ liệu trước.")
    else:
        render_ml_tab(data_dict, regime_label, macro_data, lang, exchange_map=_exchange_map)
_aidx += 1

# Backtest
with _analysis_tabs[_aidx]:
    from ui.backtest_tab import render_backtest_tab
    if not data_dict:
        st.info("Tải dữ liệu trước.")
    else:
        render_backtest_tab(
            data_dict,
            lang,
            exchange_map=_exchange_map,
            vni_df=st.session_state.get("vni_df"),
        )

# ── Tier 2: Management tabs ───────────────────────────────────
st.markdown("<div style='margin-top:0.75rem'></div>", unsafe_allow_html=True)
_mgmt_tabs = st.tabs(["💼 Portfolio", "📜 Audit Log", "📖 Hướng Dẫn"])

with _mgmt_tabs[0]:
    from ui.portfolio_tab import render_portfolio_tab
    updated_pf = render_portfolio_tab(portfolio, data_dict, lang)
    st.session_state.portfolio = updated_pf

with _mgmt_tabs[1]:
    from ui.audit_tab import render_audit_tab
    render_audit_tab(lang)

with _mgmt_tabs[2]:
    from ui.guide_tab import render_guide_tab
    render_guide_tab(lang)
