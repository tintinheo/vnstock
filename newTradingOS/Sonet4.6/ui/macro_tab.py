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


def _world_as_of(info: dict | None) -> str:
    if not info:
        return "—"
    timestamps = info.get("timestamps") or []
    if not timestamps:
        return "—"
    try:
        return pd.to_datetime(timestamps[-1], unit="s").date().isoformat()
    except Exception:
        return "—"


def _latest_world_as_of(world: dict) -> str:
    dates = [_world_as_of(info) for info in world.values() if info]
    dates = [d for d in dates if d != "—"]
    return max(dates) if dates else "—"


def _status_icon(value: bool | None) -> str:
    if value is True:
        return "✅"
    if value is False:
        return "⚠️"
    return "—"


def _macro_component_states(macro_data: dict) -> dict[str, bool | None]:
    stale_fields = set(macro_data.get("stale_fields", []))
    ff = macro_data.get("foreign_flow", {})
    dxy_trend = macro_data.get("dxy_trend", "neutral")
    vix_level = macro_data.get("vix_level", "normal")

    return {
        "dxy": None if "DXY (USD Index)" in stale_fields else dxy_trend not in ("strong_up",),
        "vix": None if "VIX" in stale_fields else vix_level == "normal",
        "foreign": None if "foreign_flow" in stale_fields else ff.get("net_buy", 0) > -1e10,
        "breadth": None if "market_breadth" in stale_fields else True,
    }


def _overall_tf_condition(
    regime_ok: bool,
    dxy_ok: bool | None,
    vix_ok: bool | None,
    foreign_ok: bool | None,
) -> str:
    if not regime_ok:
        return "🚫 Rủi ro cao"
    if any(value is None for value in (dxy_ok, vix_ok, foreign_ok)):
        return "⚪ Thiếu dữ liệu"

    positive_count = sum(1 for value in (dxy_ok, vix_ok, foreign_ok) if value)
    if positive_count == 3:
        return "✅ Thuận lợi"
    if positive_count >= 1:
        return "⚠️ Thận trọng"
    return "🚫 Rủi ro cao"


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
    stale_fields = macro_data.get("stale_fields", [])
    component_states = _macro_component_states(macro_data)

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
        if component_states["foreign"] is None:
            st.metric("Foreign Flow", "N/A", "Stale/Missing")
        else:
            ff_net = ff.get("net_buy", 0) / 1e9
            st.metric("Foreign Flow", f"{ff_net:+.1f} tỷ", ff.get("trend", "N/A"))

    with c5:
        if component_states["breadth"] is None:
            st.metric("A/D Ratio", "N/A", "Stale/Missing")
        else:
            adv   = breadth.get("advance", 0)
            dec   = breadth.get("decline", 0)
            total = adv + dec
            ad_str = f"{adv}/{dec}" if total > 0 else "N/A"
            breadth_label = "Tốt" if ad_ratio > 0.55 else "Xấu" if ad_ratio < 0.45 else "Trung bình"
            st.metric("A/D Ratio", ad_str, breadth_label)

    trust1, trust2, trust3, trust4 = st.columns(4)
    trust1.caption(f"World as-of: {_latest_world_as_of(world)}")
    trust2.caption("World source: Yahoo chart API")
    trust3.caption(
        "Breadth basis: KBS intraday snapshot"
        if component_states["breadth"] is not None else "Breadth basis: unavailable on this refresh"
    )
    trust4.caption(
        "Foreign flow basis: KBS snapshot | session net only"
        if component_states["foreign"] is not None else "Foreign flow basis: unavailable on this refresh"
    )

    if stale_fields:
        st.warning(
            "Macro trust warning: some components are missing or stale. "
            f"Current gaps: {', '.join(stale_fields)}."
        )
    else:
        st.caption("Macro trust: critical components loaded successfully for this refresh.")

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
            "As-of":  _world_as_of(info),
            "Nguồn":  "Yahoo chart API",
            "Tác động": impact_map.get(name, ""),
        })
    df_w = pd.DataFrame(rows)
    st.dataframe(df_w, width="stretch", hide_index=True)  # noqa: deprecated-arg
    st.caption("World market rows are delayed end-of-bar snapshots from Yahoo chart API, not exchange-native live feeds.")

    st.divider()

    # ── TF Condition Scorecard ────────────────────────────────
    st.subheader("📋 Điều Kiện Vào Lệnh Theo Timeframe")

    dxy_ok = component_states["dxy"]
    vix_ok = component_states["vix"]
    ff_ok  = component_states["foreign"]

    rows_tf = []
    for tf in TIMEFRAME_CONFIG:
        cfg       = TIMEFRAME_CONFIG[tf]
        label     = cfg["label"] if lang == "VI" else cfg["label_en"]
        reg_ok    = regime_result.regime in cfg["regime_filter"]
        overall   = _overall_tf_condition(reg_ok, dxy_ok, vix_ok, ff_ok)
        rows_tf.append({
            "Timeframe": label,
            "Regime":    "✅" if reg_ok else "❌",
            "DXY":       _status_icon(dxy_ok),
            "VIX":       _status_icon(vix_ok),
            "Foreign":   _status_icon(ff_ok),
            "Tổng thể":  overall,
            "Max Pos":   cfg["max_positions"],
            "R/R":       f"1:{cfg['target_rr']}",
        })

    df_tf = pd.DataFrame(rows_tf)
    st.dataframe(df_tf, width="stretch", hide_index=True)  # noqa: deprecated-arg
    st.caption("Foreign flow in this scorecard uses current-session KBS snapshot net flow, not verified rolling 20-session history.")

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
