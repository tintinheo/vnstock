"""
ui/backtest_tab.py — NewTradingOS v14.0
Backtest tab UI.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import TIMEFRAME_CONFIG, INITIAL_CAPITAL
from backtest.engine import run_multi_tf_backtest, summarise_results, trades_to_df
from ui.components import equity_chart, GREEN, RED, YELLOW


def render_backtest_tab(
    data_dict: dict,
    lang: str = "VI",
) -> None:
    st.subheader("🧪 Backtest Engine — T+2 Realistic (VN)")

    c1, c2, c3 = st.columns(3)
    with c1:
        ticker = st.selectbox("Chọn mã", sorted(data_dict.keys()),
                               key="bt_ticker")
    with c2:
        capital = st.number_input("Vốn ban đầu (VND)",
                                   min_value=10_000_000,
                                   max_value=10_000_000_000,
                                   value=INITIAL_CAPITAL,
                                   step=10_000_000,
                                   key="bt_capital")
    with c3:
        run_all_tf = st.toggle("Chạy tất cả TF", value=True, key="bt_all_tf")

    if st.button("⚡ Chạy Backtest", type="primary", key="bt_run"):
        df_raw, src = data_dict.get(ticker, (None, "N/A"))
        if df_raw is None or df_raw.empty:
            st.error(f"Không có dữ liệu cho {ticker}")
            return

        with st.spinner("Đang chạy backtest…"):
            results = run_multi_tf_backtest(df_raw, ticker=ticker,
                                             initial_capital=capital)

        # ── Summary table ─────────────────────────────────────
        st.subheader(f"📊 Kết quả — {ticker} | {src}")
        summary_df = summarise_results(results)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        # ── Per-TF equity curves ──────────────────────────────
        st.subheader("📈 Equity Curves")
        tf_tabs = st.tabs(list(results.keys()))
        for tab, (tf, res) in zip(tf_tabs, results.items()):
            with tab:
                m = res.metrics
                if "error" in m:
                    st.warning(f"Error: {m['error']}")
                    continue

                c_a, c_b, c_c, c_d = st.columns(4)
                c_a.metric("CAGR",     f"{m.get('cagr', 0):.1f}%")
                c_b.metric("Sharpe",   f"{m.get('sharpe', 0):.2f}")
                c_c.metric("Max DD",   f"{m.get('max_dd', 0):.1f}%")
                c_d.metric("Win Rate", f"{m.get('win_rate', 0):.1f}%")

                fig = equity_chart(
                    res.equity_curve, capital,
                    title=f"{ticker} — {tf} | {len(res.trades)} trades",
                )
                st.plotly_chart(fig, use_container_width=True)

                # Trade log
                if res.trades:
                    t_df = trades_to_df(res)
                    st.dataframe(t_df, use_container_width=True, hide_index=True)

                    # Exit reason distribution
                    reasons = pd.Series([t.exit_reason for t in res.trades])
                    reason_counts = reasons.value_counts()
                    fig_r = go.Figure(go.Pie(
                        labels=reason_counts.index,
                        values=reason_counts.values,
                        hole=0.4,
                        marker_colors=[GREEN, YELLOW, RED, "#888"],
                    ))
                    fig_r.update_layout(
                        height=250, template="plotly_dark",
                        paper_bgcolor="#0e1117",
                        margin=dict(l=0, r=0, t=30, b=0),
                        title="Exit Reasons",
                    )
                    st.plotly_chart(fig_r, use_container_width=True)
