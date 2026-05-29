"""TradingOS Alpha — Streamlit entry point.

Run: streamlit run src/tradingos/ui/app.py
"""
import sys
from pathlib import Path

# Ensure src/ is on PYTHONPATH when running via streamlit
# __file__ = .../TradingOS/src/tradingos/ui/app.py
# parents[2] = .../TradingOS/src
_src = Path(__file__).resolve().parents[2]
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TradingOS Alpha",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark theme CSS ────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] { background-color: #0f0f1a; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #12122a; }
    .metric-label { color: #aaa !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/48/bull--v2.png", width=48)
    st.title("TradingOS α")
    st.caption("VN Market Intelligence")
    st.divider()

    # Resolve pending navigation (set by other pages via _nav_pending)
    # Must happen BEFORE the radio widget is instantiated, so the write is valid.
    if "_nav_pending" in st.session_state:
        st.session_state["nav"] = st.session_state.pop("_nav_pending")

    # ── Check if positions are due today (ATC badge) ──────────────────────
    _atc_badge = ""
    try:
        from tradingos.engines.portfolio_tracker import portfolio_tracker as _tracker
        _due = _tracker.get_positions_due_today()
        if _due:  # returns list[dict], not DataFrame
            _atc_badge = f" 🔴{len(_due)}"
    except Exception:
        pass

    # ── Single radio with all pages (section labels shown via st.caption) ──
    st.caption("── HÀNH ĐỘNG ──")
    _VALID_PAGES = {
        "🌅 Morning Briefing",
        f"⚡ ATC Alert{_atc_badge}",
        "📂 Danh mục & Hiệu suất",
        "🔍 Profiler",
        "📡 Scanner",
        "🐳 Dòng tiền",
        "📊 Backtest",
        "🗂 Audit",
        "⚙️ Cài đặt",
    }
    _all_options = [
        "🌅 Morning Briefing",
        f"⚡ ATC Alert{_atc_badge}",
        "📂 Danh mục & Hiệu suất",
        "🔍 Profiler",
        "📡 Scanner",
        "── PHÂN TÍCH ──",
        "🐳 Dòng tiền",
        "📊 Backtest",
        "── HỆ THỐNG ──",
        "🗂 Audit",
        "⚙️ Cài đặt",
    ]
    page = st.radio(
        "Navigation",
        options=_all_options,
        key="nav",
        label_visibility="collapsed",
    )

    # ── Quick ticker search ───────────────────────────────────────────────
    st.divider()
    st.caption("🔍 Tra cứu nhanh")
    _qs_col1, _qs_col2 = st.columns([3, 1])
    _quick_t = _qs_col1.text_input(
        "ticker_search",
        placeholder="VCB, FPT...",
        label_visibility="collapsed",
        key="sidebar_quick_ticker",
    ).strip().upper()
    if _qs_col2.button("→", key="sidebar_quick_go", use_container_width=True):
        if _quick_t:
            st.session_state["profiler_ticker"] = _quick_t
            st.session_state["_nav_pending"] = "🔍 Profiler"
            st.rerun()

    st.divider()
    st.caption("⚠️ Advisory only — không phải khuyến nghị đầu tư.")
    st.caption("[H1] Hệ thống không đặt lệnh tự động.")
    st.caption("v1.2 Alpha")

# ── Normalise page (strip ATC badge suffix) ───────────────────────────────────
_active_norm = page.replace(_atc_badge, "") if _atc_badge else page

# Track last valid page so separator-click can revert gracefully
if _active_norm in _VALID_PAGES or _active_norm.replace(_atc_badge, "") in _VALID_PAGES:
    st.session_state["_last_valid_nav"] = _active_norm


# ── Route to pages ────────────────────────────────────────────────────────────
from tradingos.ui.pages import (  # noqa: E402
    profiler, scanner, money_flow, backtest, audit, settings, performance,
    morning_briefing, atc_alert,
)

if _active_norm == "🌅 Morning Briefing":
    morning_briefing.render()
elif "⚡ ATC Alert" in _active_norm:
    atc_alert.render()
elif _active_norm == "📂 Danh mục & Hiệu suất":
    performance.render()
elif _active_norm == "🔍 Profiler":
    profiler.render()
elif _active_norm == "📡 Scanner":
    scanner.render()
elif _active_norm == "🐳 Dòng tiền":
    money_flow.render()
elif _active_norm == "📊 Backtest":
    backtest.render()
elif _active_norm == "🗂 Audit":
    audit.render()
elif _active_norm == "⚙️ Cài đặt":
    settings.render()
else:
    # Section separator was accidentally clicked — revert nav to last valid page
    _revert_to = st.session_state.get("_last_valid_nav", "🌅 Morning Briefing")
    if st.session_state.get("nav") != _revert_to:
        st.session_state["nav"] = _revert_to
        st.rerun()
    # Fallback: re-render Morning Briefing if revert target is also invalid
    morning_briefing.render()

