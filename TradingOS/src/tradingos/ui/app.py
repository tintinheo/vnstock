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

    page = st.radio(
        "Navigation",
        options=["🔍 Profiler", "📡 Scanner", "🏆 Performance", "🐳 Dòng tiền", "📊 Backtest", "🗂 Audit", "⚙️ Cài đặt"],
        key="nav",
    )

    st.divider()
    st.caption("⚠️ Advisory only — không phải khuyến nghị đầu tư.")
    st.caption("[H1] Hệ thống không đặt lệnh tự động.")
    st.caption("v1.1 Alpha")

# ── Route to pages ────────────────────────────────────────────────────────────
from tradingos.ui.pages import profiler, scanner, money_flow, backtest, audit, settings, performance

if page == "🔍 Profiler":
    profiler.render()
elif page == "📡 Scanner":
    scanner.render()
elif page == "🏆 Performance":
    performance.render()
elif page == "🐳 Dòng tiền":
    money_flow.render()
elif page == "📊 Backtest":
    backtest.render()
elif page == "🗂 Audit":
    audit.render()
elif page == "⚙️ Cài đặt":
    settings.render()
