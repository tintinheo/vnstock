"""
ui/backtest_tab.py — NewTradingOS v14.0
Backtest tab UI.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import TIMEFRAME_CONFIG, INITIAL_CAPITAL, TICKER_EXCHANGE
from backtest.engine import BacktestResult, run_backtest, run_multi_tf_backtest, summarise_results, trades_to_df
from ui.components import GREEN, RED, YELLOW, equity_chart, render_decision_panel, render_guidance_callout, render_section_header


def _backtest_review_table(results: dict[str, BacktestResult]) -> pd.DataFrame:
    rows: list[dict] = []
    for tf, res in results.items():
        metrics = res.metrics
        if "error" in metrics:
            rows.append({
                "TF": tf,
                "Review Score": -1,
                "Verdict": "Thiếu dữ liệu",
                "CAGR %": 0.0,
                "Total Ret %": 0.0,
                "Sharpe": 0.0,
                "Max DD %": 0.0,
                "Win Rate %": 0.0,
                "# Trades": 0,
                "Error": metrics["error"],
            })
            continue

        review_score = 0
        total_return = float(metrics.get("total_return", 0.0) or 0.0)
        sharpe = float(metrics.get("sharpe", 0.0) or 0.0)
        max_dd = float(metrics.get("max_dd", 0.0) or 0.0)
        win_rate = float(metrics.get("win_rate", 0.0) or 0.0)
        n_trades = int(metrics.get("n_trades", 0) or 0)
        profit_factor = float(metrics.get("profit_factor", 0.0) or 0.0)

        review_score += 1 if total_return > 0 else 0
        review_score += 1 if sharpe >= 0.8 else 0
        review_score += 1 if max_dd >= -15 else 0
        review_score += 1 if profit_factor >= 1.1 else 0
        review_score += 1 if n_trades >= 3 else 0

        if review_score >= 4:
            verdict = "Ưu tiên review"
        elif review_score >= 2:
            verdict = "Có thể dùng"
        else:
            verdict = "Thận trọng"

        rows.append({
            "TF": tf,
            "Review Score": review_score,
            "Verdict": verdict,
            "CAGR %": float(metrics.get("cagr", 0.0) or 0.0),
            "Total Ret %": total_return,
            "Sharpe": sharpe,
            "Max DD %": max_dd,
            "Win Rate %": win_rate,
            "# Trades": n_trades,
            "Error": "",
        })

    compare_df = pd.DataFrame(rows)
    if compare_df.empty:
        return compare_df

    compare_df = compare_df.sort_values(
        ["Review Score", "Total Ret %", "Sharpe", "Max DD %"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    compare_df.insert(0, "Rank", range(1, len(compare_df) + 1))
    return compare_df


def _backtest_review_summary(compare_df: pd.DataFrame) -> dict[str, str | int]:
    if compare_df.empty:
        return {
            "best_tf": "—",
            "best_verdict": "Chưa có kết quả",
            "robust_count": 0,
            "next_action": "Chạy backtest",
            "next_hint": "Cần ít nhất một kết quả hợp lệ để so sánh",
        }

    valid_df = compare_df[compare_df["Review Score"] >= 0]
    if valid_df.empty:
        return {
            "best_tf": "—",
            "best_verdict": "Thiếu dữ liệu",
            "robust_count": 0,
            "next_action": "Tăng lookback",
            "next_hint": "Dữ liệu chưa đủ cho timeframe đang chọn",
        }

    best_row = valid_df.iloc[0]
    robust_count = int((valid_df["Review Score"] >= 4).sum())
    if best_row["Review Score"] >= 4:
        next_action = f"Review sâu {best_row['TF']}"
        next_hint = "Ưu tiên equity curve, trade log và exit reasons của TF tốt nhất"
    elif best_row["Review Score"] >= 2:
        next_action = f"So sánh {best_row['TF']} với TF khác"
        next_hint = "Kiểm tra drawdown và số trade trước khi tin vào CAGR"
    else:
        next_action = "Thận trọng với mọi TF"
        next_hint = "Ưu tiên xem assumptions và thử regime/macro khác"

    return {
        "best_tf": str(best_row["TF"]),
        "best_verdict": str(best_row["Verdict"]),
        "robust_count": robust_count,
        "next_action": next_action,
        "next_hint": next_hint,
    }


def _backtest_decision_state(review_summary: dict[str, str | int]) -> dict[str, str]:
    robust_count = int(review_summary.get("robust_count", 0) or 0)
    best_verdict = str(review_summary.get("best_verdict", ""))

    if robust_count > 0:
        tone = "success"
    elif best_verdict in ("Có thể dùng", "Chưa có kết quả"):
        tone = "info"
    else:
        tone = "warning"

    return {
        "primary": str(review_summary.get("next_action", "Chạy backtest")),
        "secondary": str(review_summary.get("next_hint", "Cần ít nhất một kết quả hợp lệ để so sánh")),
        "tone": tone,
    }


def render_backtest_tab(
    data_dict: dict,
    lang: str = "VI",
    exchange_map: dict[str, str] | None = None,
    vni_df: pd.DataFrame | None = None,
) -> None:
    render_section_header(
        "🧪 Backtest Engine — T+2 Realistic (VN)",
        "So sánh matrix trước để chọn timeframe đáng xem sâu, rồi mới mở từng tab equity/trade log.",
    )

    if not data_dict:
        st.info("Chưa có dữ liệu giá. Hãy tải dữ liệu trước khi chạy backtest.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        ticker = st.selectbox("Chọn mã", sorted(data_dict.keys()),
                               key="bt_ticker")
    with c2:
        capital = st.number_input("Vốn ban đầu (VND)",
                                   min_value=10_000_000,
                                   max_value=10_000_000_000,
                                   value=INITIAL_CAPITAL,
                                   step=10_000_000,
                                   key="bt_capital")
    with c3:
        run_all_tf = st.toggle("Chạy tất cả TF", value=True, key="bt_all_tf")

    single_tf = None
    if not run_all_tf:
        single_tf = st.selectbox(
            "Timeframe",
            list(TIMEFRAME_CONFIG.keys()),
            format_func=lambda tf: TIMEFRAME_CONFIG[tf]["label"],
            key="bt_single_tf",
        )

    historical_regime_available = isinstance(vni_df, pd.DataFrame) and not vni_df.empty and "Close" in vni_df.columns
    with st.expander("🧭 Backtest Assumptions & Overrides", expanded=False):
        c4, c5 = st.columns(2)
        with c4:
            regime_bt = st.selectbox(
                "Regime thị trường",
                ["bull", "sideways", "bear"],
                index=0,
                key="bt_regime",
                help="Chọn chế độ thị trường để backtest. bull=tăng, sideways=đi ngang, bear=giảm.\n"
                     "Ảnh hưởng trực tiếp đến regime_filter của từng TF: 1W chỉ cho BUY khi bull.",
            )
        with c5:
            macro_bt = st.slider(
                "Macro Score", 0.0, 10.0, 6.0, step=0.5,
                key="bt_macro",
                help="Điểm vĩ mô (0–10) áp dụng cho scoring. 10 = môi trường rất thuận lợi.",
            )

        use_historical_regime = st.toggle(
            "Dùng regime lịch sử VNINDEX",
            value=historical_regime_available,
            disabled=not historical_regime_available,
            key="bt_hist_regime",
            help="Nếu có dữ liệu VNINDEX từ lần cập nhật macro gần nhất, backtest sẽ dùng regime rule-based theo từng ngày thay vì áp một regime cố định cho toàn bộ lịch sử.",
        )
        if not historical_regime_available:
            st.caption("Chạy `Cập nhật Macro` để bật backtest theo regime lịch sử VNINDEX.")

    mode_label = "historical VNI rule-based" if historical_regime_available and use_historical_regime else f"scalar {st.session_state.get('bt_regime', 'bull')}"
    st.caption(
        f"Assumptions hiện tại: regime {st.session_state.get('bt_regime', 'bull')} | "
        f"macro {float(st.session_state.get('bt_macro', 6.0)):.1f} | {mode_label}."
    )

    with st.expander("⚠️ Backtest Trust & Assumptions", expanded=False):
        st.markdown(
            "- Macro score vẫn đang giữ cố định cho toàn bộ run backtest; regime có thể chạy theo lịch sử VNINDEX rule-based nếu dữ liệu macro đã được cập nhật.\n"
            "- T+2 exits được enforce theo số phiên nắm giữ, không phải theo dữ liệu order book thực.\n"
            "- Fill logic hiện dùng heuristic theo giá bar/stop/target; app đã chặn mua ở bar trần khóa cứng, chặn bán ở bar sàn khóa cứng, bỏ qua execution trên bar volume = 0, và cap kích thước entry/exit theo thanh khoản bar nên có thể unwind nhiều bar, nhưng vẫn chưa có mô hình queue priority, ATO/ATC hay halt chi tiết.\n"
            "- Routing biên độ giá dùng exchange map của ticker để phân biệt HOSE/HNX/UPCOM.\n"
            "- Kết quả phù hợp cho decision-support và so sánh tương đối, chưa phải execution-grade simulation."
        )

    if st.button("⚡ Chạy Backtest", type="primary", key="bt_run"):
        df_raw, src = data_dict.get(ticker, (None, "N/A"))
        if df_raw is None or df_raw.empty:
            st.error(f"Không có dữ liệu cho {ticker}")
            return

        resolved_exchange_map = exchange_map or {}
        exchange = str(resolved_exchange_map.get(ticker, TICKER_EXCHANGE.get(ticker.upper(), "HOSE"))).strip().upper() or "HOSE"
        benchmark_close = vni_df["Close"] if use_historical_regime and historical_regime_available else None
        regime_mode_label = (
            f"historical VNI rule-based | fallback {regime_bt}"
            if benchmark_close is not None
            else f"scalar {regime_bt}"
        )

        with st.spinner("Đang chạy backtest…"):
            if run_all_tf:
                results = run_multi_tf_backtest(
                    df_raw,
                    ticker=ticker,
                    initial_capital=capital,
                    regime=regime_bt,
                    macro_score=macro_bt,
                    exchange=exchange,
                    benchmark_close=benchmark_close,
                )
            else:
                assert single_tf is not None
                results = {
                    single_tf: run_backtest(
                        df_raw,
                        single_tf,
                        ticker=ticker,
                        initial_capital=capital,
                        regime=regime_bt,
                        macro_score=macro_bt,
                        exchange=exchange,
                        benchmark_close=benchmark_close,
                    )
                }

        # ── Summary table ─────────────────────────────────────
        st.subheader(f"📊 Kết quả — {ticker} | {src}")
        st.caption(
            f"Exchange: {exchange} | Source: {src} | "
            f"Regime mode: {regime_mode_label} | Macro input: {macro_bt:.1f}"
        )
        summary_df = summarise_results(results)
        compare_df = _backtest_review_table(results)
        review_summary = _backtest_review_summary(compare_df)
        decision_state = _backtest_decision_state(review_summary)

        render_decision_panel(
            "Backtest review summary",
            decision_state["primary"],
            decision_state["secondary"],
            metrics=[
                ("Best TF", review_summary["best_tf"], str(review_summary["best_verdict"])),
                ("Robust TFs", str(int(review_summary["robust_count"])), f"/{len(compare_df)} timeframe"),
                ("Review Mode", "Multi-TF" if run_all_tf else "Single TF", f"Exchange {exchange}"),
                ("Assumptions", regime_mode_label, f"Macro {macro_bt:.1f}"),
            ],
            tone=decision_state["tone"],
        )

        render_guidance_callout(
            "Review flow",
            "Dùng comparison matrix để chọn timeframe đáng xem sâu trước khi mở từng tab chi tiết.",
            tone="info",
        )
        st.dataframe(
            compare_df[["Rank", "TF", "Verdict", "Review Score", "Total Ret %", "Sharpe", "Max DD %", "Win Rate %", "# Trades", "Error"]],
            width="stretch",
            hide_index=True,
        )

        with st.expander("📋 Raw performance table", expanded=False):
            st.dataframe(summary_df, width="stretch", hide_index=True)

        # ── Per-TF equity curves ──────────────────────────────
        st.subheader("📈 Equity Curves")
        tf_tabs = st.tabs(list(results.keys()))
        for tab, (tf, res) in zip(tf_tabs, results.items()):
            with tab:
                m = res.metrics
                if "error" in m:
                    st.warning(f"Error: {m['error']}")
                    continue

                c_a, c_b, c_c, c_d = st.columns(4)
                c_a.metric("CAGR",     f"{m.get('cagr', 0):.1f}%")
                c_b.metric("Sharpe",   f"{m.get('sharpe', 0):.2f}")
                c_c.metric("Max DD",   f"{m.get('max_dd', 0):.1f}%")
                c_d.metric("Win Rate", f"{m.get('win_rate', 0):.1f}%")

                fig = equity_chart(
                    res.equity_curve, capital,
                    title=f"{ticker} — {tf} | {len(res.trades)} trades",
                )
                st.plotly_chart(fig, width="stretch")

                # Trade log
                if res.trades:
                    t_df = trades_to_df(res)
                    st.dataframe(t_df, width="stretch", hide_index=True)

                    # Exit reason distribution
                    reasons = pd.Series([t.exit_reason for t in res.trades])
                    reason_counts = reasons.value_counts()
                    fig_r = go.Figure(go.Pie(
                        labels=reason_counts.index,
                        values=reason_counts.values,
                        hole=0.4,
                        marker_colors=[GREEN, YELLOW, RED, "#888"],
                    ))
                    fig_r.update_layout(
                        height=250, template="plotly_dark",
                        paper_bgcolor="#0e1117",
                        margin=dict(l=0, r=0, t=30, b=0),
                        title="Exit Reasons",
                    )
                    st.plotly_chart(fig_r, width="stretch")
