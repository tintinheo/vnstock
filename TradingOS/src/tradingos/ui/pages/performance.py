"""Performance page — paper trading ledger, metrics, and confidence calibration."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tradingos.data.cache import cache


def _max_drawdown(pnl_series: pd.Series) -> float:
    equity = (1 + pnl_series / 100).cumprod()
    dd = 1 - equity / np.maximum.accumulate(equity)
    return float(dd.max()) if len(dd) else 0.0


def render() -> None:
    st.title("🏆 Hiệu suất Giao dịch (Paper Trading)")

    df = cache.get_trade_ledger()

    if df.empty:
        st.info("Chưa có giao dịch nào được ghi lại trong sổ lệnh (trade ledger).")
        st.write("Chạy `scan_tickers.py` để hệ thống tự động ghi lại các tín hiệu BUY/STRONG_BUY.")
        return

    closed = df[df["status"] == "CLOSED"].copy()
    open_trades = df[df["status"] == "OPEN"].copy()

    # ── Summary metrics ───────────────────────────────────────────────────
    st.subheader("Chỉ số Hiệu suất Tổng thể")
    if not closed.empty:
        wins   = closed[closed["pnl_pct"] > 0]
        losses = closed[closed["pnl_pct"] <= 0]
        win_rate     = len(wins) / max(len(closed), 1)
        avg_gain     = wins["pnl_pct"].mean() if not wins.empty else 0.0
        avg_loss     = losses["pnl_pct"].mean() if not losses.empty else 0.0
        profit_factor = wins["pnl_pct"].sum() / max(abs(losses["pnl_pct"].sum()), 1e-9)
        sharpe       = (closed["pnl_pct"].mean() / max(closed["pnl_pct"].std(), 1e-9)) * np.sqrt(252)
        max_dd       = _max_drawdown(closed["pnl_pct"])
        calmar       = (closed["pnl_pct"].mean() * 252) / max(max_dd * 100, 1e-9)

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Tỷ lệ thắng",    f"{win_rate:.1%}")
        col2.metric("Lãi TB",          f"{avg_gain:+.2f}%")
        col3.metric("Lỗ TB",           f"{avg_loss:+.2f}%")
        col4.metric("Profit Factor",   f"{profit_factor:.2f}")
        col5.metric("Sharpe",          f"{sharpe:.2f}")
        col6.metric("Max Drawdown",    f"{max_dd:.1%}")

        if len(open_trades):
            st.caption(f"📂 {len(open_trades)} giao dịch đang mở | "
                       f"📊 {len(closed)} giao dịch đã đóng | "
                       f"Calmar Ratio: {calmar:.2f}")
    else:
        st.info("_Chưa có giao dịch đã đóng. Hệ thống sẽ ghi lại kết quả khi exit advisory được kích hoạt._")

    # ── Equity curve ──────────────────────────────────────────────────────
    if not closed.empty:
        st.subheader("Biểu đồ Tăng trưởng Vốn (Equity Curve)")
        closed_s = closed.sort_values("exit_date")
        closed_s["equity"] = (1 + closed_s["pnl_pct"] / 100).cumprod()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(closed_s["exit_date"]),
            y=closed_s["equity"],
            mode="lines",
            line=dict(color="#00c851", width=2),
            name="Portfolio",
        ))
        fig.add_hline(y=1.0, line_dash="dash", line_color="#888", annotation_text="Vốn ban đầu")
        fig.update_layout(
            title="Tăng trưởng vốn giả định (1 đơn vị ban đầu)",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Walk-forward breakdown by mode ────────────────────────────────────
    if not closed.empty and "signal_mode" in closed.columns:
        st.subheader("Hiệu suất theo Mode tín hiệu")
        mode_stats = []
        for mode, grp in closed.groupby("signal_mode"):
            w = grp[grp["pnl_pct"] > 0]
            l = grp[grp["pnl_pct"] <= 0]
            mode_stats.append({
                "Mode": mode,
                "Số lệnh": len(grp),
                "Tỷ lệ thắng": f"{len(w)/max(len(grp),1):.1%}",
                "Lãi TB": f"{w['pnl_pct'].mean():+.2f}%" if not w.empty else "—",
                "Lỗ TB": f"{l['pnl_pct'].mean():+.2f}%" if not l.empty else "—",
                "Profit Factor": f"{w['pnl_pct'].sum()/max(abs(l['pnl_pct'].sum()),1e-9):.2f}",
                "Max DD": f"{_max_drawdown(grp['pnl_pct']):.1%}",
            })
        st.dataframe(pd.DataFrame(mode_stats), hide_index=True, use_container_width=True)

    # ── Confidence calibration chart ──────────────────────────────────────
    if not closed.empty:
        _render_confidence_calibration(closed)

    # ── Trade Ledger ──────────────────────────────────────────────────────
    st.subheader("Sổ lệnh Giao dịch (Trade Ledger)")
    status_filter = st.radio("Lọc:", ["Tất cả", "OPEN", "CLOSED"], horizontal=True)
    display_df = df if status_filter == "Tất cả" else df[df["status"] == status_filter]
    st.dataframe(
        display_df,
        column_config={
            "entry_date":   st.column_config.DateColumn("Ngày vào",     format="YYYY-MM-DD"),
            "exit_date":    st.column_config.DateColumn("Ngày thoát",    format="YYYY-MM-DD"),
            "entry_price":  st.column_config.NumberColumn("Giá vào",     format="%.2f"),
            "initial_sl":   st.column_config.NumberColumn("SL ban đầu",  format="%.2f"),
            "exit_price":   st.column_config.NumberColumn("Giá thoát",   format="%.2f"),
            "pnl_pct":      st.column_config.NumberColumn("P&L %",       format="%.2f"),
            "mfpm_score":   "MFPM",
            "mc_prob":      st.column_config.NumberColumn("MC Prob",      format="%.2f"),
        },
        use_container_width=True,
        hide_index=True,
    )


def _render_confidence_calibration(closed: pd.DataFrame) -> None:
    """
    Confidence calibration chart: for each confidence level, what was the
    actual win rate? Joins trade_ledger with audit_log via ticker+entry_date.
    """
    st.subheader("🎯 Hiệu chuẩn Độ tin cậy (Confidence Calibration)")
    st.caption("Nếu hệ thống hoạt động tốt, tỷ lệ thắng của HIGH > MEDIUM > LOW.")

    # Pull audit log for PROFILE events to get confidence per ticker/date
    try:
        audit_df = cache.query_audit(event_type="PROFILE", days_back=365, limit=5000)
    except Exception:
        st.write("_Không thể tải dữ liệu audit log._")
        return

    if audit_df.empty or "payload" not in audit_df.columns:
        st.write("_Chưa đủ dữ liệu audit để hiệu chuẩn._")
        return

    import json
    rows = []
    for _, row in audit_df.iterrows():
        try:
            payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
            rows.append({
                "ticker": row.get("ticker"),
                "date": str(row.get("timestamp", ""))[:10],
                "confidence": payload.get("confidence", "—"),
            })
        except Exception:
            pass

    if not rows:
        st.write("_Không thể phân tích payload audit._")
        return

    audit_conf = pd.DataFrame(rows)
    # Match on ticker (approximate: same ticker, closest date)
    merged = closed.rename(columns={"entry_date": "date"})
    merged["date"] = merged["date"].astype(str).str[:10]
    merged = merged.merge(audit_conf, on=["ticker", "date"], how="left")

    conf_order = ["HIGH", "MEDIUM", "LOW", "—"]
    calib_rows = []
    for conf in conf_order:
        grp = merged[merged["confidence"] == conf]
        if grp.empty:
            continue
        wr = (grp["pnl_pct"] > 0).mean()
        calib_rows.append({"Độ tin cậy": conf, "Số lệnh": len(grp), "Tỷ lệ thắng thực tế": wr})

    if not calib_rows:
        st.write("_Chưa đủ dữ liệu để hiển thị._")
        return

    calib_df = pd.DataFrame(calib_rows)
    colors = {"HIGH": "#00c851", "MEDIUM": "#ffbb33", "LOW": "#ff4444", "—": "#888888"}

    fig = go.Figure(go.Bar(
        x=calib_df["Độ tin cậy"],
        y=calib_df["Tỷ lệ thắng thực tế"],
        marker_color=[colors.get(c, "#888") for c in calib_df["Độ tin cậy"]],
        text=[f"{v:.1%}" for v in calib_df["Tỷ lệ thắng thực tế"]],
        textposition="outside",
    ))
    fig.add_hline(y=0.5, line_dash="dash", line_color="#888", annotation_text="50% ngẫu nhiên")
    fig.update_layout(
        yaxis=dict(tickformat=".0%", range=[0, 1]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        height=280,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(calib_df, hide_index=True, use_container_width=True)

