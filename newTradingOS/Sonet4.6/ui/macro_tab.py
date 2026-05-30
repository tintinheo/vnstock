"""
ui/macro_tab.py — NewTradingOS v14.0
Macro Pulse dashboard tab.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import TIMEFRAME_CONFIG, WORLD_IMPACT_VI, WORLD_IMPACT_EN
from core.regime import regime_label_vi
from ui.components import GREEN, RED, YELLOW, GREY, world_sparkline


def render_macro_tab(
    macro_data: dict,
    regime_result,          # RegimeResult
    lang: str = "VI",
) -> None:
    """
    Render Macro Pulse tab:
    - VN Market Regime
    - World markets table with sparklines
    - Foreign flow
    - Market breadth
    - TF condition scorecard
    """
    st.subheader("🌐 Macro Pulse — Điều Kiện Vĩ Mô Thị Trường")

    world        = macro_data.get("world", {})
    breadth      = macro_data.get("breadth", {})
    ff           = macro_data.get("foreign_flow", {})
    ad_ratio     = macro_data.get("ad_ratio", 0.5)
    dxy_trend    = macro_data.get("dxy_trend", "neutral")
    vix_level    = macro_data.get("vix_level", "normal")

    # ── Row 1: Key metrics ────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        regime_str = regime_label_vi(regime_result.regime) if lang == "VI" else regime_result.regime.title()
        color  = {"bull": GREEN, "bear": RED, "sideways": YELLOW}.get(regime_result.regime, GREY)
        emoji  = {"bull": "🟢", "bear": "🔴", "sideways": "🟡"}.get(regime_result.regime, "⚪")
        st.metric("Market Regime", f"{emoji} {regime_str}",
                  f"Prob: {regime_result.probability:.0%} | {regime_result.method.upper()}")

    dxy_info = world.get("DXY (USD Index)")
    with c2:
        if dxy_info:
            delta = f"{dxy_info['pct_5d']:+.2f}% (5d)"
            st.metric("DXY", f"{dxy_info['current']:.2f}", delta)
        else:
            st.metric("DXY", "N/A")

    vix_info = world.get("VIX")
    with c3:
        if vix_info:
            vix_emoji = "😨" if vix_level == "fear" else "⚠️" if vix_level == "elevated" else "😊"
            st.metric("VIX", f"{vix_emoji} {vix_info['current']:.1f}",
                      f"{vix_info['pct_1d']:+.2f}% (1d)")
        else:
            st.metric("VIX", "N/A")

    with c4:
        ff_net = ff.get("net_buy", 0) / 1e9
        ff_color = GREEN if ff_net > 0 else RED
        st.metric("Foreign Flow", f"{ff_net:+.1f} tỷ", ff.get("trend", "N/A"))

    with c5:
        adv   = breadth.get("advance", 0)
        dec   = breadth.get("decline", 0)
        total = adv + dec
        ad_str = f"{adv}/{dec}" if total > 0 else "N/A"
        breadth_label = "Tốt" if ad_ratio > 0.55 else "Xấu" if ad_ratio < 0.45 else "Trung bình"
        st.metric("A/D Ratio", ad_str, breadth_label)

    st.divider()

    # ── World Markets Table ───────────────────────────────────
    st.subheader("🌍 Thị Trường Thế Giới")
    impact_map = WORLD_IMPACT_VI if lang == "VI" else WORLD_IMPACT_EN

    rows = []
    for name, info in world.items():
        if info is None:
            rows.append({"Chỉ số": name, "Giá": "N/A", "1D%": "-",
                          "5D%": "-", "20D%": "-", "Tác động": impact_map.get(name, "")})
            continue
        c1d   = info["pct_1d"]
        c5d   = info["pct_5d"]
        c20d  = info["pct_20d"]
        rows.append({
            "Chỉ số": name,
            "Giá":    f"{info['current']:.2f}",
            "1D%":    f"{c1d:+.2f}%",
            "5D%":    f"{c5d:+.2f}%",
            "20D%":   f"{c20d:+.2f}%",
            "Tác động": impact_map.get(name, ""),
        })
    df_w = pd.DataFrame(rows)
    st.dataframe(df_w, width="stretch", hide_index=True)  # noqa: deprecated-arg

    st.divider()

    # ── TF Condition Scorecard ────────────────────────────────
    st.subheader("📋 Điều Kiện Vào Lệnh Theo Timeframe")

    dxy_ok = dxy_trend not in ("strong_up",)
    vix_ok = vix_level == "normal"
    ff_ok  = ff.get("net_buy", 0) > -1e10

    rows_tf = []
    for tf in TIMEFRAME_CONFIG:
        cfg       = TIMEFRAME_CONFIG[tf]
        label     = cfg["label"] if lang == "VI" else cfg["label_en"]
        reg_ok    = regime_result.regime in cfg["regime_filter"]
        overall   = "✅ Thuận lợi" if (reg_ok and dxy_ok and vix_ok) else \
                    "⚠️ Thận trọng" if (reg_ok and (dxy_ok or vix_ok)) else \
                    "🚫 Rủi ro cao"
        rows_tf.append({
            "Timeframe": label,
            "Regime":    "✅" if reg_ok else "❌",
            "DXY":       "✅" if dxy_ok else "⚠️",
            "VIX":       "✅" if vix_ok else "⚠️",
            "Foreign":   "✅" if ff_ok  else "⚠️",
            "Tổng thể":  overall,
            "Max Pos":   cfg["max_positions"],
            "R/R":       f"1:{cfg['target_rr']}",
        })

    df_tf = pd.DataFrame(rows_tf)
    st.dataframe(df_tf, width="stretch", hide_index=True)  # noqa: deprecated-arg

    # ── Regime History Chart ──────────────────────────────────
    if regime_result.history and len(regime_result.history) > 20:
        st.divider()
        st.subheader("📈 Lịch Sử Chế Độ Thị Trường")
        h = regime_result.history[-120:]
        state_map = {"bull": 1, "sideways": 0, "bear": -1}
        state_vals = [state_map.get(s, 0) for s in h]
        colors = [GREEN if v == 1 else RED if v == -1 else YELLOW for v in state_vals]

        fig = go.Figure(go.Bar(
            x=list(range(len(h))), y=state_vals,
            marker_color=colors, opacity=0.7,
        ))
        fig.update_layout(
            height=150, template="plotly_dark",
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            yaxis=dict(tickvals=[-1, 0, 1],
                       ticktext=["Bear", "Sideways", "Bull"]),
            xaxis=dict(visible=False),
            margin=dict(l=40, r=10, t=20, b=20),
            showlegend=False,
        )
        st.plotly_chart(fig, width="stretch")  # noqa: deprecated-arg
