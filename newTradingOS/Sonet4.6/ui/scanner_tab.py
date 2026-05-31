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
from core.audit import log_events, ACTION_SCAN
from core.scoring import SignalResult, batch_score
from ui.components import score_badge, source_badge, candlestick_chart, score_radar
from core.indicators import compute_all

# ── Audit logging ─────────────────────────────────────────────
_AUDIT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "audit")


def _format_bar_date(df: pd.DataFrame | None) -> str:
    if df is None or df.empty:
        return "—"
    idx = df.index[-1]
    try:
        idx = idx.date()
    except AttributeError:
        pass
    return str(idx)


def _source_mix(data_dict: dict) -> str:
    counts: dict[str, int] = {}
    for _, (_, source) in data_dict.items():
        src = source or "UNKNOWN"
        counts[src] = counts.get(src, 0) + 1
    if not counts:
        return "—"
    return ", ".join(f"{src}:{counts[src]}" for src in sorted(counts))


def _latest_bar_date(data_dict: dict) -> str:
    latest = None
    for df, _ in data_dict.values():
        if df is None or df.empty:
            continue
        idx = df.index[-1]
        try:
            idx = idx.date()
        except AttributeError:
            pass
        latest = idx if latest is None or idx > latest else latest
    return str(latest) if latest is not None else "—"


def _foreign_flow_basis(tf: str, foreign_flows: dict) -> str:
    if tf in ("2W", "1M", "3M", "5M"):
        return "KBS snapshot | session net only" if foreign_flows else "not loaded"
    return "not used"


def _scan_result_records(
    results: list[SignalResult],
    data_dict: dict,
    exchange_map: dict | None = None,
) -> list[dict]:
    rows = []
    for r in results:
        df_raw, src = data_dict.get(r.ticker, (None, "NONE"))
        rows.append({
            "ticker": r.ticker,
            "score": round(r.score, 1),
            "action": r.action,
            "price": r.price,
            "stop_loss": r.stop_loss,
            "take_profit": r.take_profit,
            "rr_ratio": r.rr_ratio,
            "manip_flag": r.manip_flag,
            "regime_ok": r.regime_ok,
            "exchange": exchange_map.get(r.ticker, "HOSE") if exchange_map else "HOSE",
            "source": src,
            "bar_date": _format_bar_date(df_raw),
            "message": r.message,
            "adv20_bn": round(float(r.indicators.get("ADV20_bn", 0.0) or 0.0), 2),
        })
    return rows


def _scan_summary_detail(
    tf: str,
    result_rows: list[dict],
    regime: str,
    macro_score: float,
    audit_path: str,
    source_mix: str,
    latest_bar_date: str,
    foreign_flow_basis: str,
    macro_stale: list[str] | None = None,
) -> dict:
    buy_count = sum(1 for row in result_rows if row["action"] in ("BUY", "STRONG BUY"))
    watch_count = sum(1 for row in result_rows if row["action"] == "WATCH")
    avg_score = round(
        sum(float(row["score"]) for row in result_rows) / len(result_rows),
        1,
    ) if result_rows else 0.0
    top_signals = [
        {
            "ticker": row["ticker"],
            "action": row["action"],
            "score": row["score"],
            "source": row["source"],
            "bar_date": row["bar_date"],
        }
        for row in sorted(
            result_rows,
            key=lambda item: (-float(item["score"]), item["ticker"]),
        )[:5]
    ]
    return {
        "kind": "summary",
        "n_tickers": len(result_rows),
        "buy_count": buy_count,
        "watch_count": watch_count,
        "avg_score": avg_score,
        "regime": regime,
        "macro_score": macro_score,
        "audit_file": audit_path,
        "source_mix": source_mix,
        "latest_bar_date": latest_bar_date,
        "foreign_flow_basis": foreign_flow_basis,
        "macro_stale": list(macro_stale or []),
        "top_signals": top_signals,
    }


