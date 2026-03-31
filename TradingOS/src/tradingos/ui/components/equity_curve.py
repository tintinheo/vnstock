"""Equity curve component — backtest P&L visualization."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from tradingos.core.backtest import BacktestResult


_MODE_COLORS = {
    "MODE_A": "#33b5e5",
    "MODE_B": "#ffbb33",
    "MODE_W": "#00c851",
}


def render_equity_curve(results: dict[str, BacktestResult]) -> None:
    """Render overlaid equity curves for backtest mode comparison."""
    fig = go.Figure()

    for mode, bt in results.items():
        if not bt.trades:
            continue
        pnls = [t.pnl_pct for t in bt.trades]
        equity = np.cumprod(1 + np.array(pnls))
        x = list(range(len(equity)))
        color = _MODE_COLORS.get(mode, "#aaa")

        fig.add_trace(go.Scatter(
            x=x,
            y=(equity - 1) * 100,
            mode="lines",
            name=f"{mode} (W={bt.win_rate:.0%}, Sharpe={bt.sharpe:.2f})",
            line=dict(color=color, width=2),
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

    fig.update_layout(
        title="Equity Curve — Mode Comparison",
        xaxis_title="Trade #",
        yaxis_title="Cumulative Return (%)",
        height=360,
        margin=dict(t=50, b=40, l=50, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        yaxis=dict(gridcolor="#333", ticksuffix="%"),
        xaxis=dict(showgrid=False),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_backtest_summary(results: dict[str, BacktestResult]) -> None:
    """Render summary metrics table for all modes."""
    import pandas as pd
    rows = []
    for mode, bt in results.items():
        rows.append({
            "Mode": mode,
            "Số lệnh": bt.n_trades,
            "Win rate": f"{bt.win_rate:.0%}",
            "Avg PnL": f"{bt.avg_pnl_pct:+.1%}",
            "Total return": f"{bt.total_return:+.1%}",
            "Max DD": f"{bt.max_drawdown:.1%}",
            "Sharpe": f"{bt.sharpe:.2f}",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
