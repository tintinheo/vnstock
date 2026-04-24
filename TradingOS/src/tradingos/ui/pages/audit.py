"""Audit page — event log browser."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from tradingos.engines.audit_service import AuditService
from tradingos.ui.components.audit_timeline import render_audit_stats
from tradingos.ui.components.dataframe_filter import filter_dataframe
from tradingos.ui.components.tplus_explainer import (
    TPLUS_MAPPING_GUIDE,
    build_action_tplus_explanation,
    build_tplus_exit_plan,
    verdict_label,
    verdict_row_tint,
    verdict_style,
)


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

_VN_BEHAVIOR_GUIDE = """
- Ưu tiên đọc theo cụm `MFPM + SMS/M-CVD + AMF + T+ Verdict`, không dùng RSI hay OBV như trigger độc lập.
- `RSI14`, `OBV`, `VWAP` và `ATR` là chỉ báo ngữ cảnh/rủi ro; ở thị trường Việt Nam chúng dễ nhiễu khi bị kéo trụ, nghẽn thanh khoản hoặc có giao dịch thoả thuận lớn.
- `Put-through Net`, `Whale % Vol` và `Sector Flow` phản ánh tâm lý dòng tiền nội sát hơn foreign-flow thô, vì hành vi nhà đầu tư Việt thường bị dẫn dắt bởi nhóm ngành và tay to nội.
- `MC Win Prob` và `R:R` chỉ hữu ích khi đi cùng `AMF=PASS` và không có `Dist Warning`; xác suất đẹp nhưng bị phân phối vẫn là tín hiệu xấu.
"""


def render() -> None:
    st.title("🗂 Audit Log")
    st.caption("Lịch sử tín hiệu và sự kiện — truy xuất từ DuckDB.")

    # ── Indicator explanation ─────────────────────────────────────────────────
    with st.expander("📖 Giải thích các chỉ số ảnh hưởng đến quyết định", expanded=False):
        st.markdown(_INDICATOR_GUIDE)
    with st.expander("🧭 Cách đọc đúng theo hành vi thị trường Việt Nam", expanded=False):
        st.markdown(_VN_BEHAVIOR_GUIDE)
    with st.expander("🧩 Mapping chuẩn giữa Action và T+ Verdict", expanded=False):
        st.markdown(TPLUS_MAPPING_GUIDE)

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

        # ── Advanced signal filters ───────────────────────────────────────
        st.markdown("**Lọc nâng cao theo tín hiệu:**")
        af1, af2, af3, af4 = st.columns(4)
        tw_filter = af1.multiselect(
            "⚠️ Trend Warning",
            options=[
                "UPTREND_STRENGTHENING", "UPTREND_EXHAUSTING",
                "BREAKOUT_EMERGING",
                "DOWNTREND_STRENGTHENING", "DOWNTREND_EXHAUSTING",
                "RANGE_COMPRESSION",
                "REVERSAL_WARNING_LOW_CONF", "REVERSAL_WARNING_CONFIRMED",
                "NONE",
            ],
            default=[],
            placeholder="Tất cả",
        )
        fc_filter = af2.multiselect(
            "🔭 Dự báo",
            options=["TĂNG", "GIẢM", "TRUNG LẬP"],
            default=[],
            placeholder="Tất cả",
        )
        vd_filter = af3.multiselect(
            "🎯 T+ Verdict",
            options=["MUA_NGAY", "CHO_XAC_NHAN", "THEO_DOI", "TRANH_XA"],
            default=[],
            placeholder="Tất cả",
        )
        min_tconf_audit = af4.number_input(
            "T+ Conf% tối thiểu", min_value=0, max_value=100, value=0, step=5,
        )

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

        st.session_state["audit_results"] = df.copy()
        st.session_state["audit_has_run"] = True

    audit_has_run = st.session_state.get("audit_has_run", False)
    df = st.session_state.get("audit_results") if audit_has_run else None

    if audit_has_run and df is not None:
        df = df.copy()
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

            # ── Apply advanced signal filters (on expanded payload cols) ──
            if tw_filter:
                _tw_col = next((c for c in ["trend_warning", "p_trend_warning"] if c in df.columns), None)
                if _tw_col:
                    df = df[df[_tw_col].isin(tw_filter)]
            if fc_filter:
                _fc_col = next((c for c in ["fc_overall_vote", "p_fc_overall_vote"] if c in df.columns), None)
                if _fc_col:
                    df = df[df[_fc_col].isin(fc_filter)]
            if vd_filter:
                _vd_col = next((c for c in ["tplus_verdict", "p_tplus_verdict"] if c in df.columns), None)
                if _vd_col:
                    df = df[df[_vd_col].isin(vd_filter)]
            if min_tconf_audit > 0:
                _tc_col = next((c for c in ["tplus_confidence", "p_tplus_confidence"] if c in df.columns), None)
                if _tc_col:
                    df = df[pd.to_numeric(df[_tc_col], errors="coerce").fillna(0) >= min_tconf_audit]

            # ── [BUG-B1 FIX] Signal breakdown tiles ──
            if "action" in df.columns and not df.empty:
                with st.container(border=True):
                    st.markdown("##### 📈 Tổng quan kết quả")
                    breakdown = df["action"].value_counts()
                    cols = st.columns(min(len(breakdown) + 1, 7))
                    cols[0].metric("📋 Tổng sự kiện", len(df))
                    for i, (action, count) in enumerate(breakdown.items(), start=1):
                        cols[i % len(cols)].metric(
                            f"{_ACTION_ICONS.get(action, '•')} {action}", int(count)
                        )
            else:
                st.metric("📋 Tổng sự kiện", len(df))

            st.subheader(f"🗂 {len(df)} sự kiện chi tiết")

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
            verdict_col = next((c for c in ["tplus_verdict", "p_tplus_verdict"] if c in df_display.columns), None)
            verdict_vi_col = next((c for c in ["tplus_verdict_vi", "p_tplus_verdict_vi"] if c in df_display.columns), None)
            stop_col = next((c for c in ["tplus_stop", "p_tplus_stop"] if c in df_display.columns), None)
            t25_col = next((c for c in ["tplus_target_t25", "p_tplus_target_t25"] if c in df_display.columns), None)
            t5_col = next((c for c in ["tplus_target_t5", "p_tplus_target_t5"] if c in df_display.columns), None)
            entry_low_col = next((c for c in ["tplus_entry_low", "p_tplus_entry_low"] if c in df_display.columns), None)
            entry_high_col = next((c for c in ["tplus_entry_high", "p_tplus_entry_high"] if c in df_display.columns), None)
            if verdict_col:
                df_display["tplus_verdict_vi_display"] = df_display.apply(
                    lambda row: verdict_label(
                        row.get(verdict_col, ""),
                        row.get(verdict_vi_col, "") if verdict_vi_col else "",
                    ),
                    axis=1,
                )
                df_display["action_tplus_note"] = df_display.apply(
                    lambda row: build_action_tplus_explanation(
                        row.get("action", ""),
                        row.get(verdict_col, ""),
                    ),
                    axis=1,
                )
                df_display["tplus_exit_plan"] = df_display.apply(
                    lambda row: build_tplus_exit_plan(
                        row.get(verdict_col, ""),
                        row.get(stop_col, 0.0) if stop_col else 0.0,
                        row.get(t25_col, 0.0) if t25_col else 0.0,
                        row.get(t5_col, 0.0) if t5_col else 0.0,
                        row.get(entry_low_col, 0.0) if entry_low_col else 0.0,
                        row.get(entry_high_col, 0.0) if entry_high_col else 0.0,
                    ),
                    axis=1,
                )
            total_events = len(df_display)

            df_display = filter_dataframe(df_display, key_prefix="audit")

            filtered_tickers = df_display["ticker"].nunique() if "ticker" in df_display.columns else 0
            filtered_actions = df_display["action"].nunique() if "action" in df_display.columns else 0
            info_cols = st.columns(3)
            info_cols[0].metric("Sự kiện đang hiển thị", len(df_display), delta=f"/{total_events} tổng")
            info_cols[1].metric("Mã cổ phiếu trong view", int(filtered_tickers))
            info_cols[2].metric("Loại khuyến nghị trong view", int(filtered_actions))

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
                    "STRONG_BUY":  "background-color:#004d1a; color:#00c851; font-weight:bold",
                    "BUY":         "background-color:#002d40; color:#33b5e5; font-weight:bold",
                    "WATCH":       "background-color:#3d3000; color:#ffbb33",
                    "NO_ACTION":   "color:#666666",
                    "EXIT":        "background-color:#3d0000; color:#ff4444; font-weight:bold",
                    "FORCED_EXIT": "background-color:#260000; color:#cc0000; font-weight:bold",
                }
                return colours.get(val, "")

            def _colour_verdict(val: str) -> str:
                return verdict_style(val)

            def _row_tint(row: pd.Series) -> list[str]:
                verdict_value = row.get("p_tplus_verdict", row.get("tplus_verdict", ""))
                tint = verdict_row_tint(verdict_value)
                return [tint] * len(row)

            config = {
                "timestamp": st.column_config.TextColumn("⏰ Thời gian", width="medium"),
                "ticker": st.column_config.TextColumn("🏷 MÃ CK", width="small"),
                "event_type": st.column_config.TextColumn("Loại SK", width="small", help="Kiểu sự kiện trong hệ thống (PROFILE, SCAN, v.v)"),
                "action": st.column_config.TextColumn("🎯 Khuyến nghị", width="medium", help="Quyết định cuối cùng do TradingOS đưa ra."),
                "confidence": st.column_config.ProgressColumn("⭐ T+ Conf(%)", format="%.0f", min_value=0, max_value=120, help="Độ tự tin vào lệnh T+ (càng cao khả năng thắng càng lớn)"),
                "p_tplus_verdict": st.column_config.TextColumn("🎯 T+ Verdict", help="Timing T+ của tín hiệu tại thời điểm log."),
                "tplus_verdict_vi_display": st.column_config.TextColumn("T+ Verdict VI", help="Diễn giải tiếng Việt của verdict T+ để đọc nhanh."),
                "action_tplus_note": st.column_config.TextColumn("A×T+ Ý nghĩa", width="large", help="Giải thích chuẩn cho tổ hợp Action và T+ Verdict, ví dụ BUY nhưng CHO_XAC_NHAN nghĩa là gì."),
                "tplus_exit_plan": st.column_config.TextColumn("T+ Exit", width="large", help="Điểm EXIT và mục tiêu tham chiếu theo verdict T+, gồm stop, T+2.5 và T+5."),
                "mfpm_score": st.column_config.ProgressColumn("🔥 Chấm điểm MFPM", format="%.0f", min_value=0, max_value=120, help="Điểm số sức mạnh kỹ thuật và xu hướng"),
                "sms_raw": st.column_config.ProgressColumn("🐳 Lực Mua Cá Mập", format="%d", min_value=0, max_value=100, help="Smart Money Score: >=60 là dòng tiền lớn đang gom, <40 là lực bán xả hàng"),
                "p_rsi14": st.column_config.NumberColumn("Sức mạnh RSI", format="%.1f", help="Chỉ báo RSI: >70 (rất nóng/mua nhiều), <30 (quá lạnh/bị bán tháo)"),
                "p_rr": st.column_config.NumberColumn("Lợi nhuận / Rủi ro ⚖️", format="%.2fx", help="Tỉ lệ Lợi nhuận dự kiến chia cho Rủi ro (Reward/Risk). Lớn hơn 2x là rất tốt."),
                "p_mc_prob": st.column_config.NumberColumn("Tỉ lệ thắng (MC)%", format="%.1f%%", help="Xác suất giá chốt lời thành công qua mô phỏng Monte Carlo"),
                "p_close": st.column_config.NumberColumn("💰 Giá Khớp", format="%.1f", help="Giá trị thực tế tại thời điểm quét tín hiệu"),
                "p_entry": st.column_config.NumberColumn("Điểm Mua", format="%.1f", help="Vùng giá mua an toàn"),
                "p_sl": st.column_config.NumberColumn("Cắt Lỗ (SL)", format="%.1f", help="Vùng giá phải bán cắt lỗ để bảo vệ vốn"),
                "p_tp1": st.column_config.NumberColumn("Chốt Lời (TP1)", format="%.1f", help="Mức giá kỳ vọng chốt lời một phần"),
                "p_tp2": st.column_config.NumberColumn("Chốt Lời (TP2)", format="%.1f", help="Mức chốt lời mục tiêu cuối cùng"),
            }

            styled = (
                df_display.style.apply(_row_tint, axis=1)
                .map(_colour_action, subset=["action"])
                .map(_colour_verdict, subset=[c for c in ["ticker", "p_tplus_verdict", "tplus_verdict_vi_display"] if c in df_display.columns])
                if "action" in df_display.columns else df_display.style
            )
            st.dataframe(
                styled, 
                use_container_width=True, 
                hide_index=True, 
                column_config=config, 
                height=650
            )

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

