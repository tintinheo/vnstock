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
from ui.components import BLUE, GREEN, GREY, RED, YELLOW, render_decision_panel, render_guidance_callout, render_section_header, render_trust_ribbon, world_sparkline


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


def _foreign_flow_signal(ff: dict) -> float:
    return float(ff.get("signal_net_buy", ff.get("net_buy", 0.0)) or 0.0)


def _foreign_flow_20d_label(trend: str) -> str:
    return {
        "accumulate": "Tích lũy 20P",
        "distribute": "Phân phối 20P",
        "neutral": "Trung tính 20P",
    }.get(trend, trend or "N/A")


def _breadth_condition_label(momentum: str, ad_ratio: float, ceiling: int, floor: int) -> tuple[str, str]:
    if momentum == "expanding" and ad_ratio >= 0.55 and ceiling >= floor:
        return "Mở rộng", "success"
    if momentum == "contracting" or ad_ratio <= 0.45 or floor > ceiling:
        return "Thu hẹp", "warning"
    return "Phân hóa", "info"


def _macro_component_states(macro_data: dict) -> dict[str, bool | None]:
    stale_fields = set(macro_data.get("stale_fields", []))
    ff = macro_data.get("foreign_flow", {})
    dxy_trend = macro_data.get("dxy_trend", "neutral")
    vix_level = macro_data.get("vix_level", "normal")
    ff_signal = _foreign_flow_signal(ff)

    return {
        "dxy": None if "DXY (USD Index)" in stale_fields else dxy_trend not in ("strong_up",),
        "vix": None if "VIX" in stale_fields else vix_level == "normal",
        "foreign": None if "foreign_flow" in stale_fields else ff_signal > -1e10,
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


def _macro_decision_state(
    overall_macro: str,
    exposure_title: str,
    exposure_hint: str,
    preferred_tfs: list[str],
    cautious_tfs: list[str],
    blocked_tfs: list[str],
) -> dict[str, str]:
    if overall_macro == "✅ Thuận lợi":
        tone = "success"
    elif overall_macro == "🚫 Rủi ro cao":
        tone = "warning"
    elif overall_macro == "⚪ Thiếu dữ liệu":
        tone = "warning"
    else:
        tone = "info"

    support_bits = [f"Market stance: {overall_macro}"]
    if preferred_tfs:
        support_bits.append(f"Ưu tiên review: {', '.join(preferred_tfs[:3])}")
    if cautious_tfs:
        support_bits.append(f"Review chọn lọc: {', '.join(cautious_tfs[:2])}")
    if blocked_tfs:
        support_bits.append(f"Hạn chế: {', '.join(blocked_tfs[:2])}")

    return {
        "primary": exposure_title,
        "secondary": f"{exposure_hint} | {' | '.join(support_bits)}",
        "tone": tone,
    }


def render_macro_tab(
    macro_data: dict,
    regime_result,          # RegimeResult
    lang: str = "VI",
) -> None:
    """
    Render Macro Pulse tab:
    - Pinned macro summary card (always above fold)
    - Evidence metrics row (always visible)
    - Collapsible sections: World Markets, Breadth Detail, Foreign Flow, TF Scorecard, Regime History
    """
    render_section_header(
        "🌐 Macro Pulse — Điều Kiện Vĩ Mô Thị Trường",
        "Đọc market stance trước, sau đó mở các section bên dưới để kiểm tra evidence.",
    )

    world        = macro_data.get("world", {})
    breadth      = macro_data.get("breadth", {})
    breadth_history = macro_data.get("breadth_history", []) or []
    breadth_momentum = macro_data.get("breadth_momentum", "neutral")
    ff           = macro_data.get("foreign_flow", {})
    ad_ratio     = macro_data.get("ad_ratio", 0.5)
    dxy_trend    = macro_data.get("dxy_trend", "neutral")
    vix_level    = macro_data.get("vix_level", "normal")
    stale_fields = macro_data.get("stale_fields", [])
    component_states = _macro_component_states(macro_data)

    tf_guidance: list[tuple[str, str]] = []
    for tf, cfg in TIMEFRAME_CONFIG.items():
        regime_ok = regime_result.regime == cfg["regime_filter"] or cfg["regime_filter"] == "all"
        tf_guidance.append((tf, _overall_tf_condition(regime_ok, component_states["dxy"], component_states["vix"], component_states["foreign"])))

    preferred_tfs = [TIMEFRAME_CONFIG[tf]["label"] for tf, status in tf_guidance if status == "✅ Thuận lợi"]
    cautious_tfs = [TIMEFRAME_CONFIG[tf]["label"] for tf, status in tf_guidance if status == "⚠️ Thận trọng"]
    blocked_tfs = [TIMEFRAME_CONFIG[tf]["label"] for tf, status in tf_guidance if status == "🚫 Rủi ro cao"]

    overall_macro = _overall_tf_condition(
        regime_result.regime != "bear",
        component_states["dxy"],
        component_states["vix"],
        component_states["foreign"],
    )
    if overall_macro == "✅ Thuận lợi":
        exposure_title = "Có thể tăng nhịp review"
        exposure_hint = "Ưu tiên setup mạnh và lọc theo liquidity/risk"
    elif overall_macro == "⚠️ Thận trọng":
        exposure_title = "Giữ trạng thái chọn lọc"
        exposure_hint = "Ưu tiên 1-2 setup tốt nhất, tránh dàn trải"
    elif overall_macro == "⚪ Thiếu dữ liệu":
        exposure_title = "Review có điều kiện"
        exposure_hint = "Đọc trust labels trước khi nâng conviction"
    else:
        exposure_title = "Thiên về phòng thủ"
        exposure_hint = "Giảm tốc độ vào lệnh mới, ưu tiên bảo toàn vốn"

    decision_state = _macro_decision_state(
        overall_macro,
        exposure_title,
        exposure_hint,
        preferred_tfs,
        cautious_tfs,
        blocked_tfs,
    )

    # ── Pinned summary card ───────────────────────────────────
    _stance_accent = {"success": GREEN, "warning": YELLOW, "info": BLUE}.get(decision_state["tone"], GREY)
    _stance_bg     = {"success": "#0f1c16", "warning": "#1f1a11", "info": "#0f1724"}.get(decision_state["tone"], "#151b28")
    _regime_str    = regime_label_vi(regime_result.regime) if lang == "VI" else regime_result.regime.title()
    _regime_emoji  = {"bull": "🟢", "bear": "🔴", "sideways": "🟡"}.get(regime_result.regime, "⚪")
    _pref_str      = ", ".join(preferred_tfs[:3]) if preferred_tfs else "—"
    _caut_str      = ", ".join(cautious_tfs[:2]) if cautious_tfs else "—"
    _dxy_icon      = _status_icon(component_states["dxy"])
    _vix_icon      = _status_icon(component_states["vix"])
    _ff_icon       = _status_icon(component_states["foreign"])
    _br_icon       = _status_icon(component_states["breadth"])
    _breadth_label, _ = _breadth_condition_label(
        str(breadth_momentum or "neutral"),
        float(ad_ratio or 0.5),
        int(breadth.get("ceiling", 0) or 0) if isinstance(breadth, dict) else 0,
        int(breadth.get("floor", 0) or 0) if isinstance(breadth, dict) else 0,
    )

    st.markdown(
        f"""
<div style='border:1px solid {_stance_accent}55;border-left:5px solid {_stance_accent};
border-radius:14px;padding:1rem 1.25rem;margin-bottom:0.75rem;background:{_stance_bg};'>
  <div style='font-size:0.82rem;color:#9db0c9;margin-bottom:0.25rem;'>🧭 Macro stance</div>
  <div style='font-size:1.25rem;font-weight:700;color:#fafafa;margin-bottom:0.5rem;'>
    {overall_macro} &nbsp;·&nbsp; {exposure_title}
  </div>
  <div style='display:flex;flex-wrap:wrap;gap:1.5rem;font-size:0.85rem;color:#cdd6e8;'>
    <span>{_regime_emoji} Regime: <b>{_regime_str}</b> ({regime_result.probability:.0%})</span>
    <span>DXY {_dxy_icon} &nbsp; VIX {_vix_icon} &nbsp; Foreign {_ff_icon} &nbsp; Breadth {_br_icon}</span>
    <span>Breadth: <b>{_breadth_label}</b></span>
    <span>Ưu tiên: <b>{_pref_str}</b></span>
    <span>Thận trọng: {_caut_str}</span>
  </div>
  <div style='margin-top:0.4rem;font-size:0.8rem;color:#7a8fa8;'>{exposure_hint}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    render_trust_ribbon([
        ("World as-of", _latest_world_as_of(world)),
        ("World source", "Yahoo chart API"),
        (
            "Breadth basis",
            "KBS intraday snapshot" if component_states["breadth"] is not None else "unavailable on this refresh",
        ),
        (
            "Foreign flow basis",
            ff.get("basis", "unavailable on this refresh") if component_states["foreign"] is not None else "unavailable on this refresh",
        ),
    ])

    if stale_fields:
        render_guidance_callout(
            "Macro trust warning",
            f"Some components are missing or stale. Current gaps: {', '.join(stale_fields)}.",
            tone="warning",
        )

    # ── Evidence Snapshot (always visible) ───────────────────
    st.subheader("🧾 Evidence Snapshot")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        regime_str = regime_label_vi(regime_result.regime) if lang == "VI" else regime_result.regime.title()
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
            history_sessions = int(ff.get("history_sessions", 0) or 0)
            delta = ff.get("trend", "N/A")
            if history_sessions >= 20:
                delta = f"{delta} | 20P {ff.get('net_buy_20d', 0) / 1e9:+.1f} tỷ"
            elif history_sessions > 1:
                delta = f"{delta} | hist {history_sessions}P"
            st.metric("Foreign Flow", f"{ff_net:+.1f} tỷ", delta)

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

    # ── Collapsible detail sections ───────────────────────────
    with st.expander("📊 Market Breadth Chi Tiết", expanded=False):
        movement = breadth.get("movement", {}) if isinstance(breadth, dict) else {}
        up_strong = int(movement.get("up_strong", 0) or 0)
        up = int(movement.get("up", 0) or 0)
        flat = int(movement.get("flat", 0) or 0)
        down = int(movement.get("down", 0) or 0)
        down_strong = int(movement.get("down_strong", 0) or 0)
        ceiling = int(breadth.get("ceiling", 0) or 0)
        floor = int(breadth.get("floor", 0) or 0)
        near_ceiling = int(breadth.get("near_ceiling", 0) or 0)
        near_floor = int(breadth.get("near_floor", 0) or 0)
        movement_total = max(1, up_strong + up + flat + down + down_strong)
        condition_label, condition_tone = _breadth_condition_label(
            str(breadth_momentum or "neutral"),
            float(ad_ratio or 0.5),
            ceiling,
            floor,
        )

        b1, b2, b3, b4, b5 = st.columns(5)
        b1.metric("Tăng mạnh", up_strong, f"{(up_strong / movement_total) * 100:.1f}%")
        b2.metric("Tăng", up, f"{(up / movement_total) * 100:.1f}%")
        b3.metric("Đứng giá", flat, f"{(flat / movement_total) * 100:.1f}%")
        b4.metric("Giảm", down, f"{(down / movement_total) * 100:.1f}%")
        b5.metric("Giảm mạnh", down_strong, f"{(down_strong / movement_total) * 100:.1f}%")

        render_guidance_callout(
            "Breadth condition",
            (
                f"Trạng thái: {condition_label} | momentum: {breadth_momentum} | "
                f"ceiling/floor: {ceiling}/{floor} | near-ceiling/floor: {near_ceiling}/{near_floor}"
            ),
            tone=condition_tone,
        )

        exchange_breakdown = breadth.get("by_exchange", {}) if isinstance(breadth, dict) else {}
        if exchange_breakdown:
            rows_ex = []
            for ex in ("HOSE", "HNX", "UPCOM"):
                bucket = exchange_breakdown.get(ex, {})
                rows_ex.append({
                    "Sàn": ex,
                    "Tăng": int(bucket.get("advance", 0) or 0),
                    "Giảm": int(bucket.get("decline", 0) or 0),
                    "Đứng": int(bucket.get("unchanged", 0) or 0),
                    "Trần": int(bucket.get("ceiling", 0) or 0),
                    "Sàn phiên": int(bucket.get("floor", 0) or 0),
                    "Tăng mạnh": int(bucket.get("up_strong", 0) or 0),
                    "Giảm mạnh": int(bucket.get("down_strong", 0) or 0),
                })
            st.dataframe(pd.DataFrame(rows_ex), width="stretch", hide_index=True)

        _sym = breadth.get("symbols", {}) if isinstance(breadth, dict) else {}
        _signal_styles = {
            "up_strong":   ("📈 Tăng mạnh",  "#00cc66", "#001a0d"),
            "up":          ("🟢 Tăng",        "#33aa66", "#001a0d"),
            "down":        ("🔴 Giảm",        "#cc4444", "#1a0000"),
            "down_strong": ("📉 Giảm mạnh",  "#ff2222", "#2a0000"),
        }
        for _key, (_label, _fg, _bg) in _signal_styles.items():
            _tickers = _sym.get(_key, [])
            if _tickers:
                with st.expander(f"{_label} — {len(_tickers)} mã", expanded=False):
                    _chips = "".join(
                        f'<span style="display:inline-block;margin:2px 3px;padding:2px 8px;'
                        f'border-radius:4px;background:{_bg};color:{_fg};'
                        f'font-size:0.82rem;font-weight:600;border:1px solid {_fg}40;'
                        f'letter-spacing:0.03em">{t}</span>'
                        for t in _tickers
                    )
                    st.markdown(f'<div style="line-height:1.8">{_chips}</div>', unsafe_allow_html=True)

        if breadth_history:
            history_df = pd.DataFrame(breadth_history)
            if not history_df.empty and "date" in history_df.columns and "ad_line" in history_df.columns:
                history_df["date"] = pd.to_datetime(history_df["date"], errors="coerce")
                history_df = history_df.dropna(subset=["date"]).sort_values("date")
                fig_ad = go.Figure(go.Scatter(
                    x=history_df["date"].dt.date.astype(str),
                    y=history_df["ad_line"],
                    mode="lines+markers",
                    line=dict(color="#2ec4b6", width=2),
                    marker=dict(size=6),
                    hovertemplate="%{x}<br>AD line: %{y}<extra></extra>",
                ))
                fig_ad.update_layout(
                    height=220,
                    template="plotly_dark",
                    paper_bgcolor="#0e1117",
                    plot_bgcolor="#0e1117",
                    margin=dict(l=40, r=10, t=20, b=30),
                    xaxis_title="Session",
                    yaxis_title="A/D line",
                    showlegend=False,
                )
                st.plotly_chart(fig_ad, width="stretch")
                st.caption("A/D line dùng 10 phiên gần nhất từ breadth_history.csv.")

    with st.expander("🌍 Thị Trường Thế Giới", expanded=False):
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
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption("World market rows are delayed end-of-bar snapshots from Yahoo chart API, not exchange-native live feeds.")

    ff_history = ff.get("history", []) or []
    with st.expander("🌊 Lịch Sử Khối Ngoại", expanded=bool(ff_history)):
        if ff_history:
            df_ff = pd.DataFrame(ff_history)
            df_ff["date"] = pd.to_datetime(df_ff["date"], errors="coerce")
            df_ff = df_ff.dropna(subset=["date"]).sort_values("date")

            ff1, ff2, ff3 = st.columns(3)
            ff1.metric("Net 20 phiên", f"{ff.get('net_buy_20d', 0) / 1e9:+.1f} tỷ", _foreign_flow_20d_label(ff.get("trend_20d", "neutral")))
            ff2.metric("History Sessions", int(ff.get("history_sessions", 0) or 0), f"As-of {ff.get('history_as_of') or '—'}")
            ff3.metric("Signal Used", f"{_foreign_flow_signal(ff) / 1e9:+.1f} tỷ", "avg 20P" if int(ff.get("history_sessions", 0) or 0) >= 20 else "latest session")

            net_vals = df_ff["net_buy"] / 1e9
            colors = [GREEN if value > 0 else RED if value < 0 else GREY for value in net_vals]
            fig_ff = go.Figure(go.Bar(
                x=df_ff["date"].dt.date.astype(str),
                y=net_vals,
                marker_color=colors,
                hovertemplate="%{x}<br>Net %{y:.1f} tỷ<extra></extra>",
            ))
            fig_ff.update_layout(
                height=260,
                template="plotly_dark",
                paper_bgcolor="#0e1117",
                plot_bgcolor="#0e1117",
                margin=dict(l=40, r=10, t=20, b=40),
                xaxis_title="Session",
                yaxis_title="Net buy (tỷ VND)",
                showlegend=False,
            )
            st.plotly_chart(fig_ff, width="stretch")
            st.caption(
                "Macro foreign-flow chart uses cached/backfilled CafeF market history when available; "
                "fallback refreshes only have current-session KBS net flow."
            )
        else:
            st.info("Chưa có lịch sử khối ngoại. Nhấn Cập nhật Macro để tải.")

    # ── TF Condition Scorecard ────────────────────────────────
    with st.expander("📋 Điều Kiện Vào Lệnh Theo Timeframe", expanded=False):
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

        st.dataframe(pd.DataFrame(rows_tf), width="stretch", hide_index=True)
        st.caption("Foreign flow in this scorecard uses verified market history when available, otherwise current-session KBS snapshot net flow.")

    # ── Regime History Chart ──────────────────────────────────
    if regime_result.history and len(regime_result.history) > 20:
        with st.expander("📈 Lịch Sử Chế Độ Thị Trường", expanded=False):
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
            st.plotly_chart(fig, width="stretch")
