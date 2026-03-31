"""Scanner page — batch universe screener."""
from __future__ import annotations

import streamlit as st
import pandas as pd

from tradingos.engines.scanner_service import ScannerService
from tradingos.data.schemas import ScanRequest


def render() -> None:
    st.title("📡 Scanner")
    st.caption("Quét toàn bộ universe theo MFPM score — lọc cơ hội mua theo Mode A/B/W.")

    with st.form("scanner_form"):
        ticker_input = st.text_area(
            "Danh sách mã (mỗi mã một dòng — để trống = quét toàn bộ HOSE + HNX)",
            placeholder="VCB\nHPG\nSSI\nVNM",
            height=120,
        )
        submitted = st.form_submit_button("🔍 Quét ngay", use_container_width=True)

    if submitted:
        tickers = [t.strip().upper() for t in ticker_input.split("\n") if t.strip()] or None

        if tickers is None:
            st.info("⏳ Quét toàn bộ HOSE + HNX — có thể mất vài phút...")

        request = ScanRequest(
            tickers=tickers,
            limit=len(tickers) if tickers else 500,
        )

        svc = ScannerService(max_workers=min(8, max(4, len(tickers or []) // 20 + 4)))
        with st.spinner("Đang quét..."):
            result = svc.scan(request)

        st.success(f"✅ Quét xong: {result.tickers_scanned} mã → **{result.tickers_passed} kết quả**")

        if result.results:
            rows = []
            for item in result.results:
                rows.append({
                    "Mã": item.ticker,
                    "Action": item.action,
                    "Conf": item.confidence,
                    "MFPM": item.mfpm_score,
                    "SMS": item.sms_raw,
                    "Mode": item.signal_mode,
                    "Giá": f"{item.close:,.0f}",
                    "Vào": f"{item.entry:,.0f}",
                    "SL": f"{item.sl:,.0f}",
                    "TP1": f"{item.tp1:,.0f}",
                    "R:R": f"1:{item.rr:.1f}",
                    "AMF": item.amf_decision,
                    "Pattern": item.best_pattern,
                    "HMM": item.hmm_state,
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Quick drill-down
            selected = st.selectbox("Xem chi tiết mã:", [r.ticker for r in result.results])
            if selected and st.button("Mở Profiler"):
                st.session_state["profiler_ticker"] = selected
                st.info(f"Chuyển sang tab Profiler và nhập **{selected}**.")
        else:
            st.info("Không có kết quả phù hợp.")
