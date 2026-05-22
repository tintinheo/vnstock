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
        if _due is not None and not _due.empty:
            _atc_badge = f" 🔴{len(_due)}"
    except Exception:
        pass

    # ── HÀNH ĐỘNG section ─────────────────────────────────────────────────
    st.caption("── HÀNH ĐỘNG ──")
    page = st.radio(
        "Navigation",
        options=[
            "🌅 Morning Briefing",
            f"⚡ ATC Alert{_atc_badge}",
            "📂 Danh mục & Hiệu suất",
            "🔍 Profiler",
            "📡 Scanner",
        ],
        key="nav",
    )
    st.caption("── PHÂN TÍCH ──")
    page_analysis = st.radio(
        "Analysis",
        options=[
            "🐳 Dòng tiền",
            "📊 Backtest",
        ],
        key="nav_analysis",
        label_visibility="collapsed",
    )
    st.caption("── HỆ THỐNG ──")
    page_system = st.radio(
        "System",
        options=[
            "🗂 Audit",
            "⚙️ Cài đặt",
        ],
        key="nav_system",
        label_visibility="collapsed",
    )

    # Merge: last-clicked group wins
    _all_pages = [page, page_analysis, page_system]
    _last_nav = st.session_state.get("_last_nav")
    # Detect which group changed relative to last render
    if "nav_last_action" not in st.session_state:
        st.session_state["nav_last_action"] = "nav"

    st.divider()
    st.caption("⚠️ Advisory only — không phải khuyến nghị đầu tư.")
    st.caption("[H1] Hệ thống không đặt lệnh tự động.")
    st.caption("v1.2 Alpha")

# ── Determine active page (track which radio last changed) ────────────────────
# We store the previous values to detect which group the user just clicked
_prev_main     = st.session_state.get("_prev_nav",     "🌅 Morning Briefing")
_prev_analysis = st.session_state.get("_prev_analysis","🐳 Dòng tiền")
_prev_system   = st.session_state.get("_prev_system",  "🗂 Audit")

if page != _prev_main:
    active_page = page
    st.session_state["_prev_nav"]      = page
elif page_analysis != _prev_analysis:
    active_page = page_analysis
    st.session_state["_prev_analysis"] = page_analysis
elif page_system != _prev_system:
    active_page = page_system
    st.session_state["_prev_system"]   = page_system
else:
    # No change — use the stored active page (default Morning Briefing)
    active_page = st.session_state.get("_active_page", "🌅 Morning Briefing")

st.session_state["_active_page"] = active_page

# Normalise ATC badge variant
_active_norm = active_page.replace(_atc_badge, "") if _atc_badge else active_page

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
    morning_briefing.render()

