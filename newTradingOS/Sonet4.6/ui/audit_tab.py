"""
ui/audit_tab.py — NewTradingOS v14.0
In-app audit log viewer with business-relevant filters.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core.audit import (
    load_events, filter_events,
    ACTION_OPEN, ACTION_CLOSE, ACTION_LOAD, ACTION_MACRO, ACTION_SCAN,
    AUDIT_FILE,
)

_ACTION_LABELS: dict[str, str] = {
    ACTION_OPEN:  "📈 Mở lệnh",
    ACTION_CLOSE: "📉 Đóng lệnh",
    ACTION_LOAD:  "🔄 Tải dữ liệu",
    ACTION_MACRO: "🌐 Cập nhật Macro",
    ACTION_SCAN:  "🔍 Scan tín hiệu",
}
_ALL_ACTIONS = list(_ACTION_LABELS.keys())


def _events_to_df(events: list[dict]) -> pd.DataFrame:
    rows = []
    for e in events:
        detail = e.get("detail", {})
        # Build a human-readable summary from the detail dict
        if e["action"] == ACTION_OPEN:
            summary = (
                f"Mua {detail.get('n_shares', '')} cp @ "
                f"{detail.get('entry_price', 0):,.0f} | "
                f"Cost: {detail.get('cost_vnd', 0):,.0f} VND | "
                f"SL {detail.get('stop_loss', 0):,.0f} "
                f"TP {detail.get('take_profit', 0):,.0f}"
            )
        elif e["action"] == ACTION_CLOSE:
            pnl = detail.get("pnl_pct", 0)
            sign = "+" if pnl >= 0 else ""
            summary = (
                f"Bán {detail.get('n_shares', '')} cp @ "
                f"{detail.get('exit_price', 0):,.0f} | "
                f"PnL: {sign}{pnl:.2f}% ({detail.get('pnl_vnd', 0):,.0f} VND) | "
                f"Lý do: {detail.get('reason', '')}"
            )
        elif e["action"] == ACTION_LOAD:
            uni = ", ".join(detail.get("universe", []))
            summary = (
                f"Universe: {uni} | "
                f"{detail.get('loaded', 0)}/{detail.get('total', 0)} mã | "
                f"{detail.get('days_back', '')} ngày"
            )
        elif e["action"] == ACTION_MACRO:
            summary = (
                f"Score: {detail.get('macro_score', ''):.1f}/10 | "
                f"Macro regime: {detail.get('macro_regime', '')} | "
                f"VNI regime: {detail.get('regime', '')}"
            )
        else:
            summary = str(detail)

        rows.append({
            "Thời gian":   e["ts"][:19].replace("T", " "),
            "Hành động":   _ACTION_LABELS.get(e["action"], e["action"]),
            "Ticker":      e.get("ticker") or "—",
            "Timeframe":   e.get("timeframe") or "—",
            "Kết quả":     e.get("result", "ok").upper(),
            "Chi tiết":    summary,
        })
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=["Thời gian", "Hành động", "Ticker",
                                  "Timeframe", "Kết quả", "Chi tiết"])


def render_audit_tab(lang: str = "VI") -> None:
    st.subheader("📜 Nhật Ký Hoạt Động (Audit Log)")

    # Load raw events
    events = load_events()

    if not events:
        st.info("Chưa có sự kiện nào. Hãy Tải Dữ Liệu hoặc Cập nhật Macro để bắt đầu ghi nhật ký.")
        return

    # ── Filters ────────────────────────────────────────────────
    st.markdown("#### 🔍 Bộ lọc")
    col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])

    with col1:
        sel_actions = st.multiselect(
            "Loại hành động",
            options=_ALL_ACTIONS,
            format_func=lambda x: _ACTION_LABELS.get(x, x),
            default=[],
            key="audit_actions",
            placeholder="Tất cả",
        )

    with col2:
        all_tickers = sorted({
            e["ticker"] for e in events
            if e.get("ticker") and e["ticker"] not in ("", "—")
        })
        sel_tickers = st.multiselect(
            "Ticker",
            options=all_tickers,
            default=[],
            key="audit_tickers",
            placeholder="Tất cả",
        )

    with col3:
        all_tfs = sorted({
            e.get("timeframe", "") for e in events
            if e.get("timeframe") and e["timeframe"] not in ("", "—")
        })
        sel_tf = st.selectbox(
            "Timeframe",
            options=[""] + all_tfs,
            format_func=lambda x: "Tất cả" if x == "" else x,
            key="audit_tf",
        )

    with col4:
        sel_result = st.selectbox(
            "Kết quả",
            options=["", "ok", "partial", "fail"],
            format_func=lambda x: "Tất cả" if x == "" else x.upper(),
            key="audit_result",
        )

    with col5:
        date_range_opts = {
            "Hôm nay":    0,
            "7 ngày":     7,
            "30 ngày":    30,
            "Tất cả":     -1,
        }
        sel_range = st.selectbox(
            "Khoảng thời gian",
            options=list(date_range_opts.keys()),
            index=3,
            key="audit_range",
        )

    # Compute date boundaries
    today_str = date.today().isoformat()
    days_ago  = date_range_opts[sel_range]
    if days_ago >= 0:
        from_str = (date.today() - timedelta(days=days_ago)).isoformat()
    else:
        from_str = None

    # Apply filters
    filtered = filter_events(
        events,
        actions=sel_actions or None,
        tickers=sel_tickers or None,
        timeframe=sel_tf or None,
        result=sel_result or None,
        date_from=from_str,
        date_to=today_str if days_ago >= 0 else None,
    )

    st.caption(f"**{len(filtered)}** sự kiện (tổng: {len(events)})")

    # ── Summary metrics (for trade actions) ────────────────────
    trade_events = [e for e in filtered if e["action"] in (ACTION_OPEN, ACTION_CLOSE)]
    if trade_events:
        closes = [e for e in trade_events if e["action"] == ACTION_CLOSE]
        if closes:
            pnls = [e["detail"].get("pnl_pct", 0) for e in closes]
            wins = sum(1 for p in pnls if p > 0)
            total_pnl = sum(e["detail"].get("pnl_vnd", 0) for e in closes)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Số lệnh đóng", len(closes))
            c2.metric("Win rate", f"{wins / len(closes) * 100:.0f}%")
            c3.metric("Avg P&L", f"{sum(pnls) / len(pnls):+.2f}%")
            c4.metric("Tổng P&L (VND)", f"{total_pnl:,.0f}")
            st.divider()

    # ── Table ──────────────────────────────────────────────────
    df = _events_to_df(filtered)
    if df.empty:
        st.info("Không có sự kiện phù hợp với bộ lọc đã chọn.")
        return

    # Colour-code Kết quả column
    def _highlight_result(val: str) -> str:
        if val == "OK":
            return "color: #00d26a; font-weight: bold"
        if val in ("FAIL", "ERROR"):
            return "color: #ff4b4b; font-weight: bold"
        if val == "PARTIAL":
            return "color: #ffa500; font-weight: bold"
        return ""

    styled = df.style.map(_highlight_result, subset=["Kết quả"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Export ─────────────────────────────────────────────────
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Tải về CSV",
        data=csv,
        file_name=f"audit_{date.today().isoformat()}.csv",
        mime="text/csv",
        key="audit_download",
    )

    # ── File path info ─────────────────────────────────────────
    with st.expander("ℹ️ Thông tin lưu trữ"):
        st.caption(f"File: `{os.path.abspath(AUDIT_FILE)}`")
        file_size = os.path.getsize(AUDIT_FILE) if os.path.exists(AUDIT_FILE) else 0
        st.caption(f"Kích thước: {file_size:,} bytes | {len(events)} sự kiện")
