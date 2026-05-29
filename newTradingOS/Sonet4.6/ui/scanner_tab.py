"""
ui/scanner_tab.py — NewTradingOS v14.0
Reusable scanner tab for all 5 timeframes.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import streamlit as st
import pandas as pd

from config import TIMEFRAME_CONFIG, score_to_action
from core.scoring import SignalResult, batch_score
from ui.components import score_badge, source_badge, candlestick_chart, score_radar
from core.indicators import compute_all

# ── Audit logging ─────────────────────────────────────────────
_AUDIT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "audit")


def _write_audit(tf: str, results: list[SignalResult], regime: str, macro_score: float) -> str:
    """Append one scan run to data/audit/YYYY-MM-DD.jsonl. Returns file path."""
    os.makedirs(_AUDIT_DIR, exist_ok=True)
    date_str  = datetime.now().strftime("%Y-%m-%d")
    filepath  = os.path.join(_AUDIT_DIR, f"{date_str}.jsonl")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record = {
        "ts":          timestamp,
        "tf":          tf,
        "regime":      regime,
        "macro_score": macro_score,
        "n_tickers":   len(results),
        "results": [
            {
                "ticker":     r.ticker,
                "score":      round(r.score, 1),
                "action":     r.action,
                "price":      r.price,
                "stop_loss":  r.stop_loss,
                "take_profit":r.take_profit,
                "rr_ratio":   r.rr_ratio,
                "manip_flag": r.manip_flag,
                "regime_ok":  r.regime_ok,
            }
            for r in results
        ],
    }
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return filepath


def render_scanner_tab(
    tf: str,
    data_dict: dict,          # {ticker: (df, source)}
    regime: str,
    macro_score: float,
    foreign_flows: dict,
    lang: str = "VI",
) -> None:
    """
    Compute ALL tickers unconditionally, write audit log, and display the
    complete result table. No rows are hidden — the user sorts/filters using
    the Streamlit dataframe column headers and the search toolbar.
    """
    cfg   = TIMEFRAME_CONFIG[tf]
    label = cfg["label"] if lang == "VI" else cfg["label_en"]

    st.subheader(f"📡 Scanner — {label}")

    # ── Score every ticker (no min_score filter) ──────────────
    with st.spinner(f"Đang quét {len(data_dict)} mã ({tf})…"):
        all_results: list[SignalResult] = batch_score(
            data_dict, tf,
            regime=regime,
            macro_score=macro_score,
            foreign_flows=foreign_flows,
            min_score=None,
        )

    if not all_results:
        st.warning("Không có dữ liệu để quét.")
        return

    # ── Audit log ─────────────────────────────────────────────
    audit_path = _write_audit(tf, all_results, regime, macro_score)
    st.caption(f"🗂️ Audit → `{audit_path}`  |  {len(all_results)} mã  |  "
               f"{datetime.now().strftime('%H:%M:%S')}")

    # ── Summary metrics (full unfiltered set) ─────────────────
    buy_count  = sum(1 for r in all_results if r.action in ("BUY", "STRONG BUY"))
    watch_count= sum(1 for r in all_results if r.action == "WATCH")
    avg_score  = sum(r.score for r in all_results) / len(all_results)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tổng mã", len(all_results))
    m2.metric("BUY / STRONG BUY", buy_count)
    m3.metric("WATCH", watch_count)
    m4.metric("Score trung bình", f"{avg_score:.1f}")

    # ── Full result table — all rows, color-coded by Action ──
    rows = []
    for r in all_results:
        src = data_dict.get(r.ticker, (None, "NONE"))[1]
        rows.append({
            "Mã":        r.ticker,
            "Score":     round(r.score, 1),
            "Action":    r.action,
            "Giá":       round(r.price, 0),
            "Stop":      round(r.stop_loss, 0),
            "Target":    round(r.take_profit, 0),
            "R/R":       r.rr_ratio,
            "RSI":       r.indicators.get("RSI", None),
            "Vol×":      r.indicators.get("Vol_ratio", None),
            "Regime OK": r.regime_ok,
            "Manip":     r.manip_flag,
            "Nguồn":     src,
        })

    df_out = pd.DataFrame(rows)

    # Row background colours keyed on Action
    _ACTION_BG = {
        "STRONG BUY": "background-color: #1a5e2a; color: #ffffff",
        "BUY":        "background-color: #c6efce; color: #275b2a",
        "HOLD":       "background-color: #ffeb9c; color: #5a4000",
        "WATCH":      "background-color: #dae8fc; color: #0a3c6e",
        "SELL":       "background-color: #ffc7ce; color: #9c0006",
    }

    def _colour_row(row: pd.Series) -> list[str]:
        style = _ACTION_BG.get(row["Action"], "")
        return [style] * len(row)

    styled = df_out.style.apply(_colour_row, axis=1)

    st.info("💡 Màu hàng: 🟩 STRONG BUY → BUY → 🟨 HOLD → 🟦 WATCH → 🟥 SELL. "
            "Click tiêu đề cột để sắp xếp.")
    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score":     st.column_config.NumberColumn("Score", format="%.1f",
                             help="Điểm tín hiệu 0–100. ≥65 là vùng mua, <30 là bán."),
            "Giá":       st.column_config.NumberColumn("Giá (VND)", format="%,.0f"),
            "Stop":      st.column_config.NumberColumn("Stop (VND)", format="%,.0f"),
            "Target":    st.column_config.NumberColumn("Target (VND)", format="%,.0f"),
            "R/R":       st.column_config.NumberColumn("R/R", format="1:%.1f"),
            "RSI":       st.column_config.NumberColumn("RSI", format="%.1f"),
            "Vol×":      st.column_config.NumberColumn("Vol×", format="%.2f"),
            "Regime OK": st.column_config.CheckboxColumn("Regime OK"),
            "Manip":     st.column_config.CheckboxColumn("Manip ⚠️"),
        },
        height=min(700, 56 + len(df_out) * 35),
    )

    # ── Download full CSV ─────────────────────────────────────
    csv = df_out.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        f"⬇️ Tải CSV đầy đủ ({tf}) — {len(df_out)} mã", csv,
        file_name=f"scan_{tf}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key=f"dl_{tf}",
    )

    # ── Detail expanders — ALL tickers grouped by action ─────
    st.divider()
    st.subheader("🔍 Chi tiết tất cả tín hiệu")

    # Newbie guide (collapsed by default)
    with st.expander("📖 Hướng dẫn đọc kết quả (dành cho người mới)", expanded=False):
        st.markdown("""
