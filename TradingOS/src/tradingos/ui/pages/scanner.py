"""Scanner page — batch universe screener."""
from __future__ import annotations

import streamlit as st
import pandas as pd

from tradingos.engines.scanner_service import ScannerService
from tradingos.engines.audit_service import AuditService
from tradingos.data.schemas import ScanRequest
from tradingos.core.nlp import generate_summary_headline

_ACTION_ORDER = {"STRONG_BUY": 0, "BUY": 1, "WATCH": 2, "NO_ACTION": 3, "EXIT": 4, "FORCED_EXIT": 5}


def render() -> None:
    st.title("📡 Scanner")
    st.caption("Quét toàn bộ universe theo MFPM score — lọc cơ hội mua theo Mode A/B/W.")

    with st.form("scanner_form"):
        col_left, col_right = st.columns([3, 1])
        ticker_input = col_left.text_area(
            "Danh sách mã (mỗi mã một dòng, hoặc CSV — để trống = quét theo sàn đã chọn)",
            placeholder="VCB\nHPG\nSSI\nVNM",
            height=120,
        )
        exchange = col_left.selectbox("Sàn", ["HOSE", "HNX", "ALL"], index=0)
        min_mfpm = col_right.slider("MFPM tối thiểu", 0, 120, 0)
        min_sms = col_right.slider("SMS tối thiểu", 0, 100, 0)
        max_workers = col_right.slider("Workers", 1, 16, 8)
        # [BUG-6 FIX] include_blocked was hardcoded True — AMF filter never applied.
        # Default False: exclude AMF-blocked tickers (manipulation suspected).
        include_blocked = col_right.checkbox(
            "Hiển thị mã bị AMF chặn",
            value=False,
            help="AMF (Anti-Manipulation Filter) — bỏ chọn để lọc mã nghi thao túng",
        )
        submitted = st.form_submit_button("🔍 Quét ngay", use_container_width=True)

    if not submitted:
        return

    raw = ticker_input.replace(",", "\n").replace(" ", "\n")
    tickers = [t.strip().upper() for t in raw.split("\n") if t.strip()] or None

    if tickers is None:
        st.info(f"⏳ Quét toàn bộ {exchange} — có thể mất vài phút...")

    request = ScanRequest(
        tickers=tickers,
        exchange=exchange,
        limit=len(tickers) if tickers else 2000,
        min_mfpm_score=min_mfpm,
        min_sms=min_sms,
        min_action="",          # hiển thị tất cả tín hiệu kể cả NO_ACTION
        include_blocked=include_blocked,
    )

    svc = ScannerService(max_workers=max_workers)
    audit_svc = AuditService()

    with st.spinner("Đang quét..."):
        result = svc.scan(request)

    st.success(
        f"✅ Quét xong: **{result.tickers_scanned}** mã → "
        f"hiển thị **{result.tickers_passed}** kết quả"
    )

    if not result.results:
        st.info("Không có kết quả phù hợp.")
        return

    # Log scan to audit
    for item in result.results:
        audit_svc.log_event(
            event_type="SCAN",
            ticker=item.ticker,
            action=item.action,
            mfpm_score=item.mfpm_score,
            sms_raw=item.sms_raw,
            confidence=item.confidence,
            extra={"signal_mode": item.signal_mode, "close": item.close, "best_pattern": item.best_pattern},
        )

    rows = []
    for item in result.results:
        rows.append({
            "Mã":       item.ticker,
            "Action":   item.action,
            "Conf":     item.confidence,
            "MFPM":     item.mfpm_score,
            "Macro":    item.macro_regime,
            "MacroScore": item.macro_score,
            "Sector Flow": item.sector_flow,
            "BCTC Risk": item.earnings_risk,
            "FundScore": item.fundamental_score,
            "W-Score":  item.mode_w_score,
            "SMS":      item.sms_raw,
            "SMS Label":item.sms_label,
            "Mode":     item.signal_mode,
            "Giá":      item.close,
            "Vào":      item.entry,
            "SL":       item.sl,
            "TP1":      item.tp1,
            "R:R":      item.rr,
            "AMF":      item.amf_decision,
            "Pattern":  item.best_pattern,
            "HMM":      item.hmm_state,
            "Stealth":  item.stealth_accum,
            "Tóm tắt NLP": generate_summary_headline(
                ticker=item.ticker,
                action=item.action,
                mfpm_score=item.mfpm_score,
                signal_mode=item.signal_mode,
                rsi14=getattr(item, "rsi14", 50.0),
                sms_raw=item.sms_raw,
                stealth_accum=item.stealth_accum,
                best_pattern=item.best_pattern,
                distribution_warning=getattr(item, "distribution_warning", "NONE"),
                hmm_state=item.hmm_state,
            ),
            "T+ Setup":   getattr(item, "tplus_setup",    "T_NO_SETUP"),
            "T+ Verdict": getattr(item, "tplus_verdict",  "THEO_DOI"),
            "T+ Conf":    getattr(item, "tplus_confidence", 0.0),
            "CVD":        getattr(item, "cvd_signal",       "N/A"),
        })

    df_all = pd.DataFrame(rows)
    df_all["_sort"] = df_all["Action"].map(_ACTION_ORDER).fillna(9)
    df_all = df_all.sort_values(["_sort", "MFPM"], ascending=[True, False]).drop(columns="_sort")

    # ── Signal breakdown ──────────────────────────────────────────────────────
    breakdown = df_all["Action"].value_counts()
    _icons = {"STRONG_BUY": "🚀", "BUY": "🟢", "WATCH": "👀", "NO_ACTION": "⏸", "EXIT": "🔴", "FORCED_EXIT": "⚠️"}
    cols = st.columns(min(len(breakdown), 6))
    for i, (action, count) in enumerate(breakdown.items()):
        cols[i % len(cols)].metric(f"{_icons.get(action, '📋')} {action}", count)

    st.divider()

    # ── Filter controls ───────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([2, 2, 1])
    with fc1:
        selected_actions = st.multiselect(
            "Lọc Action",
            options=list(_ACTION_ORDER.keys()),
            default=[],
            placeholder="Để trống = tất cả",
            key="scanner_action_filter",
        )
    with fc2:
        selected_modes = st.multiselect(
            "Lọc Mode",
            options=sorted(df_all["Mode"].unique().tolist()),
            default=[],
            placeholder="Để trống = tất cả",
            key="scanner_mode_filter",
        )
    with fc3:
        stealth_only = st.checkbox("Stealth Accum only", key="scanner_stealth")

    df_show = df_all.copy()
    if selected_actions:
        df_show = df_show[df_show["Action"].isin(selected_actions)]
    if selected_modes:
        df_show = df_show[df_show["Mode"].isin(selected_modes)]
    if stealth_only:
        df_show = df_show[df_show["Stealth"] == True]

    st.caption(f"Hiển thị **{len(df_show)}** / {len(df_all)} mã sau lọc")

    # Colour-code Action
    def _colour_action(val: str) -> str:
        colours = {
            "STRONG_BUY": "background-color:#004d1a; color:#00c851",
            "BUY":        "background-color:#002d40; color:#33b5e5",
            "WATCH":      "background-color:#3d3000; color:#ffbb33",
            "NO_ACTION":  "color:#888",
            "EXIT":       "background-color:#3d0000; color:#ff4444",
            "FORCED_EXIT":"background-color:#260000; color:#cc0000",
        }
        return colours.get(val, "")

    styled = df_show.style.map(_colour_action, subset=["Action"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Export ────────────────────────────────────────────────────────────────
    csv_bytes = df_show.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Xuất CSV",
        data=csv_bytes,
        file_name="scan_results.csv",
        mime="text/csv",
    )

    # ── Inline NLP per high-priority result ──────────────────────────────────
    buy_items = [
        item for item in result.results
        if item.action in ("STRONG_BUY", "BUY", "WATCH")
        and item.ticker in df_show["Mã"].values
    ]
    if buy_items:
        st.divider()
        st.markdown("#### 📝 Tóm tắt tín hiệu — NLP")
        st.caption("Hiển thị tối đa 20 mã có tín hiệu STRONG_BUY / BUY / WATCH đầu tiên.")
        _action_icon = {"STRONG_BUY": "🚀", "BUY": "🟢", "WATCH": "👀"}
        for item in buy_items[:20]:
            headline = generate_summary_headline(
                ticker=item.ticker,
                action=item.action,
                mfpm_score=item.mfpm_score,
                signal_mode=item.signal_mode,
                rsi14=getattr(item, "rsi14", 50.0),
                sms_raw=item.sms_raw,
                stealth_accum=item.stealth_accum,
                best_pattern=item.best_pattern,
                distribution_warning=getattr(item, "distribution_warning", "NONE"),
                hmm_state=item.hmm_state,
            )
            icon = _action_icon.get(item.action, "📋")
            with st.expander(
                f"{icon} **{item.ticker}** — {item.action}  |  {headline}",
                expanded=False,
            ):
                col_l, col_r = st.columns([1, 1])
                with col_l:
                    st.markdown(f"**Giá:** {item.close:,.0f}")
                    st.markdown(f"**Vào lệnh:** {item.entry:,.0f}")
                    st.markdown(f"**Cắt lỗ:** {item.sl:,.0f}")
                    st.markdown(f"**TP1:** {item.tp1:,.0f}")
                    st.markdown(f"**R:R:** 1:{item.rr:.1f}")
                with col_r:
                    st.markdown(f"**Mode:** {item.signal_mode}")
                    st.markdown(f"**MFPM:** {item.mfpm_score}")
                    st.markdown(f"**SMS:** {item.sms_raw} ({item.sms_label})")
                    st.markdown(f"**HMM:** {item.hmm_state}")
                    st.markdown(f"**Pattern:** {item.best_pattern}")
                    st.markdown(f"**Stealth:** {'✅' if item.stealth_accum else '❌'}")
                if st.button(f"📈 Mở Profiler — {item.ticker}", key=f"nlp_open_{item.ticker}"):
                    st.session_state["profiler_ticker"] = item.ticker
                    st.session_state["nav"] = "🔍 Profiler"
                    st.rerun()

    # ── Drill-down to profiler ────────────────────────────────────────────────
    st.divider()
    ticker_options = df_show["Mã"].tolist()
    if ticker_options:
        selected = st.selectbox("Xem chi tiết mã:", ticker_options)
        if selected and st.button("📈 Mở Profiler", use_container_width=True):
            st.session_state["profiler_ticker"] = selected
            st.session_state["nav"] = "🔍 Profiler"
            st.rerun()
