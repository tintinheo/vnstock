"""Performance page — paper trading ledger, metrics, and confidence calibration."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tradingos.data.cache import cache
from tradingos.engines.portfolio_tracker import portfolio_tracker as _tracker
from tradingos.ui.components.dataframe_filter import filter_dataframe
from tradingos.ui.components.position_card import render_position_card, render_close_dialog
from tradingos.utils.dates import trading_day_offset


_PERFORMANCE_READING_GUIDE = """
- `Win rate` không đủ để đánh giá hệ thống; nên đọc cùng `Profit Factor`, `Max Drawdown` và `Calmar`.
- `Confidence Calibration` chỉ đáng tin khi số lệnh đủ lớn; đây là kiểm tra hệ thống có tự chấm độ tin cậy đúng hay không.
- Khi lọc ledger, hãy nhìn nhóm lệnh đang xem thay vì suy từ thống kê tổng thể.
"""


def _max_drawdown(pnl_series: pd.Series) -> float:
    equity = (1 + pnl_series / 100).cumprod()
    dd = 1 - equity / np.maximum.accumulate(equity)
    return float(dd.max()) if len(dd) else 0.0


def _to_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        if hasattr(value, "date"):
            return value.date()
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def render() -> None:
    st.title("📂 Danh mục & Hiệu suất")
    with st.expander("🧭 Cách đọc trang Hiệu suất", expanded=False):
        st.markdown(_PERFORMANCE_READING_GUIDE)

    tab_open, tab_closed, tab_add = st.tabs(["📂 Đang nắm", "📊 Lịch sử & Hiệu suất", "➕ Thêm lệnh thủ công"])

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1 — Open Positions T+2.5 Dashboard
    # ════════════════════════════════════════════════════════════════════════
    with tab_open:
        open_df = _tracker.get_open_positions()

        if open_df.empty:
            st.info(
                "📂 Chưa có vị thế nào đang mở.\n\n"
                "Thêm lệnh từ **🔍 Profiler** (nút 📥 Thêm vào danh mục) hoặc tab **➕ Thêm lệnh** bên cạnh."
            )
        else:
            advisories = _tracker.get_exit_advisories()
            adv_map = {a["ticker"]: a for a in advisories}
            today = date.today()

            # Sort by T+2 urgency
            rows_sorted = []
            for _, row in open_df.iterrows():
                entry_d = _to_date(row.get("entry_date"))
                t2 = trading_day_offset(entry_d, 2) if entry_d else today
                rows_sorted.append((t2, row))
            rows_sorted.sort(key=lambda x: x[0])

            st.markdown(f"**{len(open_df)} vị thế đang mở:**")
            for t2_d, row in rows_sorted:
                ticker   = str(row.get("ticker", ""))
                entry_d  = _to_date(row.get("entry_date"))
                entry_px = float(row.get("entry_price") or 0)
                sl_val   = float(row.get("initial_sl") or 0)
                mode     = str(row.get("signal_mode") or "")
                mfpm     = int(row.get("mfpm_score") or 0)

                render_position_card(
                    ticker=ticker,
                    entry_date=entry_d or today,
                    entry_price=entry_px,
                    initial_sl=sl_val,
                    signal_mode=mode,
                    mfpm_score=mfpm,
                    key_suffix=f"perf_{ticker}",
                )
                exit_price = render_close_dialog(ticker, entry_px, key_suffix=f"perf_{ticker}")
                if exit_price is not None:
                    if _tracker.close_position(ticker, exit_price):
                        st.success(f"✅ Đã đóng {ticker} tại {exit_price:,.0f}")
                        st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2 — Closed trades + performance metrics
    # ════════════════════════════════════════════════════════════════════════
    with tab_closed:
        df = cache.get_trade_ledger()

        if df.empty:
            st.info("Chưa có giao dịch nào được ghi lại trong sổ lệnh (trade ledger).")
            st.write("Chạy `scan_tickers.py` để hệ thống tự động ghi lại các tín hiệu BUY/STRONG_BUY.")
        else:
            closed = df[df["status"] == "CLOSED"].copy()
            open_trades = df[df["status"] == "OPEN"].copy()

            # ── Summary metrics ──────────────────────────────────────────────
            st.subheader("Chỉ số Hiệu suất Tổng thể")
            if not closed.empty:
                wins   = closed[closed["pnl_pct"] > 0]
                losses = closed[closed["pnl_pct"] <= 0]
                win_rate      = len(wins) / max(len(closed), 1)
                avg_gain      = wins["pnl_pct"].mean() if not wins.empty else 0.0
                avg_loss      = losses["pnl_pct"].mean() if not losses.empty else 0.0
                profit_factor = wins["pnl_pct"].sum() / max(abs(losses["pnl_pct"].sum()), 1e-9)
                sharpe        = (closed["pnl_pct"].mean() / max(closed["pnl_pct"].std(), 1e-9)) * np.sqrt(252)
                max_dd        = _max_drawdown(closed["pnl_pct"])
                calmar        = (closed["pnl_pct"].mean() * 252) / max(max_dd * 100, 1e-9)

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

            # ── Equity curve ─────────────────────────────────────────────────
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
                st.plotly_chart(fig, use_container_width=True, key="perf_equity_curve")

            # ── Walk-forward breakdown by mode ────────────────────────────────
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
                df_stats = filter_dataframe(pd.DataFrame(mode_stats), key_prefix="perf_stats")
                st.dataframe(df_stats, hide_index=True, use_container_width=True)

            # ── Confidence calibration ────────────────────────────────────────
            if not closed.empty:
                _render_confidence_calibration(closed)

            # ── Trade Ledger ──────────────────────────────────────────────────
            st.subheader("Sổ lệnh Giao dịch (Trade Ledger)")
            status_filter = st.radio("Lọc:", ["Tất cả", "OPEN", "CLOSED"], horizontal=True)
            display_df = df if status_filter == "Tất cả" else df[df["status"] == status_filter]

            display_df = filter_dataframe(display_df, key_prefix="perf_ledger")
            visible_closed = display_df[display_df["status"] == "CLOSED"] if "status" in display_df.columns else pd.DataFrame()
            visible_open   = display_df[display_df["status"] == "OPEN"]   if "status" in display_df.columns else pd.DataFrame()
            visible_win_rate = float((visible_closed["pnl_pct"] > 0).mean()) if not visible_closed.empty else 0.0
            visible_avg_pnl  = float(visible_closed["pnl_pct"].mean()) if not visible_closed.empty else 0.0
            ledger_info_cols = st.columns(4)
            ledger_info_cols[0].metric("Lệnh đang hiển thị", len(display_df), delta=f"/{len(df)} tổng")
            ledger_info_cols[1].metric("Lệnh OPEN trong view", int(len(visible_open)))
            ledger_info_cols[2].metric("Win rate trong view", f"{visible_win_rate:.1%}")
            ledger_info_cols[3].metric("P&L TB trong view", f"{visible_avg_pnl:+.2f}%")

            st.dataframe(
                display_df,
                column_config={
                    "entry_date":  st.column_config.DateColumn("Ngày vào",    format="YYYY-MM-DD"),
                    "exit_date":   st.column_config.DateColumn("Ngày thoát",   format="YYYY-MM-DD"),
                    "entry_price": st.column_config.NumberColumn("Giá vào",    format="%.2f"),
                    "initial_sl":  st.column_config.NumberColumn("SL ban đầu", format="%.2f"),
                    "exit_price":  st.column_config.NumberColumn("Giá thoát",  format="%.2f"),
                    "pnl_pct":     st.column_config.NumberColumn("P&L %",      format="%.2f"),
                    "mfpm_score":  "MFPM",
                    "mc_prob":     st.column_config.NumberColumn("MC Prob",     format="%.2f"),
                },
                use_container_width=True,
                hide_index=True,
            )

    # ════════════════════════════════════════════════════════════════════════
    # TAB 3 — Manual Trade Entry
    # ════════════════════════════════════════════════════════════════════════
    with tab_add:
        st.markdown("### ➕ Thêm giao dịch thủ công")
        st.caption("Ghi nhận giao dịch thực tế hoặc paper trade vào ledger.")

        with st.form("manual_entry_form"):
            c1, c2 = st.columns(2)
            m_ticker    = c1.text_input("Mã", placeholder="VCB").strip().upper()
            m_entry_date = c2.date_input("Ngày vào", value=date.today())
            c3, c4 = st.columns(2)
            m_entry_px  = c3.number_input("Giá vào (VND)", value=0.0, min_value=0.0, step=100.0)
            m_sl        = c4.number_input("Stop Loss (VND)", value=0.0, min_value=0.0, step=100.0)
            c5, c6, c7 = st.columns(3)
            m_mode      = c5.selectbox("Signal Mode", ["MODE_A", "MODE_B", "MODE_W", "MANUAL"], index=3)
            m_mfpm      = c6.number_input("MFPM", value=0, min_value=0, max_value=120, step=1)
            m_mc_prob   = c7.number_input("MC Win Prob", value=0.5, min_value=0.0, max_value=1.0, step=0.01)

            add_btn = st.form_submit_button("💾 Lưu lệnh", use_container_width=True, type="primary")

        if add_btn:
            if not m_ticker:
                st.error("Vui lòng nhập mã cổ phiếu.")
            elif m_entry_px <= 0:
                st.error("Giá vào phải lớn hơn 0.")
            else:
                trade_id = _tracker.add_position(
                    ticker=m_ticker,
                    entry_price=m_entry_px,
                    initial_sl=m_sl,
                    signal_mode=m_mode,
                    mfpm_score=m_mfpm,
                    mc_prob=m_mc_prob,
                    entry_date=m_entry_date,
                )
                st.success(f"✅ Đã thêm {m_ticker} vào danh mục (trade_id: `{trade_id[:8]}...`)")
                st.rerun()

        st.divider()
        st.markdown("**Đóng lệnh nhanh:**")
        open_df2 = _tracker.get_open_positions()
        if open_df2.empty:
            st.info("Không có lệnh mở.")
        else:
            opts = open_df2["ticker"].tolist()
            sel_close = st.selectbox("Chọn mã để đóng:", opts, key="quick_close_ticker")
            close_px  = st.number_input("Giá thoát", value=0.0, min_value=0.0, step=100.0, key="quick_close_px")
            if st.button("✅ Đóng lệnh", key="quick_close_btn"):
                if close_px > 0 and sel_close:
                    if _tracker.close_position(sel_close, close_px):
                        st.success(f"✅ Đã đóng {sel_close} tại {close_px:,.0f}")
                        st.rerun()
                    else:
                        st.error("Không tìm thấy lệnh mở.")
                else:
                    st.error("Giá thoát phải lớn hơn 0.")


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
                "confidence": payload.get("confidence", row.get("confidence", "—")),
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

    # [P5.1 BUG FIX] Build calib_df BEFORE calling filter_dataframe on it.
    calib_df = pd.DataFrame(calib_rows)
    calib_df = filter_dataframe(calib_df, key_prefix="perf_calib")
    st.caption(f"Đang hiển thị {len(calib_df)} nhóm confidence sau khi lọc bảng calibration.")
    if calib_df.empty:
        st.info("Không còn nhóm confidence nào sau khi lọc bảng calibration.")
        return

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
    st.plotly_chart(fig, use_container_width=True, key="perf_calibration")
    st.dataframe(calib_df, hide_index=True, use_container_width=True)

    # [P5.1] ECE + Brier Score — calibration quality metrics
    # Map confidence label to predicted probability mid-point
    _conf_prob_map = {"HIGH": 0.75, "MEDIUM": 0.55, "LOW": 0.35, "—": 0.50}
    ece_rows = merged[merged["confidence"].isin(_conf_prob_map)]
    if not ece_rows.empty:
        predicted   = ece_rows["confidence"].map(_conf_prob_map).astype(float)
        outcomes    = (ece_rows["pnl_pct"] > 0).astype(float)
        n           = len(ece_rows)
        # Brier score: mean squared error between predicted prob and binary outcome
        brier = float(((predicted - outcomes) ** 2).mean())
        # ECE: weighted average of |predicted - actual| per confidence bin
        ece_total, ece_weight = 0.0, 0
        for conf, pred_p in _conf_prob_map.items():
            grp = ece_rows[ece_rows["confidence"] == conf]
            if grp.empty:
                continue
            actual_p = float((grp["pnl_pct"] > 0).mean())
            ece_total  += len(grp) * abs(pred_p - actual_p)
            ece_weight += len(grp)
        ece = ece_total / max(ece_weight, 1)
        m1, m2 = st.columns(2)
        m1.metric(
            "ECE (Expected Calibration Error)",
            f"{ece:.3f}",
            help="0 = perfectly calibrated. ECE < 0.05 is excellent; > 0.15 is poor.",
        )
        m2.metric(
            "Brier Score",
            f"{brier:.3f}",
            help="0 = perfect. Brier < 0.20 is good for binary classification.",
        )
