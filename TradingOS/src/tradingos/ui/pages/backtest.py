"""Backtest page — mode A/B/W comparison + walk-forward."""
from __future__ import annotations

import streamlit as st

from tradingos.engines.backtest_service import BacktestService
from tradingos.data.schemas import BacktestRequest
from tradingos.ui.components.equity_curve import render_equity_curve, render_backtest_summary


def render() -> None:
    st.title("📊 Backtest")
    st.caption("So sánh Mode A / B / W — VN constraints (T+3, LOCK_SAN=5% synthetic).")

    with st.form("bt_form"):
        col1, col2, col3 = st.columns(3)
        ticker = col1.text_input("Mã chứng khoán", value="VCB").upper()
        start = col2.text_input("Từ ngày (YYYY-MM-DD)", value="2022-01-01")
        end = col3.text_input("Đến ngày (YYYY-MM-DD)", value="2024-12-31")
        col1b, col2b, col3b = st.columns(3)
        sl_pct = col1b.number_input("SL %", value=6.0, min_value=1.0, max_value=20.0, step=0.5) / 100
        tp1_mult = col2b.number_input("TP1 = SL ×", value=1.5, min_value=1.0, max_value=5.0, step=0.1)
        tp2_mult = col3b.number_input("TP2 = SL ×", value=2.5, min_value=1.5, max_value=8.0, step=0.1)
        submitted = st.form_submit_button("▶️ Chạy Backtest", use_container_width=True)

    if submitted and ticker:
        svc = BacktestService()
        request = BacktestRequest(
            ticker=ticker,
            start_date=start,
            end_date=end,
            sl_pct=sl_pct,
            tp1_mult=tp1_mult,
            tp2_mult=tp2_mult,
        )

        with st.spinner(f"Đang backtest {ticker}..."):
            results = svc.run(request)

        if not results:
            st.error("Không đủ dữ liệu để backtest.")
            return

        st.subheader("📈 Equity Curve")
        render_equity_curve(results)

        st.subheader("📋 Tổng kết")
        render_backtest_summary(results)

        # Walk-forward windows
        for mode, bt in results.items():
            if bt.walk_forward_windows:
                with st.expander(f"Walk-Forward Windows — {mode}"):
                    import pandas as pd
                    st.dataframe(pd.DataFrame(bt.walk_forward_windows), use_container_width=True, hide_index=True)

        # Trade list
        best_mode = max(results, key=lambda m: results[m].total_return)
        bt = results[best_mode]
        if bt.trades:
            with st.expander(f"📜 Trade list — {best_mode} ({len(bt.trades)} lệnh)"):
                import pandas as pd
                rows = [vars(t) for t in bt.trades[:50]]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.caption(
            "⚠️ [SYNTHETIC] LOCK_SAN=5% là tham số giả định. Kết quả backtest chỉ mang tính tham khảo."
        )
