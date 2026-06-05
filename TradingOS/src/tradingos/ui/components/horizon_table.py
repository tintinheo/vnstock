"""Horizon table component — render multi-horizon recommendations."""
from __future__ import annotations

import pandas as pd
import streamlit as st


def render_horizon_table(horizons: list[dict]) -> None:
    """Render horizon recommendation table from TickerProfile.horizons."""
    if not horizons:
        st.info("Không có dữ liệu horizon.")
        return

    rows = []
    for h in horizons:
        rows.append({
            "Kỳ hạn": h.get("period_label", f"T+{h.get('horizon_days')}"),
            "Action": h.get("action", "—"),
            "Confidence": h.get("confidence", "—"),
            "Vào lệnh": f"{h.get('entry_price', 0):,.0f}",
            "Cắt lỗ": f"{h.get('stop_loss', 0):,.0f} (-{h.get('sl_pct', 0):.1%})",
            "TP1": f"{h.get('tp1', 0):,.0f}",
            "TP2": f"{h.get('tp2', 0):,.0f}",
            "R:R": f"1:{h.get('rr_ratio', 0):.1f}",
            "Cửa sổ vào": h.get("entry_window", "—"),
        })

    df = pd.DataFrame(rows)

    def _color_action(val: str) -> str:
        colors = {
            "STRONG_BUY": "background-color: #00c851; color: white",
            "BUY": "background-color: #33b5e5; color: white",
            "WATCH": "background-color: #ffbb33; color: black",
            "NO_ACTION": "background-color: #aaa; color: white",
        }
        return colors.get(val, "")

    styled = df.style.map(_color_action, subset=["Action"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
