"""Audit timeline component — event log visualization."""
from __future__ import annotations

import pandas as pd
import streamlit as st


def render_audit_timeline(df: pd.DataFrame) -> None:
    """Render audit log DataFrame as styled timeline."""
    if df.empty:
        st.info("Không có sự kiện audit.")
        return

    _action_icon = {
        "STRONG_BUY": "📈",
        "BUY": "🟢",
        "WATCH": "👀",
        "NO_ACTION": "⏸",
        "EXIT": "🔴",
        "FORCED_EXIT": "⚠️",
        "SCAN": "🔍",
        "BACKTEST": "📊",
        "PROFILE": "👤",
    }

    for _, row in df.iterrows():
        action = str(row.get("action", ""))
        icon = _action_icon.get(action, "📋")
        ts = str(row.get("ts", row.get("timestamp", "")))[:16]
        ticker = str(row.get("ticker", ""))
        score = row.get("mfpm_score", "")
        conf = row.get("confidence", "")

        st.markdown(
            f"`{ts}` &nbsp; {icon} **{ticker}** — {action} "
            f"{'· score=' + str(score) if score else ''} "
            f"{'· ' + str(conf) if conf and conf != '—' else ''}"
        )


def render_audit_stats(stats: dict) -> None:
    """Render audit summary stats."""
    col1, col2 = st.columns(2)
    col1.metric("Tổng sự kiện", stats.get("total_events", 0))
    col2.metric("Tickers đã profile", stats.get("tickers_profiled", 0))

    breakdown = stats.get("action_breakdown", {})
    if breakdown:
        st.markdown("**Phân bổ tín hiệu:**")
        df = pd.DataFrame(
            list(breakdown.items()), columns=["Action", "Count"]
        ).sort_values("Count", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