def _build_scan_audit_events(
    tf: str,
    results: list[SignalResult],
    regime: str,
    macro_score: float,
    data_dict: dict,
    foreign_flows: dict,
    audit_path: str,
    exchange_map: dict | None = None,
    macro_stale: list[str] | None = None,
) -> list[dict]:
    result_rows = _scan_result_records(results, data_dict, exchange_map=exchange_map)
    source_mix = _source_mix(data_dict)
    latest_bar_date = _latest_bar_date(data_dict)
    foreign_flow_basis = _foreign_flow_basis(tf, foreign_flows)

    events = [{
        "action": ACTION_SCAN,
        "ticker": "",
        "timeframe": tf,
        "detail": _scan_summary_detail(
            tf,
            result_rows,
            regime,
            macro_score,
            audit_path,
            source_mix,
            latest_bar_date,
            foreign_flow_basis,
            macro_stale=macro_stale,
        ),
        "result": "ok",
    }]

    for row in result_rows:
        events.append({
            "action": ACTION_SCAN,
            "ticker": row["ticker"],
            "timeframe": tf,
            "detail": {
                "kind": "result",
                "signal_action": row["action"],
                "score": row["score"],
                "price": row["price"],
                "stop_loss": row["stop_loss"],
                "take_profit": row["take_profit"],
                "rr_ratio": row["rr_ratio"],
                "manip_flag": row["manip_flag"],
                "regime_ok": row["regime_ok"],
                "exchange": row["exchange"],
                "source": row["source"],
                "bar_date": row["bar_date"],
                "message": row["message"],
                "adv20_bn": row["adv20_bn"],
                "audit_file": audit_path,
            },
            "result": "ok",
        })
    return events


