"""Settings page — config review + watchlist management."""
from __future__ import annotations

import streamlit as st

from tradingos.utils.config import cfg
from tradingos.data.cache import cache


def render() -> None:
    st.title("⚙️ Cài đặt")

    tab1, tab2, tab3 = st.tabs(["📋 Config", "📌 Watchlist", "🗄 Database"])

    # ── Tab 1: Config viewer ──────────────────────────────────────────────
    with tab1:
        st.subheader("strategy.yaml snapshot")
        strategy = cfg.strategy()
        if isinstance(strategy, dict):
            for section, values in strategy.items():
                with st.expander(f"[{section}]"):
                    st.json(values)
        else:
            st.code(str(strategy))

        st.subheader("default.toml")
        st.markdown(f"- DB Path: `{cfg.db_path}`")
        st.markdown(f"- Log level: `{cfg.get('logging', 'level', default='INFO')}`")

    # ── Tab 2: Watchlist manager ──────────────────────────────────────────
    with tab2:
        current = cache.get_watchlist()
        st.markdown(f"**Watchlist hiện tại ({len(current)} mã):**")
        st.write(", ".join(current) if current else "_Chưa có mã nào._")

        with st.form("add_watchlist"):
            new_ticker = st.text_input("Thêm mã:", max_chars=10).upper()
            add = st.form_submit_button("➕ Thêm")
            if add and new_ticker:
                cache.add_to_watchlist(new_ticker)
                st.success(f"Đã thêm {new_ticker}")
                st.rerun()

    # ── Tab 3: DB info ────────────────────────────────────────────────────
    with tab3:
        st.markdown(f"**DuckDB path:** `{cfg.db_path}`")
        try:
            import duckdb
            con = duckdb.connect(str(cfg.db_path), read_only=True)
            tables = con.execute("SHOW TABLES").fetchall()
            con.close()
            st.markdown("**Tables:**")
            for (t,) in tables:
                st.markdown(f"- `{t}`")
        except Exception as e:
            st.error(f"DB error: {e}")
