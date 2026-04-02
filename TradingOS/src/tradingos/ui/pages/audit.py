"""Audit page — event log browser."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from tradingos.engines.audit_service import AuditService
from tradingos.ui.components.audit_timeline import render_audit_timeline, render_audit_stats


_ACTION_ICONS = {
    "STRONG_BUY": "🚀", "BUY": "🟢", "WATCH": "👀",
    "NO_ACTION": "⏸", "EXIT": "🔴", "FORCED_EXIT": "⚠️",
    "SCAN": "🔍", "BACKTEST": "📊", "PROFILE": "👤",
}

_INDICATOR_GUIDE = """
| Chỉ số | Ảnh hưởng tới quyết định |
|---|---|
| **MFPM Score** (0–120) | Điểm tổng hợp — ≥70 → BUY, ≥50 → WATCH, <50 → NO_ACTION |
| **Mode A Score** (0–60) | Pullback về SMA20 trong xu hướng tăng — RSI > 50 xác nhận |
| **Mode B Score** (0–60) | Phá vỡ đỉnh pivot kèm volume đột biến — second mouse gate |
| **Mode W Score** (0–115) | Whale follow — cần SMS≥60 + M-CVD UP + stealth + 7 điều kiện |
| **SMS Raw** (0–100) | Smart Money Score — ≥60: tổ chức mua, <40: retail chủ đạo |
| **M-CVD 5d** | Cumulative Volume Delta 5 phiên — UP = dòng tiền tổ chức tích lũy |
| **AMD Phase** | Accumulation / Markup / Distribution / Markdown — vị trí chu kỳ |
| **HMM State** | Hidden Markov Model — STEADY_BULL tốt nhất để vào lệnh |
| **AMF Decision** | Anti-Manipulation Filter — BLOCK = đừng vào, PASS = an toàn |
| **RSI14** | <40 oversold, 50–70 ideal entry, >75 overbought |
| **VWAP Daily** | Giá trung bình theo khối lượng ngày — trên VWAP = tích cực |
| **ATR14** | Biên độ biến động TB — dùng tính SL/TP (SL=1.5×ATR, TP1=4×ATR) |
| **Stealth Accum** | Tổ chức gom hàng không để lộ — HIGH confidence = tín hiệu mạnh |
| **Put-through Net 5d** | Khớp thoả thuận net — dương lớn = tổ chức mua qua thoả thuận |
| **FVG Zones** | Fair Value Gap — vùng trống giá thường được lấp, dùng làm hỗ trợ/kháng cự |
| **Best Pattern** | VCP/Cup-with-Handle/Wyckoff Spring/RSI Div — tăng điểm Mode A/B |
| **Dist Warning** | NONE→WATCH→CAUTION→EXIT→FORCED_EXIT — mức độ phân phối cần thoát |
| **R:R** | Risk/Reward ratio — lý tưởng ≥ 2.5 |
| **MC Win Prob** | Monte Carlo xác suất thắng (10,000 phiên) — lý tưởng ≥ 55% |
| **Sizing %** | % danh mục đề xuất cho lệnh này (Kelly fraction điều chỉnh rủi ro) |
"""


def render() -> None:
    st.title("🗂 Audit Log")
    st.caption("Lịch sử tín hiệu và sự kiện — truy xuất từ DuckDB.")

    # ── Indicator explanation ─────────────────────────────────────────────────
    with st.expander("📖 Giải thích các chỉ số ảnh hưởng đến quyết định", expanded=False):
        st.markdown(_INDICATOR_GUIDE)

    svc = AuditService()

    # ── Search form ───────────────────────────────────────────────────────────
    with st.form("audit_form"):
        c1, c2, c3 = st.columns([2, 2, 2])
        ticker = c1.text_input("Lọc mã (để trống = tất cả)", "")
        event_type = c2.selectbox(
            "Loại sự kiện",
            ["", "PROFILE", "SCAN", "BACKTEST", "POSITION_OPEN"],
            index=0,
        )
        action_filter = c3.multiselect(
            "Lọc Action",
            options=["STRONG_BUY", "BUY", "WATCH", "NO_ACTION", "EXIT", "FORCED_EXIT"],
            default=[],
            placeholder="Tất cả",
        )

        tc1, tc2, tc3 = st.columns([2, 2, 1])
        date_from = tc1.date_input(
            "Từ ngày",
            value=(datetime.now(timezone.utc) - timedelta(days=7)).date(),
        )
        date_to = tc2.date_input("Đến ngày", value=datetime.now(timezone.utc).date())
        limit = tc3.number_input("Giới hạn", value=500, min_value=10, max_value=5000, step=50)
        submitted = st.form_submit_button("🔍 Tìm kiếm", use_container_width=True)

    if submitted:
        # days_back derived from date_from
        days_back = max(1, (datetime.now(timezone.utc).date() - date_from).days + 1)
        df = svc.query_events(
            ticker=ticker.upper() if ticker.strip() else None,
            event_type=event_type if event_type else None,
            days_back=days_back,
            limit=int(limit),
        )

        # Apply date_to upper cut
        if not df.empty and "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
            cutoff = pd.Timestamp(date_to, tz="UTC") + pd.Timedelta(days=1)
            df = df[df["timestamp"] < cutoff]

        if action_filter and "action" in df.columns:
            df = df[df["action"].isin(action_filter)]

        # ── Signal breakdown tiles ────────────────────────────────────────
        if "action" in df.columns and not df.empty:
            breakdown = df["action"].value_counts()
            cols = st.columns(min(len(breakdown) + 1, 7))
            cols[0].metric("📋 Tổng sự kiện", len(df))
            for i, (action, count) in enumerate(breakdown.items(), start=1):
                cols[i % len(cols)].metric(
                    f"{_ACTION_ICONS.get(action, '•')} {action}", int(count)
                )
        else:
            st.metric("📋 Tổng sự kiện", len(df))

        st.subheader(f"📋 {len(df)} sự kiện")

        if not df.empty:
            # ── Expand payload JSON into columns ──────────────────────────
            if "payload" in df.columns:
                def _expand(row):
                    try:
                        p = json.loads(row) if isinstance(row, str) else (row or {})
                    except Exception:
                        p = {}
                    return pd.Series(p)

                payload_df = df["payload"].apply(_expand)
                # Prefix payload columns that collide with existing columns
                base_cols = set(df.columns) - {"payload"}
                rename_map = {c: f"p_{c}" for c in payload_df.columns if c in base_cols}
                payload_df = payload_df.rename(columns=rename_map)
                df = pd.concat([df.drop(columns=["payload"]), payload_df], axis=1)

            # Ensure index is unique and clean before styling
            df = df.reset_index(drop=True)

            # ── Column ordering ───────────────────────────────────────────
            priority_cols = [
                "timestamp", "ticker", "event_type", "action", "confidence",
                # Scores (from base row — payload versions prefixed p_*)
                "mfpm_score", "p_mode_a_score", "p_mode_b_score", "p_mode_w_score", "p_mc_prob",
                # Signal context
                "p_signal_mode", "p_amd_phase", "p_hmm_state", "p_amf_decision", "p_best_pattern",
                "p_stealth_accum", "p_stealth_conf", "p_dist_warning",
                # Levels
                "p_close", "p_entry", "p_sl", "p_tp1", "p_tp2", "p_rr",
                # Money flow
                "sms_raw", "p_mcvd_trend", "p_mcvd_5d", "p_pt_net_5d",
                "p_whale_pct_vol", "p_sector_flow",
                # Technical
                "p_rsi14", "p_sma20", "p_sma50", "p_atr14", "p_vwap_daily",
                "p_obv", "p_vqs", "p_gmo_omega",
                # FVG + sizing
                "p_fvg_zones", "p_sizing_pct", "p_sector",
            ]
            display_cols = [c for c in priority_cols if c in df.columns]
            # Append any remaining columns not in priority list and not internal
            _skip = {"audit_id", "signal_id", "rejected_reason", "amf_decision",
                     "signal_mode", "close", "entry", "sl", "tp1", "tp2", "rr"}
            display_cols += [c for c in df.columns if c not in display_cols
                              and c not in _skip]
            df_display = df[display_cols].copy()

            # Format timestamp
            if "timestamp" in df_display.columns:
                df_display["timestamp"] = df_display["timestamp"].dt.strftime("%Y-%m-%d %H:%M")

            # Round floats
            for col in ["p_close", "p_entry", "p_sl", "p_tp1", "p_tp2", "p_vwap_daily", "p_sma20", "p_sma50"]:
                if col in df_display.columns:
                    df_display[col] = df_display[col].round(1)
            for col in ["p_rr", "p_mc_prob", "p_sizing_pct", "p_whale_pct_vol", "p_gmo_omega", "p_vqs"]:
                if col in df_display.columns:
                    df_display[col] = df_display[col].round(3)

            def _colour_action(val: str) -> str:
                colours = {
                    "STRONG_BUY":  "background-color:#004d1a; color:#00c851",
                    "BUY":         "background-color:#002d40; color:#33b5e5",
                    "WATCH":       "background-color:#3d3000; color:#ffbb33",
                    "NO_ACTION":   "color:#888",
                    "EXIT":        "background-color:#3d0000; color:#ff4444",
                    "FORCED_EXIT": "background-color:#260000; color:#cc0000",
                }
                return colours.get(val, "")

            styled = (
                df_display.style.map(_colour_action, subset=["action"])
                if "action" in df_display.columns else df_display.style
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)

            # ── FVG detail expander ───────────────────────────────────────
            if "p_fvg_zones" in df_display.columns:
                fvg_rows = df_display[
                    df_display["p_fvg_zones"].apply(
                        lambda x: bool(x) if isinstance(x, list) else False
                    )
                ]
                if not fvg_rows.empty:
                    with st.expander(f"🕳️ FVG zones ({len(fvg_rows)} mã có gap)", expanded=False):
                        for _, row in fvg_rows.iterrows():
                            ticker_label = row.get("ticker", "?")
                            zones = row["p_fvg_zones"]
                            if isinstance(zones, list) and zones:
                                zone_lines = "  ".join(
                                    f"**{z.get('type','?')}** [{z.get('low',0):.1f}–{z.get('high',0):.1f}]"
                                    for z in zones
                                )
                                st.markdown(f"**{ticker_label}**: {zone_lines}")

            # Export
            export_df = df_display.copy()
            if "p_fvg_zones" in export_df.columns:
                export_df["p_fvg_zones"] = export_df["p_fvg_zones"].apply(
                    lambda x: json.dumps(x) if isinstance(x, list) else x
                )
            csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ Xuất CSV",
                data=csv_bytes,
                file_name=f"audit_log_{date_from}_{date_to}.csv",
                mime="text/csv",
            )
        else:
            st.info("Không có sự kiện audit phù hợp.")

    st.divider()
    st.subheader("📊 Thống kê 30 ngày gần nhất")
    stats = svc.summary_stats(days_back=30)
    render_audit_stats(stats)

