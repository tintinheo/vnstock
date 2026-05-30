"""
ui/portfolio_tab.py — NewTradingOS v14.0
Portfolio tracker tab UI.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from config import INITIAL_CAPITAL
from portfolio.tracker import Portfolio, Position
from portfolio.sizing import (
    kelly_fraction, position_size_vnd,
    allocate_budget, compute_portfolio_metrics,
)
from ui.components import GREEN, RED, YELLOW, equity_chart


def render_portfolio_tab(
    portfolio: Portfolio,
    data_dict: dict,
    lang: str = "VI",
) -> Portfolio:
    """
    Render portfolio management tab.
    Returns potentially updated Portfolio.
    """
    st.subheader("💼 Portfolio Tracker")

    # ── Summary metrics ───────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng Vốn",     f"{portfolio.capital:,.0f} VND")
    c2.metric("Tiền mặt",     f"{portfolio.cash:,.0f} VND")
    c3.metric("Lãi thực hiện",f"{portfolio.realised_pnl:,.0f} VND",
              delta=f"{portfolio.realised_pnl / portfolio.capital * 100:+.2f}%" if portfolio.capital else "")
    c4.metric("# Vị thế mở",  len(portfolio.open_positions))

    st.divider()

    # ── Open Positions ────────────────────────────────────────
    st.subheader("📂 Vị Thế Đang Mở")
    if portfolio.open_positions:
        # Mark-to-market: lấy giá hiện tại từ data_dict để tính MTM
        _prices = {
            t: float(df["Close"].iloc[-1])
            for t, (df, _) in data_dict.items()
            if df is not None and not df.empty
        }
        _unreal = portfolio.unrealized_pnl(_prices)
        _mtm    = portfolio.market_value(_prices)
        _unreal_pct = (_unreal / (_mtm - _unreal) * 100) if (_mtm - _unreal) > 0 else 0.0

        cm1, cm2 = st.columns(2)
        cm1.metric(
            "💰 Giá trị thị trường (MTM)",
            f"{_mtm:,.0f} VND",
            delta=f"Đầu tư: {(_mtm - portfolio.cash):,.0f} VND",
        )
        cm2.metric(
            "📈 Lãi/Lỗ chưa thực hiện",
            f"{_unreal:+,.0f} VND",
            delta=f"{_unreal_pct:+.2f}%",
        )

        # Break-even trailing stop tự động khi lãi ≥ 15%
        _updated_stops = portfolio.update_stops(_prices)
        if _updated_stops:
            portfolio.save()
            st.info(
                f"🔒 Break-even stop tự động nâng lên giá vào: **{', '.join(_updated_stops)}**\n\n"
                "Stop đã được nâng lên mức hoà vốn để bảo toàn lợi nhuận (lãi ≥ 15%)."
            )

        pos_df = portfolio.positions_df()
        st.dataframe(pos_df, width="stretch", hide_index=True)

        # Quick close
        close_options = {
            f"{p.ticker} | {p.timeframe} | {p.entry_date}": p
            for p in portfolio.open_positions
        }
        col_close1, col_close2, col_close3 = st.columns(3)
        with col_close1:
            close_label = st.selectbox(
                "Đóng vị thế",
                list(close_options.keys()),
                key="close_ticker",
            )
        with col_close2:
            close_reason = st.selectbox(
                "Lý do", ["signal", "stop", "target", "manual"],
                key="close_reason",
            )
        with col_close3:
            if st.button("🔴 Đóng lệnh", key="btn_close"):
                selected_pos = close_options[close_label]
                # Get current price
                df_t, _ = data_dict.get(selected_pos.ticker, (None, None))
                if df_t is not None and not df_t.empty:
                    cur_price = float(df_t["Close"].iloc[-1])
                    from datetime import date
                    pos = portfolio.close_position(
                        selected_pos.ticker,
                        cur_price,
                        str(date.today()),
                        close_reason,
                        timeframe=selected_pos.timeframe,
                        entry_date=selected_pos.entry_date,
                    )
                    if pos:
                        portfolio.save()
                        pnl_pct = (pos.pnl_pct or 0) * 100
                        if pnl_pct >= 0:
                            st.success(f"✅ Đóng {selected_pos.ticker} +{pnl_pct:.2f}%")
                        else:
                            st.error(f"❌ Đóng {selected_pos.ticker} {pnl_pct:.2f}%")
    else:
        st.info("Chưa có vị thế mở.")

    st.divider()

    # ── Position Sizer ────────────────────────────────────────
    st.subheader("📐 Position Sizer (Kelly Criterion)")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        wr   = st.number_input("Win Rate (%)", 0.0, 100.0, 55.0, key="ks_wr") / 100
    with c2:
        avgw = st.number_input("Avg Win (%)", 0.1, 50.0, 8.0, key="ks_aw") / 100
    with c3:
        avgl = st.number_input("Avg Loss (%)", 0.1, 30.0, 4.0, key="ks_al") / 100
    with c4:
        price_in = st.number_input("Giá vào", 1000.0, 500000.0, 50000.0,
                                    step=500.0, key="ks_price")

    kf  = kelly_fraction(wr, avgw, avgl)
    ns, vnd = position_size_vnd(portfolio.cash, kf, price_in)

    st.info(
        f"**Kelly fraction:** {kf*100:.1f}%  |  "
        f"**Số cổ phiếu:** {ns:,}  |  "
        f"**Giá trị:** {vnd:,.0f} VND"
    )

    st.divider()

    # ── Trade History ─────────────────────────────────────────
    st.subheader("📋 Lịch Sử Giao Dịch")
    if portfolio.trades:
        t_df = portfolio.trades_df()
        st.dataframe(t_df, width="stretch", hide_index=True)

        pnls = [(t.pnl_pct or 0) for t in portfolio.trades]
        # Equity curve đúng: cộng pnl_vnd thực từng trade theo thứ tự thời gian.
        # Cách cũ dùng pnl_pct trên 100% vốn là sai (mỗi position chỉ dùng 10-25% vốn).
        _sorted_trades  = sorted(portfolio.trades, key=lambda t: t.exit_date or "")
        _total_pnl_vnd  = sum(t.pnl_vnd or 0 for t in _sorted_trades)
        _start_capital  = max(portfolio.capital - _total_pnl_vnd, 0.0)
        capital_curve   = [_start_capital]
        _running        = _start_capital
        for _t in _sorted_trades:
            _running += (_t.pnl_vnd or 0)
            capital_curve.append(max(_running, 0.0))
        if len(capital_curve) > 2:
            fig = equity_chart(capital_curve, INITIAL_CAPITAL,
                               title="Historical P&L Curve")
            st.plotly_chart(fig, width="stretch")

        metrics = compute_portfolio_metrics(
            capital_curve, [{"pnl_pct": p} for p in pnls]
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Win Rate", f"{metrics.get('win_rate', 0):.1f}%")
        c2.metric("Sharpe",   f"{metrics.get('sharpe', 0):.2f}")
        c3.metric("Max DD",   f"{metrics.get('max_dd', 0):.1f}%")
        c4.metric("P/F",      f"{metrics.get('profit_factor', 0):.2f}")
    else:
        st.info("Chưa có giao dịch nào được ghi nhận.")

    return portfolio
