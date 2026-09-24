import streamlit as st

st.set_page_config(page_title="TradingOS Alpha", layout="wide", page_icon="📈")

st.sidebar.title("TradingOS Alpha v1.0")
st.sidebar.markdown("**Status:** HMM: `STEADY_BULL` | Ω: `0.55`")

pages = {
    "Analytics": [
        st.Page("pages/scanner.py", title="Market Scanner", icon="📡"),
        st.Page("pages/profiler.py", title="Stock Profiler", icon="🔍"),
        st.Page("pages/money_flow.py", title="Large Money Flow", icon="🐋"),
    ],
    "System": [
        st.Page("pages/backtest.py", title="Backtesting", icon="🧪"),
        st.Page("pages/audit.py", title="Audit Trail", icon="📜"),
        st.Page("pages/settings.py", title="Settings", icon="⚙️"),
    ]
}

pg = st.navigation(pages)
pg.run()