def _write_audit(
    tf: str,
    results: list[SignalResult],
    regime: str,
    macro_score: float,
    data_dict: dict,
    foreign_flows: dict,
    exchange_map: dict | None = None,
    macro_stale: list[str] | None = None,
) -> str:
    """Append one scan run to data/audit/YYYY-MM-DD.jsonl. Returns file path."""
    os.makedirs(_AUDIT_DIR, exist_ok=True)
    date_str  = datetime.now().strftime("%Y-%m-%d")
    filepath  = os.path.join(_AUDIT_DIR, f"{date_str}.jsonl")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result_rows = _scan_result_records(results, data_dict, exchange_map=exchange_map)

    record = {
        "ts":          timestamp,
        "tf":          tf,
        "regime":      regime,
        "macro_score": macro_score,
        "n_tickers":   len(results),
        "source_mix":  _source_mix(data_dict),
        "latest_bar_date": _latest_bar_date(data_dict),
        "foreign_flow_basis": _foreign_flow_basis(tf, foreign_flows),
        "macro_stale": list(macro_stale or []),
        "results": result_rows,
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
    exchange_map: dict | None = None,
) -> None:
    """
    Compute ALL tickers unconditionally, write audit log, and display the
    complete result table. Scan results are cached in session_state; re-scoring
    is skipped unless data version, regime, or macro_score changes.

    Parameters
    ----------
    exchange_map : optional dict {ticker: exchange_str}
        When provided, each ticker uses its correct exchange price limit
        (HOSE ±7%, HNX ±10%, UPCoM ±15%) in the Streak indicator and scoring.
        Build from config.TICKER_EXCHANGE in the caller. Defaults to HOSE if None.
    """
    cfg   = TIMEFRAME_CONFIG[tf]
    label = cfg["label"] if lang == "VI" else cfg["label_en"]

    st.subheader(f"📡 Scanner — {label}")

    # ── Session-state scan cache ──────────────────────────────
    data_version = st.session_state.get("data_version", 0)
    cache_key    = f"{tf}|{regime}|{macro_score:.2f}|{data_version}"
    scan_cache   = st.session_state.setdefault("_scan_cache", {})
    macro_stale = st.session_state.get("macro_stale", [])

    if cache_key in scan_cache:
        all_results: list[SignalResult] = scan_cache[cache_key]
        st.caption(
            f"📋 Cached  |  {len(all_results)} mã  |  "
            f"v{data_version}  |  {datetime.now().strftime('%H:%M:%S')}"
        )
    else:
        with st.spinner(f"Đang quét {len(data_dict)} mã ({tf})…"):
            all_results = batch_score(
                data_dict, tf,
                regime=regime,
                macro_score=macro_score,
                foreign_flows=foreign_flows,
                min_score=None,
                exchange_map=exchange_map,
            )
        scan_cache[cache_key] = all_results
        # Write audit only on fresh scan runs
        audit_path = _write_audit(
            tf,
            all_results,
            regime,
            macro_score,
            data_dict,
            foreign_flows,
            exchange_map=exchange_map,
            macro_stale=macro_stale,
        )
        log_events(
            _build_scan_audit_events(
                tf,
                all_results,
                regime,
                macro_score,
                data_dict,
                foreign_flows,
                audit_path,
                exchange_map=exchange_map,
                macro_stale=macro_stale,
            )
        )
        st.caption(
            f"🗂️ Audit → `{audit_path}`  |  {len(all_results)} mã  |  "
            f"{datetime.now().strftime('%H:%M:%S')}"
        )

    if not all_results:
        st.warning("Không có dữ liệu để quét.")
        return

    # ── Summary metrics (full unfiltered set) ─────────────────
    buy_count  = sum(1 for r in all_results if r.action in ("BUY", "STRONG BUY"))
    watch_count= sum(1 for r in all_results if r.action == "WATCH")
    avg_score  = sum(r.score for r in all_results) / len(all_results)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tổng mã", len(all_results))
    m2.metric("BUY / STRONG BUY", buy_count)
    m3.metric("WATCH", watch_count)
    m4.metric("Score trung bình", f"{avg_score:.1f}")

    trust1, trust2, trust3, trust4 = st.columns(4)
    trust1.caption(f"Latest bar: {_latest_bar_date(data_dict)}")
    trust2.caption(f"Source mix: {_source_mix(data_dict)}")
    trust3.caption(f"Macro as-of: {st.session_state.get('macro_updated_at') or '—'}")
    if tf in ("2W", "1M", "3M", "5M"):
        trust4.caption(
            f"Foreign flow basis: {_foreign_flow_basis(tf, foreign_flows)}"
        )
    else:
        trust4.caption(f"Foreign flow basis: {_foreign_flow_basis(tf, foreign_flows)} on this timeframe")

    _macro_stale = macro_stale
    if _macro_stale:
        st.warning(
            "Scanner trust warning: macro data is partial. "
            f"Missing components: {', '.join(_macro_stale)}."
        )

    # ── Full result table — all rows, color-coded by Action ──
    rows = []
    for r in all_results:
        df_raw, src = data_dict.get(r.ticker, (None, "NONE"))
        exchange = exchange_map.get(r.ticker, "HOSE") if exchange_map else "HOSE"
        rows.append({
            "Mã":        r.ticker,
            "Score":     round(r.score, 1),
            "Action":    r.action,
            "Sàn":       exchange,
            "Bar Date":  _format_bar_date(df_raw),
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
        width="stretch",
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

                        df_raw, src = data_dict.get(r.ticker, (None, "NONE"))
                        exchange = exchange_map.get(r.ticker, "HOSE") if exchange_map else "HOSE"
                        st.markdown("**Trust & Provenance:**")
                        st.markdown(source_badge(src), unsafe_allow_html=True)
                        st.caption(f"Exchange: {exchange}")
                        st.caption(f"Latest bar date: {_format_bar_date(df_raw)}")
                        if tf in ("2W", "1M", "3M", "5M"):
                            st.caption("Foreign flow basis: KBS snapshot | session net only")
                        if r.message:
                            st.warning(r.message)

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
                        if df_raw is not None and not df_raw.empty:
                            df_ind = compute_all(df_raw.copy(), TIMEFRAME_CONFIG[tf], exchange=exchange)
                            lookback_bars = {"1W": 60, "2W": 90, "1M": 120,
                                             "3M": 200, "5M": 300}.get(tf, 120)
                            fig = candlestick_chart(
                                df_ind.tail(lookback_bars), r.ticker, tf,
                                signal=r, height=480,
                            )
                            st.plotly_chart(fig, width="stretch")
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

    trust_bits = [
        f"Latest bar: {run.get('latest_bar_date', '—')}",
        f"Source mix: {run.get('source_mix', '—')}",
        f"Foreign flow basis: {run.get('foreign_flow_basis', '—')}",
    ]
    st.caption(" | ".join(trust_bits))
    if run.get("macro_stale"):
        st.warning(
            "Macro at scan time was partial. Missing components: "
            f"{', '.join(run.get('macro_stale', []))}."
        )

    rows = [
        {
            "Mã":       res["ticker"],
            "Score":    res["score"],
            "Action":   res["action"],
            "Sàn":      res.get("exchange", "—"),
            "Nguồn":    res.get("source", "—"),
            "Bar Date": res.get("bar_date", "—"),
            "Giá":      f"{res['price']:,.0f}",
            "Stop":     f"{res['stop_loss']:,.0f}",
            "Target":   f"{res['take_profit']:,.0f}",
            "R/R":      f"1:{res['rr_ratio']}",
            "Regime OK":"✅" if res["regime_ok"] else "❌",
            "Manip":    "⚠️" if res["manip_flag"] else "✅",
            "ADV20 bn": res.get("adv20_bn", "—"),
            "Note":     res.get("message", ""),
        }
        for res in run["results"]
    ]
    df_audit = pd.DataFrame(rows)
    st.dataframe(df_audit, width="stretch", hide_index=True)

    csv = df_audit.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        f"⬇️ Tải audit CSV", csv,
        file_name=f"audit_{tf}_{run['ts'].replace(':', '-').replace(' ', '_')}.csv",
        mime="text/csv",
        key=f"dl_audit_{tf}_{sel_idx}",
    )