**Score (0–100)** — Điểm tổng hợp tất cả chỉ báo kỹ thuật.
- ≥ 80 → **STRONG BUY**: Tín hiệu rất mạnh, nhiều chỉ báo cùng đồng thuận tăng.
- 65–79 → **BUY**: Tín hiệu tốt, phù hợp để mở vị thế.
- 45–64 → **HOLD**: Chưa rõ xu hướng, nếu đang giữ thì tiếp tục chờ.
- 30–44 → **WATCH**: Tín hiệu yếu, quan sát thêm, chưa nên vào hàng.
- < 30 → **SELL**: Tín hiệu xấu, nếu đang giữ thì cân nhắc cắt lỗ.

**Stop Loss** — Mức giá bạn nên đặt lệnh cắt lỗ. Nếu giá xuống dưới mức này, thoát lệnh để bảo vệ vốn.

**Target** — Mức giá mục tiêu chốt lời dựa trên phân tích kỹ thuật.

**R/R (Risk/Reward)** — Tỉ lệ lời/lỗ. R/R = 1:2 nghĩa là mỗi đồng rủi ro bạn có thể lời 2 đồng. Nên giao dịch khi R/R ≥ 1:1.5.

**RSI (14)** — Chỉ số sức mạnh tương đối.
- RSI > 70: Vùng mua quá mức (cẩn thận điều chỉnh).
- RSI 40–70: Vùng trung tính/tích lũy.
- RSI < 30: Vùng bán quá mức (có thể là cơ hội mua).

**Vol× (Volume Ratio)** — Khối lượng phiên này so với trung bình 20 phiên.
- Vol× > 2: Phiên có khối lượng đột biến → thường đi kèm breakout.
- Vol× < 0.5: Giao dịch uể oải, không có động lực.

**ADX** — Độ mạnh của xu hướng (không phân biệt tăng/giảm).
- ADX > 25: Xu hướng rõ ràng.
- ADX < 20: Sideway, không có xu hướng.

**BB %B** — Vị trí giá trong dải Bollinger Bands (0 = cạnh dưới, 1 = cạnh trên, 0.5 = giữa).

**MFI** — Chỉ số dòng tiền. MFI > 80 → dòng tiền vào mạnh. MFI < 20 → dòng tiền ra nhiều.

**Regime OK** ✅ — Chế độ thị trường hiện tại phù hợp với chiến lược mua. ❌ = thị trường đang xấu, hạn chế mở vị thế mới.

**Manip ⚠️** — Phát hiện dấu hiệu thao túng giá (đẩy giá, bán phá giá). Nếu có dấu hiệu này, hãy thận trọng hơn.
        """)

    # Group results by action priority
    _ACTION_ORDER = ["STRONG BUY", "BUY", "HOLD", "WATCH", "SELL"]
    _ACTION_ICON  = {
        "STRONG BUY": "🟢",
        "BUY":        "🟩",
        "HOLD":       "🟨",
        "WATCH":      "🟦",
        "SELL":       "🟥",
    }
    grouped: dict[str, list] = {a: [] for a in _ACTION_ORDER}
    for r in all_results:
        grouped.setdefault(r.action, []).append(r)

    for action in _ACTION_ORDER:
        group = grouped.get(action, [])
        if not group:
            continue
        icon = _ACTION_ICON.get(action, "⬜")
        with st.expander(f"{icon} {action} — {len(group)} mã", expanded=(action in ("STRONG BUY", "BUY"))):
            # Action-level explanation
            _ACTION_EXPLAIN = {
                "STRONG BUY": "Tín hiệu rất mạnh. Nhiều chỉ báo đồng thuận tăng. Phù hợp mở vị thế đầy đủ với stop loss chặt.",
                "BUY":        "Tín hiệu tốt. Phù hợp mở vị thế một phần, chờ xác nhận thêm nếu muốn an toàn hơn.",
                "HOLD":       "Chưa có tín hiệu rõ ràng. Nếu đang giữ thì tiếp tục, chưa nên mua thêm.",
                "WATCH":      "Tín hiệu yếu. Cho vào danh sách theo dõi, chờ điểm vào tốt hơn.",
                "SELL":       "Tín hiệu xấu. Nếu đang giữ cổ phiếu này, cân nhắc thoát ra để bảo vệ vốn.",
            }
            st.caption(_ACTION_EXPLAIN.get(action, ""))

            for r in group:
                with st.expander(
                    f"**{r.ticker}** — Score: {r.score:.0f}  |  "
                    f"Giá: {r.price:,.0f}  |  Stop: {r.stop_loss:,.0f}  |  "
                    f"Target: {r.take_profit:,.0f}  |  R/R: 1:{r.rr_ratio}",
                    expanded=False,
                ):
                    c_info, c_chart = st.columns([1, 3])

                    with c_info:
                        st.markdown("##### Tóm tắt quyết định")
                        rsi_val  = r.indicators.get("RSI", None)
                        adx_val  = r.indicators.get("ADX", None)
                        vol_val  = r.indicators.get("Vol_ratio", None)
                        mfi_val  = r.indicators.get("MFI", None)
                        bb_val   = r.indicators.get("BB_%B", None)
                        manip_s  = r.indicators.get("Manip_score", None)

                        # Score bar
                        score_pct = int(r.score)
                        st.progress(score_pct / 100,
                                    text=f"Score: **{r.score:.0f}/100**")

                        st.markdown("**Các chỉ báo chính:**")
                        if rsi_val is not None:
                            rsi_note = ("quá mua ⚠️" if rsi_val > 70
                                        else "quá bán 💡" if rsi_val < 30
                                        else "bình thường")
                            st.caption(f"RSI {rsi_val:.1f} — {rsi_note}")
                        if adx_val is not None:
                            adx_note = "xu hướng mạnh ✅" if adx_val > 25 else "sideway ⚠️"
                            st.caption(f"ADX {adx_val:.1f} — {adx_note}")
                        if vol_val is not None:
                            vol_note = "đột biến 🚀" if vol_val > 2 else ("thấp 😴" if vol_val < 0.5 else "bình thường")
                            st.caption(f"Vol× {vol_val:.2f} — {vol_note}")
                        if mfi_val is not None:
                            mfi_note = "dòng tiền vào mạnh ✅" if mfi_val > 60 else ("dòng tiền ra ⚠️" if mfi_val < 40 else "trung tính")
                            st.caption(f"MFI {mfi_val:.1f} — {mfi_note}")
                        if bb_val is not None:
                            bb_note = ("sát trần BB ⚠️" if bb_val > 0.8
                                       else "sát đáy BB 💡" if bb_val < 0.2
                                       else "giữa dải BB")
                            st.caption(f"BB %B {bb_val:.2f} — {bb_note}")

                        st.markdown("**Quản lý rủi ro:**")
                        if r.price > 0 and r.stop_loss > 0:
                            risk_pct = abs(r.price - r.stop_loss) / r.price * 100
                            st.caption(f"Rủi ro nếu chạm Stop: **{risk_pct:.1f}%** vốn vị thế")
                        if r.price > 0 and r.take_profit > 0:
                            gain_pct = abs(r.take_profit - r.price) / r.price * 100
                            st.caption(f"Tiềm năng lợi nhuận: **{gain_pct:.1f}%** nếu đạt Target")

                        if not r.regime_ok:
                            st.warning("⚠️ Chế độ thị trường không thuận lợi — hạn chế mở vị thế mới.")
                        if r.manip_flag:
                            st.error(f"🚨 Phát hiện dấu hiệu thao túng (điểm: {manip_s}). Hãy thận trọng!")

                        st.markdown("**Breakdown điểm:**")
                        for k, v in r.breakdown.items():
                            bar = "█" * max(0, int(v * 3))
                            st.caption(f"{k}: {bar} {v:.1f}")

                    with c_chart:
                        df_raw, _ = data_dict.get(r.ticker, (None, None))
                        if df_raw is not None and not df_raw.empty:
                            df_ind = compute_all(df_raw.copy(), TIMEFRAME_CONFIG[tf])
                            lookback_bars = {"1W": 60, "2W": 90, "1M": 120,
                                             "3M": 200, "5M": 300}.get(tf, 120)
                            fig = candlestick_chart(
                                df_ind.tail(lookback_bars), r.ticker, tf,
                                signal=r, height=480,
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("Không có dữ liệu biểu đồ.")

    # ── Audit Viewer ──────────────────────────────────────────
    with st.expander("🗂️ Lịch sử Audit (tất cả lần chạy)", expanded=False):
        _render_audit_viewer(tf)


def _render_audit_viewer(tf: str) -> None:
    """Load and display all past audit runs for this timeframe."""
    if not os.path.isdir(_AUDIT_DIR):
        st.info("Chưa có dữ liệu audit.")
        return

    files = sorted(
        [f for f in os.listdir(_AUDIT_DIR) if f.endswith(".jsonl")],
        reverse=True,
    )
    if not files:
        st.info("Chưa có dữ liệu audit.")
        return

    selected_file = st.selectbox("Chọn ngày", files, key=f"audit_date_{tf}")
    filepath = os.path.join(_AUDIT_DIR, selected_file)

    records = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # filter to this timeframe
    runs = [r for r in records if r.get("tf") == tf]
    if not runs:
        st.info(f"Không có lần chạy nào cho TF={tf} trong ngày này.")
        return

    run_labels = [f"{r['ts']}  ({r['n_tickers']} mã, regime={r['regime']}, macro={r['macro_score']:.0f})" for r in runs]
    sel_idx    = st.selectbox("Chọn lần chạy", range(len(runs)), format_func=lambda i: run_labels[i],
                               key=f"audit_run_{tf}")
    run = runs[sel_idx]

    rows = [
        {
            "Mã":       res["ticker"],
            "Score":    res["score"],
            "Action":   res["action"],
            "Giá":      f"{res['price']:,.0f}",
            "Stop":     f"{res['stop_loss']:,.0f}",
            "Target":   f"{res['take_profit']:,.0f}",
            "R/R":      f"1:{res['rr_ratio']}",
            "Regime OK":"✅" if res["regime_ok"] else "❌",
            "Manip":    "⚠️" if res["manip_flag"] else "✅",
        }
        for res in run["results"]
    ]
    df_audit = pd.DataFrame(rows)
    st.dataframe(df_audit, use_container_width=True, hide_index=True)

    csv = df_audit.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        f"⬇️ Tải audit CSV", csv,
        file_name=f"audit_{tf}_{run['ts'].replace(':', '-').replace(' ', '_')}.csv",
        mime="text/csv",
        key=f"dl_audit_{tf}_{sel_idx}",
    )
